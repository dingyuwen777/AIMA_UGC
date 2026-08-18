"""Stage 5A Provider/Raw V1 契约测试。"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.contracts.provider import (
    REDACTED,
    ProviderAttemptV1,
    ProviderBillingV1,
    ProviderErrorV1,
    ProviderRequestV1,
    RawEnvelopeV1,
    RawRequestV1,
    assert_redacted_json,
    redact_json,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]


def _request(**overrides: object) -> ProviderRequestV1:
    values: dict[str, object] = {
        "request_id": uuid4(),
        "run_id": uuid4(),
        "scope_id": uuid4(),
        "provider": "fake_provider",
        "operations": "xhs",
        "operation": "keyword_search",
        "request_params": {"keyword": "爱玛", "filters": {"sort": "latest"}},
        "pagination_input": {"page": 1},
    }
    values.update(overrides)
    return ProviderRequestV1.create(**values)


def test_provider_request_fingerprint_is_stable_and_secret_free() -> None:
    request_id = uuid4()
    run_id = uuid4()
    scope_id = uuid4()
    first = _request(request_id=request_id, run_id=run_id, scope_id=scope_id)
    second = _request(
        request_id=request_id,
        run_id=run_id,
        scope_id=scope_id,
        request_params={"filters": {"sort": "latest"}, "keyword": "爱玛"},
    )

    assert first.schema_version == "provider-request.v1"
    assert first.request_fingerprint == second.request_fingerprint
    assert len(first.request_fingerprint) == 64

    other_operation = _request(
        request_id=request_id,
        run_id=run_id,
        scope_id=scope_id,
        operation="content_detail",
    )
    assert first.request_fingerprint != other_operation.request_fingerprint

    with pytest.raises((ValidationError, ValueError), match="Secret"):
        _request(request_params={"headers": {"Authorization": "Bearer forbidden"}})


def test_raw_contract_rejects_unredacted_secret_text() -> None:
    with pytest.raises(ValidationError, match="脱敏"):
        RawRequestV1(
            transport_kind="http",
            method="GET",
            path="/search?api_key=must-not-survive",
        )

    with pytest.raises(ValidationError, match="脱敏"):
        ProviderErrorV1(
            category="unknown",
            code="network_result_unknown",
            safe_summary="Authorization: Bearer must-not-survive",
            retryable=True,
        )


def test_raw_redaction_covers_suffix_tokens_inside_url_or_query_strings() -> None:
    raw = {
        "url": (
            "https://example.invalid/path?"
            "xsec_token=xsec-must-not-survive&"
            "refresh_token=refresh-must-not-survive&"
            "client_secret=secret-must-not-survive"
        )
    }

    redacted = redact_json(raw)
    rendered = json.dumps(redacted, ensure_ascii=False)

    assert "xsec-must-not-survive" not in rendered
    assert "refresh-must-not-survive" not in rendered
    assert "secret-must-not-survive" not in rendered
    assert rendered.count(REDACTED) == 3
    assert_redacted_json(redacted)
    with pytest.raises(ValueError, match="脱敏"):
        assert_redacted_json(raw)


def test_provider_attempt_rejects_inconsistent_unknown_and_not_sent_states() -> None:
    now = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    request = _request()
    unknown_error = ProviderErrorV1(
        category="unknown",
        code="network_result_unknown",
        safe_summary="发送后连接中断，结果未知",
        retryable=True,
    )

    with pytest.raises(ValidationError, match="unknown"):
        ProviderAttemptV1(
            attempt_id=uuid4(),
            provider_request_id=request.request_id,
            attempt_no=1,
            dispatch_status="unknown",
            dispatch_started_at=now,
            completed_at=now + timedelta(seconds=1),
            billing=ProviderBillingV1(status="not_billable"),
            potential_duplicate_charge=False,
            error=unknown_error,
            created_at=now,
        )

    with pytest.raises(ValidationError, match="not_sent"):
        ProviderAttemptV1(
            attempt_id=uuid4(),
            provider_request_id=request.request_id,
            attempt_no=1,
            dispatch_status="not_sent",
            dispatch_started_at=now,
            completed_at=now + timedelta(seconds=1),
            billing=ProviderBillingV1(status="not_billable"),
            error=ProviderErrorV1(
                category="transient",
                code="connect_failed",
                safe_summary="发送前连接失败",
                retryable=True,
            ),
            created_at=now,
        )


def test_raw_envelope_contract_is_provider_neutral_and_versioned() -> None:
    schema = RawEnvelopeV1.model_json_schema()

    assert RawEnvelopeV1.model_fields["schema_version"].default == "provider-response.v1"
    assert "provider" in schema["properties"]
    assert "operations" in schema["properties"]
    assert "operation" in schema["properties"]
    assert "tikhub" not in str(schema).lower()

    billing = ProviderBillingV1(
        status="confirmed",
        currency="CNY",
        unit="request",
        unit_price_snapshot=Decimal("0.100000"),
        estimated_cost=Decimal("0.100000"),
        actual_cost=Decimal("0.100000"),
    )
    assert billing.actual_cost == Decimal("0.100000")


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("request.v1.schema.json", ProviderRequestV1),
        ("attempt.v1.schema.json", ProviderAttemptV1),
        ("raw-envelope.v1.schema.json", RawEnvelopeV1),
    ],
)
def test_fixed_provider_schemas_match_pydantic_contract(filename: str, model: type) -> None:
    target = ROOT / "contracts" / "provider" / filename

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == model.model_json_schema()
