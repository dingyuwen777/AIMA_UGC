"""Provider Dispatch 各阶段的 PostgreSQL 短事务编排。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from aima_ugc.contracts.provider import ProviderAttemptV1
from aima_ugc.modules.collection.provider_budget import (
    ProviderBudgetService,
    completed_budget_settlement_amount,
)
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchPreparation
from aima_ugc.modules.collection.provider_persistence import (
    ProviderAttemptRecord,
    ProviderRequestNotFoundError,
)
from aima_ugc.modules.collection.provider_recovery import ProviderRecoveryCandidate
from aima_ugc.modules.collection.providers import raw_storage_key
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table

from .artifact_metadata import PostgresArtifactMetadataRepository
from .jobs import PostgresJobRepository
from .provider import PostgresProviderRepository
from .provider_budget import PostgresProviderBudgetRepository


class PostgresProviderDispatchPersistence:
    """Fencing、Budget 与 Collection/Artifact Owner 终态事务入口。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def start_dispatch(
        self,
        *,
        attempt_id: UUID,
        fence: JobExecutionFence,
    ) -> ProviderDispatchPreparation:
        session = self._session_factory()
        try:
            with session.begin():
                provider = PostgresProviderRepository(session)
                preparation = provider.load_dispatch_preparation(attempt_id)
                if preparation is None:
                    raise ProviderRequestNotFoundError(f"Provider Attempt 不存在: {attempt_id}")
                _lock_matching_job(session, preparation=preparation, fence=fence)
                ProviderBudgetService(
                    PostgresProviderBudgetRepository(session)
                ).assert_dispatch_ready(attempt_id)
                dispatching = provider.mark_dispatching(attempt_id)
                return ProviderDispatchPreparation(
                    job_id=preparation.job_id,
                    request=preparation.request,
                    attempt=dispatching,
                )
        finally:
            session.close()

    def finalize_dispatch(
        self,
        *,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
        fence: JobExecutionFence,
    ) -> ProviderAttemptRecord:
        session = self._session_factory()
        try:
            with session.begin():
                provider = PostgresProviderRepository(session)
                preparation = provider.load_dispatch_preparation(attempt.attempt_id)
                if preparation is None:
                    raise ProviderRequestNotFoundError(
                        f"Provider Attempt 不存在: {attempt.attempt_id}"
                    )
                _lock_matching_job(session, preparation=preparation, fence=fence)
                return _finalize_provider_and_artifact(
                    session,
                    provider=provider,
                    attempt=attempt,
                    raw_artifact_id=raw_artifact_id,
                )
        finally:
            session.close()


class PostgresProviderRecoveryPersistence:
    """Reconciler 使用的候选查找与二次 Fencing 提交边界。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def find_inherited(
        self,
        fence: JobExecutionFence,
    ) -> ProviderRecoveryCandidate | None:
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                attempt_id = session.scalar(
                    _dispatching_attempt_ids().where(collection_runs_table.c.job_id == fence.job_id)
                )
                return (
                    _load_recovery_candidate(session, attempt_id)
                    if attempt_id is not None
                    else None
                )
        finally:
            session.close()

    def find_orphaned(self) -> ProviderRecoveryCandidate | None:
        session = self._session_factory()
        try:
            with session.begin():
                now = func.clock_timestamp()
                attempt_id = session.scalar(
                    _dispatching_attempt_ids()
                    .join(jobs_table, collection_runs_table.c.job_id == jobs_table.c.id)
                    .where(
                        or_(
                            jobs_table.c.status != "running",
                            jobs_table.c.lease_expires_at <= now,
                            jobs_table.c.attempt_deadline_at <= now,
                        )
                    )
                )
                return (
                    _load_recovery_candidate(session, attempt_id)
                    if attempt_id is not None
                    else None
                )
        finally:
            session.close()

    def finalize_inherited(
        self,
        *,
        candidate: ProviderRecoveryCandidate,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
        fence: JobExecutionFence,
    ) -> ProviderAttemptRecord:
        session = self._session_factory()
        try:
            with session.begin():
                provider = PostgresProviderRepository(session)
                preparation = _require_preparation(provider, candidate.attempt.id)
                _lock_matching_job(session, preparation=preparation, fence=fence)
                return _finalize_provider_and_artifact(
                    session,
                    provider=provider,
                    attempt=attempt,
                    raw_artifact_id=raw_artifact_id,
                )
        finally:
            session.close()

    def finalize_orphaned(
        self,
        *,
        candidate: ProviderRecoveryCandidate,
        attempt: ProviderAttemptV1,
        raw_artifact_id: UUID | None,
    ) -> ProviderAttemptRecord:
        session = self._session_factory()
        try:
            with session.begin():
                provider = PostgresProviderRepository(session)
                preparation = _require_preparation(provider, candidate.attempt.id)
                if preparation.job_id != candidate.job_id:
                    raise LeaseLostError("Provider Recovery 的 Job 来源已改变")
                if PostgresJobRepository(session).lock_expired_execution(candidate.job_id) is None:
                    raise LeaseLostError("Provider Recovery 期间 Job 已由有效 Token 接管")
                return _finalize_provider_and_artifact(
                    session,
                    provider=provider,
                    attempt=attempt,
                    raw_artifact_id=raw_artifact_id,
                )
        finally:
            session.close()


def _lock_matching_job(
    session: Session,
    *,
    preparation: ProviderDispatchPreparation,
    fence: JobExecutionFence,
) -> None:
    if preparation.job_id != fence.job_id:
        raise LeaseLostError("Provider Attempt 不属于当前 Job Fence")
    PostgresJobRepository(session).lock_current_execution(fence)


def _dispatching_attempt_ids() -> Select[tuple[UUID]]:
    return (
        select(provider_request_attempts_table.c.id)
        .select_from(
            provider_request_attempts_table.join(
                provider_requests_table,
                provider_request_attempts_table.c.provider_request_id
                == provider_requests_table.c.id,
            )
            .join(
                collection_scopes_table,
                provider_requests_table.c.scope_id == collection_scopes_table.c.id,
            )
            .join(
                collection_runs_table,
                collection_scopes_table.c.run_id == collection_runs_table.c.id,
            )
        )
        .where(provider_request_attempts_table.c.dispatch_status == "dispatching")
        .order_by(
            provider_request_attempts_table.c.dispatch_started_at,
            provider_request_attempts_table.c.id,
        )
        .limit(1)
    )


def _load_recovery_candidate(
    session: Session,
    attempt_id: UUID,
) -> ProviderRecoveryCandidate:
    provider = PostgresProviderRepository(session)
    preparation = _require_preparation(provider, attempt_id)
    started_at = preparation.attempt.dispatch_started_at
    artifact = None
    if started_at is not None:
        artifact = PostgresArtifactMetadataRepository(session).get_by_storage_key(
            raw_storage_key(
                request=preparation.request,
                dispatch_started_at=started_at,
                attempt_id=attempt_id,
            )
        )
    return ProviderRecoveryCandidate(
        job_id=preparation.job_id,
        request=preparation.request,
        attempt=preparation.attempt,
        artifact=artifact,
    )


def _require_preparation(
    provider: PostgresProviderRepository,
    attempt_id: UUID,
) -> ProviderDispatchPreparation:
    preparation = provider.load_dispatch_preparation(attempt_id)
    if preparation is None:
        raise ProviderRequestNotFoundError(f"Provider Attempt 不存在: {attempt_id}")
    return preparation


def _finalize_provider_and_artifact(
    session: Session,
    *,
    provider: PostgresProviderRepository,
    attempt: ProviderAttemptV1,
    raw_artifact_id: UUID | None,
) -> ProviderAttemptRecord:
    budget_status: Literal["completed", "not_sent", "unknown"]
    if attempt.dispatch_status == "completed":
        budget_status = "completed"
    elif attempt.dispatch_status == "not_sent":
        budget_status = "not_sent"
    elif attempt.dispatch_status == "unknown":
        budget_status = "unknown"
    else:
        raise ValueError("Provider Dispatch 终态无效")

    persisted = provider.finalize_dispatch(
        attempt=attempt,
        raw_artifact_id=raw_artifact_id,
    )
    budget_settlement_cost = attempt.billing.actual_cost
    if budget_status == "completed" and attempt.billing.status != "not_billable":
        if attempt.billing.currency is None:
            raise ValueError("completed 计费 Attempt 缺少 currency")
        budget_settlement_cost = completed_budget_settlement_amount(
            dimension="monetary_cost",
            reserved_amount=attempt.billing.estimated_cost,
            billing_status=attempt.billing.status,
            actual_cost=attempt.billing.actual_cost,
            billing_currency=attempt.billing.currency,
            account_unit=attempt.billing.currency,
        )
    ProviderBudgetService(PostgresProviderBudgetRepository(session)).finalize_attempt(
        provider_request_attempt_id=attempt.attempt_id,
        dispatch_status=budget_status,
        actual_cost=budget_settlement_cost,
        currency=attempt.billing.currency,
    )
    if raw_artifact_id is not None:
        if attempt.completed_at is None:
            raise ValueError("Raw Artifact 关联要求 Attempt 已完成")
        PostgresArtifactMetadataRepository(session).mark_linked(
            raw_artifact_id,
            linked_at=attempt.completed_at,
        )
    return persisted
