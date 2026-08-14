"""Provider Client 与 Fake Transport 的一次发送行为。"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportFailure,
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from pydantic import SecretStr, ValidationError


def _clock(*values: datetime):
    moments: Iterator[datetime] = iter(values)
    return lambda: next(moments)


def _request() -> ProviderRequestV1:
    return ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake_provider",
        platform="xhs",
        operation="keyword_search",
        request_params={"keyword": "爱玛"},
        pagination_input={"page": 1},
    )


def _transport_request(token: str = "stage5a-test-token") -> ProviderTransportRequest:
    return ProviderTransportRequest(
        transport_kind="http",
        method="GET",
        path="/fake/search",
        params={"keyword": "爱玛"},
        credential=SecretStr(token),
    )


def test_provider_client_success_calls_transport_once_without_persisting_token() -> None:
    started = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    finished = started + timedelta(milliseconds=50)
    billing = ProviderBillingV1(
        status="confirmed",
        currency="CNY",
        unit="request",
        unit_price_snapshot=Decimal("0.1"),
        estimated_cost=Decimal("0.1"),
        actual_cost=Decimal("0.1"),
    )
    transport = FakeProviderTransport(
        [
            ProviderTransportResponse(
                status_code=200,
                external_request_id="fake-request-1",
                body={"items": [{"id": "note-1"}]},
                billing=billing,
            )
        ]
    )
    client = ProviderClient(transport=transport, clock=_clock(started, finished))
    transport_request = _transport_request()

    result = client.dispatch(
        request=_request(),
        attempt_id=uuid4(),
        attempt_no=1,
        transport_request=transport_request,
    )

    assert transport.call_count == 1
    assert result.attempt.dispatch_status == "completed"
    assert result.attempt.http_status == 200
    assert result.attempt.error is None
    assert result.attempt.billing == billing
    assert result.raw_response is not None
    assert result.raw_response.body == {"items": [{"id": "note-1"}]}
    assert "stage5a-test-token" not in transport_request.model_dump_json()
    assert "stage5a-test-token" not in repr(transport.seen_requests)

    with pytest.raises(ValidationError, match="脱敏"):
        ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search?api_key=stage5a-test-token",
        )


@pytest.mark.parametrize(
    ("status_code", "category", "retryable"),
    [(429, "rate_limited", True), (503, "transient", True), (400, "permanent", False)],
)
def test_provider_client_classifies_definitive_http_errors(
    status_code: int,
    category: str,
    retryable: bool,
) -> None:
    started = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    transport = FakeProviderTransport(
        [ProviderTransportResponse(status_code=status_code, body={"message": "safe"})]
    )
    client = ProviderClient(
        transport=transport,
        clock=_clock(started, started + timedelta(seconds=1)),
    )

    result = client.dispatch(
        request=_request(),
        attempt_id=uuid4(),
        attempt_no=1,
        transport_request=_transport_request(),
    )

    assert transport.call_count == 1
    assert result.attempt.dispatch_status == "completed"
    assert result.attempt.error is not None
    assert result.attempt.error.category == category
    assert result.attempt.error.retryable is retryable


@pytest.mark.parametrize(
    ("failure", "status", "duplicate", "billing_status"),
    [
        (
            ProviderTransportFailure.not_sent(
                code="connect_failed",
                safe_summary="发送前连接失败",
            ),
            "not_sent",
            False,
            "not_billable",
        ),
        (
            ProviderTransportFailure.unknown(
                code="network_result_unknown",
                safe_summary="发送后连接中断",
            ),
            "unknown",
            True,
            "unknown",
        ),
    ],
)
def test_provider_client_preserves_transport_failure_boundary(
    failure: ProviderTransportFailure,
    status: str,
    duplicate: bool,
    billing_status: str,
) -> None:
    started = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    transport = FakeProviderTransport([failure])
    client = ProviderClient(
        transport=transport,
        clock=_clock(started, started + timedelta(seconds=1)),
    )

    result = client.dispatch(
        request=_request(),
        attempt_id=uuid4(),
        attempt_no=1,
        transport_request=_transport_request(),
    )

    assert transport.call_count == 1
    assert result.attempt.dispatch_status == status
    assert result.attempt.potential_duplicate_charge is duplicate
    assert result.attempt.billing.status == billing_status
    assert result.attempt.error is not None
    assert result.attempt.error.code == failure.code
    if status == "not_sent":
        assert result.attempt.dispatch_started_at is None
    else:
        assert result.attempt.dispatch_started_at == started
