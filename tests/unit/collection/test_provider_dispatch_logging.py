"""Provider Dispatch 稳定结构化生命周期事件回归。"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.contracts.provider import (
    ProviderAttemptV1,
    ProviderRequestV1,
    terminal_attempt_with_raw,
)
from aima_ugc.modules.collection.provider_dispatch import (
    ProviderDispatchPreparation,
    ProviderDispatchService,
)
from aima_ugc.modules.collection.provider_persistence import ProviderAttemptRecord
from aima_ugc.modules.collection.providers import (
    CapturedRawArtifact,
    ProviderClient,
    ProviderDispatchResult,
    ProviderTransportFailure,
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactRecord


class _Persistence:
    def __init__(self, preparation: ProviderDispatchPreparation) -> None:
        self.preparation = preparation

    def start_dispatch(
        self,
        *,
        attempt_id: UUID,
        fence: JobExecutionFence,
    ) -> ProviderDispatchPreparation:
        assert attempt_id == self.preparation.attempt.id
        return self.preparation

    def finalize_dispatch(
        self,
        *,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
        fence: JobExecutionFence,
    ) -> ProviderAttemptRecord:
        return replace(
            self.preparation.attempt,
            dispatch_status=attempt.dispatch_status,
            completed_at=attempt.completed_at,
            http_status=attempt.http_status,
            external_request_id=attempt.external_request_id,
            raw_artifact_id=raw_artifact_id,
            billing_status=attempt.billing.status,
            estimated_cost=attempt.billing.estimated_cost,
            actual_cost=attempt.billing.actual_cost,
            error_code=attempt.error.code if attempt.error else None,
            error_detail=attempt.error.safe_summary if attempt.error else None,
        )


class _RawArtifacts:
    def __init__(self, artifact: ArtifactRecord) -> None:
        self.artifact = artifact

    def capture(
        self,
        *,
        request: ProviderRequestV1,
        dispatch: ProviderDispatchResult,
    ) -> CapturedRawArtifact:
        return CapturedRawArtifact(
            artifact=self.artifact,
            attempt=terminal_attempt_with_raw(dispatch.attempt, self.artifact.id),
            envelope=object(),  # type: ignore[arg-type]
        )


def _service(outcome: ProviderTransportResponse | ProviderTransportFailure):
    started_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    completed_at = started_at + timedelta(milliseconds=250)
    moments = iter([started_at, completed_at])
    job_id = uuid4()
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake_provider",
        platform="xhs",
        operation="keyword_search",
        request_params={"keyword": "敏感业务输入不应进入日志"},
    )
    attempt_id = uuid4()
    attempt = ProviderAttemptRecord(
        id=attempt_id,
        provider_request_id=request.request_id,
        attempt_no=1,
        dispatch_status="dispatching",
        dispatch_started_at=started_at,
        completed_at=None,
        http_status=None,
        external_request_id=None,
        raw_artifact_id=None,
        estimated_cost=Decimal("0"),
        actual_cost=Decimal("0"),
        cost_currency=None,
        cost_unit=None,
        unit_price_snapshot=Decimal("0"),
        billing_status="not_billable",
        potential_duplicate_charge=False,
        error_code=None,
        error_detail=None,
        created_at=started_at,
    )
    artifact = ArtifactRecord(
        id=uuid4(),
        kind="provider-raw",
        storage_backend="local",
        storage_key=f"raw/fake/{attempt_id}.json.gz",
        content_type="application/json",
        encoding="gzip",
        retention_class="raw",
        storage_status="stored",
        created_at=started_at,
        sha256="a" * 64,
        byte_size=1,
        stored_at=started_at,
    )
    service = ProviderDispatchService(
        persistence=_Persistence(
            ProviderDispatchPreparation(job_id=job_id, request=request, attempt=attempt)
        ),
        client=ProviderClient(
            transport=FakeProviderTransport([outcome]),
            clock=lambda: next(moments),
        ),
        raw_artifacts=_RawArtifacts(artifact),
    )
    return service, request, attempt_id, JobExecutionFence(job_id=job_id, lease_token="secret")


@pytest.mark.parametrize(
    ("outcome", "terminal_event", "terminal_status"),
    [
        (
            ProviderTransportResponse(
                status_code=200,
                body={"items": []},
                external_request_id="provider-request-1",
            ),
            "provider.request.completed",
            "completed",
        ),
        (
            ProviderTransportFailure.not_sent(
                code="connect_failed",
                safe_summary="连接建立前失败",
            ),
            "provider.request.failed",
            "not_sent",
        ),
        (
            ProviderTransportFailure.unknown(
                code="read_timeout",
                safe_summary="发送后结果未知",
            ),
            "provider.request.failed",
            "unknown",
        ),
    ],
)
def test_provider_dispatch_emits_safe_stable_lifecycle_events(
    caplog: pytest.LogCaptureFixture,
    outcome: ProviderTransportResponse | ProviderTransportFailure,
    terminal_event: str,
    terminal_status: str,
) -> None:
    service, request, attempt_id, fence = _service(outcome)

    with caplog.at_level(logging.INFO, logger="aima_ugc.modules.collection.provider_dispatch"):
        service.dispatch(
            attempt_id=attempt_id,
            fence=fence,
            transport_request=ProviderTransportRequest(
                transport_kind="http",
                method="GET",
                path="/fake/search",
            ),
        )

    records = [record for record in caplog.records if hasattr(record, "event")]
    assert [record.event for record in records] == ["provider.request.started", terminal_event]
    started, terminal = records
    assert started.provider_request_id == str(request.request_id)
    assert started.provider_attempt_id == str(attempt_id)
    assert started.run_id == str(request.run_id)
    assert started.scope_id == str(request.scope_id)
    assert started.platform == "xhs"
    assert started.operation == "keyword_search"
    assert terminal.status == terminal_status
    assert terminal.provider_attempt_id == str(attempt_id)
    for record in records:
        assert "request_params" not in record.__dict__
        assert "transport_request" not in record.__dict__
        assert "body" not in record.__dict__
        assert "lease_token" not in record.__dict__
