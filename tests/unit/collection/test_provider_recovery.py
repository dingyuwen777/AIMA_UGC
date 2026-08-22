"""Provider Attempt Reconciler 的 Raw 优先恢复语义。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from aima_ugc.contracts.provider import (
    ProviderBillingV1,
    ProviderRequestV1,
    RawEnvelopeV1,
    RawRequestV1,
    RawResponseV1,
)
from aima_ugc.modules.collection.provider_persistence import ProviderAttemptRecord
from aima_ugc.modules.collection.provider_recovery import (
    ProviderAttemptReconciler,
    ProviderRecoveryCandidate,
)
from aima_ugc.modules.collection.providers import RawArtifactIntegrityError
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactRecord


class FakeRecoveryPersistence:
    def __init__(self, candidate: ProviderRecoveryCandidate) -> None:
        self.candidate = candidate
        self.inherited_available = True
        self.orphaned_available = True
        self.finalized = []

    def find_inherited(self, fence: JobExecutionFence):
        if not self.inherited_available:
            return None
        self.inherited_available = False
        return self.candidate

    def find_orphaned(self):
        if not self.orphaned_available:
            return None
        self.orphaned_available = False
        return self.candidate

    def finalize_inherited(self, **kwargs):
        self.finalized.append(kwargs)
        return self.candidate.attempt

    def finalize_orphaned(self, **kwargs):
        self.finalized.append(kwargs)
        return self.candidate.attempt


class FakeRawReplay:
    def __init__(self, envelope: RawEnvelopeV1) -> None:
        self.envelope = envelope
        self.count = 0

    def replay(self, artifact: ArtifactRecord) -> RawEnvelopeV1:
        self.count += 1
        return self.envelope


class CorruptRawReplay:
    def replay(self, artifact: ArtifactRecord) -> RawEnvelopeV1:
        raise RawArtifactIntegrityError("Raw SHA-256 校验失败")


def _candidate(*, with_artifact: bool):
    started_at = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake_provider",
        platform="xiaohongshu",
        operation="keyword_search",
        request_params={"keyword": "爱玛"},
    )
    attempt = ProviderAttemptRecord(
        id=uuid4(),
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
    artifact = (
        ArtifactRecord(
            id=uuid4(),
            kind="provider-raw",
            storage_backend="local",
            storage_key=f"raw/fake/{attempt.id}.json.gz",
            content_type="application/json",
            encoding="gzip",
            retention_class="raw",
            storage_status="stored",
            created_at=started_at,
            sha256="a" * 64,
            byte_size=1,
            stored_at=started_at,
        )
        if with_artifact
        else None
    )
    candidate = ProviderRecoveryCandidate(
        job_id=uuid4(),
        request=request,
        attempt=attempt,
        artifact=artifact,
    )
    envelope = RawEnvelopeV1(
        provider=request.provider,
        platform=request.platform,
        operation=request.operation,
        request_id=request.request_id,
        attempt_id=attempt.id,
        run_id=request.run_id,
        scope_id=request.scope_id,
        requested_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        dispatch_status="completed",
        request=RawRequestV1(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
        response=RawResponseV1(status_code=200, body={"items": []}),
        billing=ProviderBillingV1(status="not_billable"),
    )
    return candidate, envelope


def test_inherited_attempt_recovers_verified_raw_without_unknown() -> None:
    candidate, envelope = _candidate(with_artifact=True)
    persistence = FakeRecoveryPersistence(candidate)
    raw = FakeRawReplay(envelope)
    fence = JobExecutionFence(job_id=candidate.job_id, lease_token="new-token")

    recovered = ProviderAttemptReconciler(
        persistence=persistence,
        raw_artifacts=raw,
    ).recover_inherited(fence)

    assert recovered == 1
    assert raw.count == 1
    finalized = persistence.finalized[0]
    assert finalized["attempt"].dispatch_status == "completed"
    assert finalized["raw_artifact_id"] == candidate.artifact.id


def test_orphaned_attempt_without_raw_becomes_unknown() -> None:
    candidate, envelope = _candidate(with_artifact=False)
    persistence = FakeRecoveryPersistence(candidate)

    reconciled = ProviderAttemptReconciler(
        persistence=persistence,
        raw_artifacts=FakeRawReplay(envelope),
        clock=lambda: candidate.attempt.dispatch_started_at + timedelta(seconds=5),
    ).reap_once()

    assert reconciled is True
    finalized = persistence.finalized[0]
    assert finalized["attempt"].dispatch_status == "unknown"
    assert finalized["attempt"].billing.status == "unknown"
    assert finalized["attempt"].potential_duplicate_charge is True
    assert finalized["raw_artifact_id"] is None


def test_orphaned_attempt_with_corrupt_raw_logs_reason_and_becomes_unknown(caplog) -> None:
    candidate, _ = _candidate(with_artifact=True)
    persistence = FakeRecoveryPersistence(candidate)

    with caplog.at_level("WARNING"):
        ProviderAttemptReconciler(
            persistence=persistence,
            raw_artifacts=CorruptRawReplay(),
            clock=lambda: candidate.attempt.dispatch_started_at + timedelta(seconds=5),
        ).reap_once()

    finalized = persistence.finalized[0]
    assert finalized["attempt"].dispatch_status == "unknown"
    assert finalized["raw_artifact_id"] is None
    assert candidate.artifact.storage_status == "stored"
    assert "provider_raw_recovery_rejected" in caplog.text
    assert "Raw SHA-256 校验失败" in caplog.text
    assert str(candidate.attempt.id) in caplog.text
    assert str(candidate.artifact.id) in caplog.text
