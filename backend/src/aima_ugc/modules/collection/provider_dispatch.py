"""Provider Attempt 的 Fencing、一次执行与 Raw 终态编排。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactRecord

from .provider_persistence import ProviderAttemptRecord
from .providers import (
    CapturedRawArtifact,
    ProviderClient,
    ProviderDispatchResult,
    ProviderTransportRequest,
)


@dataclass(frozen=True, slots=True)
class ProviderDispatchPreparation:
    """Dispatch CAS 提交后的数据库事实。"""

    job_id: UUID
    request: ProviderRequestV1
    attempt: ProviderAttemptRecord


@dataclass(frozen=True, slots=True)
class ProviderDispatchOutcome:
    """Provider 执行已持久化的终态结果。"""

    attempt: ProviderAttemptRecord
    artifact: ArtifactRecord | None


class ProviderDispatchPersistence(Protocol):
    """Dispatch 各短事务的持久化边界。"""

    def start_dispatch(
        self,
        *,
        attempt_id: UUID,
        fence: JobExecutionFence,
    ) -> ProviderDispatchPreparation: ...

    def finalize_dispatch(
        self,
        *,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
        fence: JobExecutionFence,
    ) -> ProviderAttemptRecord: ...


class ProviderAttemptStateConflict(RuntimeError):
    """Attempt 当前状态不允许所请求的 CAS 转换。"""


class RawArtifactCapture(Protocol):
    """Raw 落盘与完整性边界。"""

    def capture(
        self,
        *,
        request: ProviderRequestV1,
        dispatch: ProviderDispatchResult,
    ) -> CapturedRawArtifact: ...


def _planned_billing_from_record(attempt: ProviderAttemptRecord) -> ProviderBillingV1:
    if attempt.billing_status == "not_billable":
        return ProviderBillingV1(status="not_billable")
    if attempt.billing_status != "estimated":
        raise ValueError("dispatching Attempt 的 Billing 必须为 not_billable 或 estimated")
    if attempt.cost_currency is None:
        raise ValueError("estimated Attempt 缺少 cost_currency")
    return ProviderBillingV1(
        status="estimated",
        currency=attempt.cost_currency,
        unit=attempt.cost_unit,
        unit_price_snapshot=attempt.unit_price_snapshot or Decimal("0"),
        estimated_cost=attempt.estimated_cost,
        actual_cost=Decimal("0"),
    )


class ProviderDispatchService:
    """CAS 后执行一次 Provider Client，再提交 Raw 终态。"""

    def __init__(
        self,
        *,
        persistence: ProviderDispatchPersistence,
        client: ProviderClient,
        raw_artifacts: RawArtifactCapture,
    ) -> None:
        self._persistence = persistence
        self._client = client
        self._raw_artifacts = raw_artifacts

    def dispatch(
        self,
        *,
        attempt_id: UUID,
        fence: JobExecutionFence,
        transport_request: ProviderTransportRequest,
    ) -> ProviderDispatchOutcome:
        """Dispatch 一个 Attempt；任意重发都必须由调用方创建新 Attempt。"""
        preparation = self._persistence.start_dispatch(attempt_id=attempt_id, fence=fence)
        if preparation.attempt.dispatch_started_at is None:
            raise ValueError("dispatching Attempt 缺少 dispatch_started_at")
        dispatch = self._client.dispatch(
            request=preparation.request,
            attempt_id=preparation.attempt.id,
            attempt_no=preparation.attempt.attempt_no,
            transport_request=transport_request,
            dispatch_started_at=preparation.attempt.dispatch_started_at,
            planned_billing=_planned_billing_from_record(preparation.attempt),
        )
        if dispatch.attempt.dispatch_status == "not_sent":
            persisted = self._persistence.finalize_dispatch(
                attempt=dispatch.attempt,
                raw_artifact_id=None,
                fence=fence,
            )
            return ProviderDispatchOutcome(attempt=persisted, artifact=None)

        captured = self._raw_artifacts.capture(
            request=preparation.request,
            dispatch=dispatch,
        )
        persisted = self._persistence.finalize_dispatch(
            attempt=captured.attempt,
            raw_artifact_id=captured.artifact.id,
            fence=fence,
        )
        return ProviderDispatchOutcome(attempt=persisted, artifact=captured.artifact)
