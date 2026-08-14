"""Provider `dispatching` Attempt 的 Raw 优先崩溃恢复。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.provider import (
    ProviderAttemptV1,
    ProviderBillingV1,
    ProviderErrorV1,
    ProviderRequestV1,
    RawEnvelopeV1,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactRecord

from .provider_persistence import ProviderAttemptRecord
from .providers import RawArtifactIntegrityError


@dataclass(frozen=True, slots=True)
class ProviderRecoveryCandidate:
    """Reconciler 在数据库中发现的遗留 dispatching Attempt。"""

    job_id: UUID
    request: ProviderRequestV1
    attempt: ProviderAttemptRecord
    artifact: ArtifactRecord | None


class ProviderRecoveryPersistence(Protocol):
    """Reconciler 查找和提交的 PostgreSQL 短事务边界。"""

    def find_inherited(
        self,
        fence: JobExecutionFence,
    ) -> ProviderRecoveryCandidate | None: ...

    def find_orphaned(self) -> ProviderRecoveryCandidate | None: ...

    def finalize_inherited(
        self,
        *,
        candidate: ProviderRecoveryCandidate,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
        fence: JobExecutionFence,
    ) -> ProviderAttemptRecord: ...

    def finalize_orphaned(
        self,
        *,
        candidate: ProviderRecoveryCandidate,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
    ) -> ProviderAttemptRecord: ...


class RawArtifactReplay(Protocol):
    """Reconciler 只读校验 Raw 的边界。"""

    def replay(self, artifact: ArtifactRecord) -> RawEnvelopeV1: ...


class ProviderAttemptReconciler:
    """Raw 完整时恢复原终态，否则保守收敛为 unknown。"""

    def __init__(
        self,
        *,
        persistence: ProviderRecoveryPersistence,
        raw_artifacts: RawArtifactReplay,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._persistence = persistence
        self._raw_artifacts = raw_artifacts
        self._clock = clock or (lambda: datetime.now(UTC))

    def recover_inherited(self, fence: JobExecutionFence) -> int:
        """新 Worker Token 在进入 Handler 时收敛上一 Token 留下的 Attempt。"""
        recovered = 0
        while candidate := self._persistence.find_inherited(fence):
            terminal, raw_artifact_id = self._resolve(candidate)
            self._persistence.finalize_inherited(
                candidate=candidate,
                attempt=terminal,
                raw_artifact_id=raw_artifact_id,
                fence=fence,
            )
            recovered += 1
        return recovered

    def reap_once(self) -> bool:
        """收敛一个 Job 租约已失效或已终态的遗留 Attempt。"""
        candidate = self._persistence.find_orphaned()
        if candidate is None:
            return False
        terminal, raw_artifact_id = self._resolve(candidate)
        self._persistence.finalize_orphaned(
            candidate=candidate,
            attempt=terminal,
            raw_artifact_id=raw_artifact_id,
        )
        return True

    def _resolve(
        self,
        candidate: ProviderRecoveryCandidate,
    ) -> tuple[ProviderAttemptV1, UUID | None]:
        if candidate.artifact is not None:
            try:
                envelope = self._raw_artifacts.replay(candidate.artifact)
                return (
                    _attempt_from_envelope(candidate, envelope),
                    candidate.artifact.id,
                )
            except RawArtifactIntegrityError:
                pass
        return _unknown_attempt(candidate.attempt, completed_at=self._clock()), None


def _attempt_from_envelope(
    candidate: ProviderRecoveryCandidate,
    envelope: RawEnvelopeV1,
) -> ProviderAttemptV1:
    request = candidate.request
    attempt = candidate.attempt
    lineage = (
        envelope.provider,
        envelope.platform,
        envelope.operation,
        envelope.request_id,
        envelope.attempt_id,
        envelope.run_id,
        envelope.scope_id,
    )
    expected = (
        request.provider,
        request.platform,
        request.operation,
        request.request_id,
        attempt.id,
        request.run_id,
        request.scope_id,
    )
    if lineage != expected:
        raise RawArtifactIntegrityError("Raw Envelope 与 Provider Attempt 来源不一致")
    response = envelope.response
    return ProviderAttemptV1(
        attempt_id=attempt.id,
        provider_request_id=attempt.provider_request_id,
        attempt_no=attempt.attempt_no,
        dispatch_status=envelope.dispatch_status,
        dispatch_started_at=envelope.requested_at,
        completed_at=envelope.completed_at,
        http_status=response.status_code if response is not None else None,
        external_request_id=(response.external_request_id if response is not None else None),
        raw_artifact_id=candidate.artifact.id if candidate.artifact is not None else None,
        billing=envelope.billing,
        potential_duplicate_charge=envelope.dispatch_status == "unknown",
        error=envelope.error,
        created_at=attempt.created_at,
    )


def _unknown_attempt(
    attempt: ProviderAttemptRecord,
    *,
    completed_at: datetime,
) -> ProviderAttemptV1:
    if attempt.dispatch_started_at is None:
        raise ValueError("dispatching Attempt 缺少 dispatch_started_at")
    safe_completed_at = max(completed_at, attempt.dispatch_started_at, attempt.created_at)
    return ProviderAttemptV1(
        attempt_id=attempt.id,
        provider_request_id=attempt.provider_request_id,
        attempt_no=attempt.attempt_no,
        dispatch_status="unknown",
        dispatch_started_at=attempt.dispatch_started_at,
        completed_at=safe_completed_at,
        billing=ProviderBillingV1(
            status="unknown",
            currency=attempt.cost_currency,
            unit=attempt.cost_unit,
            unit_price_snapshot=attempt.unit_price_snapshot or Decimal("0"),
            estimated_cost=attempt.estimated_cost,
            actual_cost=attempt.actual_cost,
        ),
        potential_duplicate_charge=True,
        error=ProviderErrorV1(
            category="unknown",
            code="dispatch_recovery_unknown",
            safe_summary="Provider 执行结果在崩溃恢复时无法确定",
            retryable=True,
        ),
        created_at=attempt.created_at,
    )
