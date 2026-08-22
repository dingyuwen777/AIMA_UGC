"""Provider Dispatch Service 的一次执行语义。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.contracts.provider import (
    ProviderAttemptV1,
    ProviderRequestV1,
    terminal_attempt_with_raw,
)
from aima_ugc.modules.collection.provider_dispatch import (
    ProviderDispatchOutcome,
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


def _attempt(
    *,
    attempt_id: UUID,
    request_id: UUID,
    dispatch_status: str,
    created_at: datetime,
) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        id=attempt_id,
        provider_request_id=request_id,
        attempt_no=1,
        dispatch_status=dispatch_status,
        dispatch_started_at=created_at if dispatch_status == "dispatching" else None,
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
        created_at=created_at,
    )


class FakeDispatchPersistence:
    def __init__(self, preparation: ProviderDispatchPreparation) -> None:
        self.preparation = preparation
        self.finalized: list[tuple[UUID, UUID | None, str]] = []

    def start_dispatch(
        self,
        *,
        attempt_id: UUID,
        fence: JobExecutionFence,
    ) -> ProviderDispatchPreparation:
        assert attempt_id == self.preparation.attempt.id
        assert fence.job_id == self.preparation.job_id
        return self.preparation

    def finalize_dispatch(
        self,
        *,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
        fence: JobExecutionFence,
    ) -> ProviderAttemptRecord:
        terminal = self.preparation.attempt
        dispatch_status = attempt.dispatch_status
        self.finalized.append((attempt.attempt_id, raw_artifact_id, dispatch_status))
        return replace(
            terminal,
            dispatch_status=dispatch_status,
            completed_at=attempt.completed_at,
            raw_artifact_id=raw_artifact_id,
            billing_status=attempt.billing.status,
            error_code=attempt.error.code if attempt.error is not None else None,
            error_detail=(attempt.error.safe_summary if attempt.error is not None else None),
        )


class FakeRawArtifacts:
    def __init__(self, artifact: ArtifactRecord) -> None:
        self.artifact = artifact
        self.capture_count = 0

    def capture(
        self,
        *,
        request: ProviderRequestV1,
        dispatch: ProviderDispatchResult,
    ) -> CapturedRawArtifact:
        self.capture_count += 1
        return CapturedRawArtifact(
            artifact=self.artifact,
            attempt=terminal_attempt_with_raw(dispatch.attempt, self.artifact.id),
            envelope=object(),  # type: ignore[arg-type]
        )


def _fixture(
    outcomes: list[ProviderTransportResponse | ProviderTransportFailure],
) -> tuple[
    ProviderDispatchService,
    FakeProviderTransport,
    FakeDispatchPersistence,
    FakeRawArtifacts,
    JobExecutionFence,
    UUID,
]:
    started_at = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
    completed_at = started_at + timedelta(seconds=1)
    moments = iter([started_at, completed_at])
    job_id = uuid4()
    run_id = uuid4()
    scope_id = uuid4()
    attempt_id = uuid4()
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=run_id,
        scope_id=scope_id,
        provider="fake_provider",
        platform="xiaohongshu",
        operation="keyword_search",
        request_params={"keyword": "爱玛"},
    )
    preparation = ProviderDispatchPreparation(
        job_id=job_id,
        request=request,
        attempt=_attempt(
            attempt_id=attempt_id,
            request_id=request.request_id,
            dispatch_status="dispatching",
            created_at=started_at,
        ),
    )
    persistence = FakeDispatchPersistence(preparation)
    transport = FakeProviderTransport(outcomes)
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
    raw_artifacts = FakeRawArtifacts(artifact)
    service = ProviderDispatchService(
        persistence=persistence,
        client=ProviderClient(transport=transport, clock=lambda: next(moments)),
        raw_artifacts=raw_artifacts,
    )
    return (
        service,
        transport,
        persistence,
        raw_artifacts,
        JobExecutionFence(job_id=job_id, lease_token="current-token"),
        attempt_id,
    )


def test_dispatch_captures_raw_and_finalizes_once() -> None:
    service, transport, persistence, raw_artifacts, fence, attempt_id = _fixture(
        [ProviderTransportResponse(status_code=200, body={"items": []})]
    )

    outcome = service.dispatch(
        attempt_id=attempt_id,
        fence=fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    assert isinstance(outcome, ProviderDispatchOutcome)
    assert outcome.attempt.dispatch_status == "completed"
    assert outcome.artifact is not None
    assert transport.call_count == 1
    assert raw_artifacts.capture_count == 1
    assert persistence.finalized == [(attempt_id, outcome.artifact.id, "completed")]


def test_definitive_not_sent_does_not_create_raw() -> None:
    service, transport, persistence, raw_artifacts, fence, attempt_id = _fixture(
        [
            ProviderTransportFailure.not_sent(
                code="connect_failed",
                safe_summary="连接建立前失败",
            )
        ]
    )

    outcome = service.dispatch(
        attempt_id=attempt_id,
        fence=fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    assert outcome.attempt.dispatch_status == "not_sent"
    assert outcome.artifact is None
    assert transport.call_count == 1
    assert raw_artifacts.capture_count == 0
    assert persistence.finalized == [(attempt_id, None, "not_sent")]


def test_job_execution_fence_repr_hides_lease_token() -> None:
    fence = JobExecutionFence(job_id=uuid4(), lease_token="secret-lease-token")

    assert "secret-lease-token" not in repr(fence)
