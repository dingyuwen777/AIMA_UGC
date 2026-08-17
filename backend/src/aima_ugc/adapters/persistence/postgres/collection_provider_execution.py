"""Collection live runtime 的 Fenced Provider Request/Attempt 准备与 Scope 执行事实读取。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.candidate_tables import collection_candidates_table
from aima_ugc.modules.collection.provider_persistence import (
    PreparedProviderAttempt,
    ProviderPersistenceConflictError,
    ProviderPersistenceService,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .jobs import PostgresJobRepository
from .provider import PostgresProviderRepository


@dataclass(frozen=True, slots=True)
class CollectionScopeExecutionCounts:
    """由 Provider Attempt/Candidate durable 事实聚合的 Scope 计数。"""

    requested_count: int
    succeeded_count: int
    failed_count: int
    content_count: int
    comment_count: int


class PostgresFencedProviderAttemptPreparer:
    """在任何 Provider Request/Attempt 写入前验证当前 Job Fence 与 Scope 归属。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def prepare_billable_attempt(
        self,
        *,
        request: ProviderRequestV1,
        provider_config_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
        fence: JobExecutionFence,
    ) -> PreparedProviderAttempt:
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                self._require_request_scope(session, request=request, fence=fence)
                return ProviderPersistenceService(
                    PostgresProviderRepository(session)
                ).prepare_billable_attempt(
                    request=request,
                    provider_config_id=provider_config_id,
                    attempt_id=attempt_id,
                    billing=billing,
                )
        finally:
            session.close()

    def resolve_or_prepare_billable_attempt(
        self,
        *,
        request: ProviderRequestV1,
        provider_config_id: UUID,
        attempt_id: UUID,
        billing: ProviderBillingV1,
        fence: JobExecutionFence,
    ) -> PreparedProviderAttempt:
        """恢复时复用同一逻辑 Request 的成功 Raw 或尚未发送的 reserved Attempt。"""
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                self._require_request_scope(session, request=request, fence=fence)

                repository = PostgresProviderRepository(session)
                service = ProviderPersistenceService(repository)
                persisted_request = service.ensure_request(
                    request,
                    provider_config_id=provider_config_id,
                )
                attempts = repository.list_attempts(persisted_request.id)
                dispatching_attempts = [
                    attempt for attempt in attempts if attempt.dispatch_status == "dispatching"
                ]
                if dispatching_attempts:
                    raise ProviderPersistenceConflictError(
                        "同一 Provider Request 存在未收敛的 dispatching Attempt，"
                        "必须先执行 Recovery"
                    )

                successful_attempts = [
                    attempt
                    for attempt in attempts
                    if attempt.dispatch_status == "completed"
                    and attempt.error_code is None
                    and attempt.raw_artifact_id is not None
                ]
                if successful_attempts:
                    successful = max(successful_attempts, key=lambda item: item.attempt_no)
                    if any(item.attempt_no > successful.attempt_no for item in attempts):
                        raise ProviderPersistenceConflictError(
                            "成功 Provider Attempt 之后存在额外执行事实，无法静默选择重发"
                        )
                    return PreparedProviderAttempt(
                        request=persisted_request,
                        attempt=successful,
                    )

                reserved_attempts = [
                    attempt for attempt in attempts if attempt.dispatch_status == "reserved"
                ]
                if len(reserved_attempts) > 1:
                    raise ProviderPersistenceConflictError(
                        "同一 Provider Request 存在多个 reserved Attempt，无法安全恢复"
                    )

                resolved_attempt_id = reserved_attempts[0].id if reserved_attempts else attempt_id
                return service.prepare_billable_attempt(
                    request=request,
                    provider_config_id=provider_config_id,
                    attempt_id=resolved_attempt_id,
                    billing=billing,
                )
        finally:
            session.close()

    def read_scope_counts(
        self,
        *,
        scope_id: UUID,
        fence: JobExecutionFence,
    ) -> CollectionScopeExecutionCounts:
        """从数据库执行事实聚合计数，避免进程崩溃造成内存统计丢失。"""
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                ownership = session.execute(
                    select(collection_runs_table.c.job_id)
                    .select_from(
                        collection_scopes_table.join(
                            collection_runs_table,
                            collection_scopes_table.c.run_id == collection_runs_table.c.id,
                        )
                    )
                    .where(collection_scopes_table.c.id == scope_id)
                ).scalar_one_or_none()
                if ownership != fence.job_id:
                    raise LeaseLostError("Collection Scope 不属于当前 Job Fence")

                attempts = session.execute(
                    select(
                        provider_request_attempts_table.c.dispatch_status,
                        provider_request_attempts_table.c.error_code,
                    )
                    .select_from(
                        provider_request_attempts_table.join(
                            provider_requests_table,
                            provider_request_attempts_table.c.provider_request_id
                            == provider_requests_table.c.id,
                        )
                    )
                    .where(provider_requests_table.c.scope_id == scope_id)
                ).all()
                requested_count = sum(status != "reserved" for status, _ in attempts)
                succeeded_count = sum(
                    status == "completed" and error_code is None for status, error_code in attempts
                )
                failed_count = sum(
                    status in {"not_sent", "unknown"}
                    or (status == "completed" and error_code is not None)
                    for status, error_code in attempts
                )

                def candidate_count(kind: str) -> int:
                    value = session.scalar(
                        select(
                            func.count(
                                func.distinct(
                                    func.coalesce(
                                        collection_candidates_table.c.external_item_id,
                                        collection_candidates_table.c.item_locator,
                                    )
                                )
                            )
                        )
                        .select_from(
                            collection_candidates_table.join(
                                provider_request_attempts_table,
                                collection_candidates_table.c.provider_request_attempt_id
                                == provider_request_attempts_table.c.id,
                            ).join(
                                provider_requests_table,
                                provider_request_attempts_table.c.provider_request_id
                                == provider_requests_table.c.id,
                            )
                        )
                        .where(
                            provider_requests_table.c.scope_id == scope_id,
                            collection_candidates_table.c.item_kind == kind,
                        )
                    )
                    return int(value or 0)

                return CollectionScopeExecutionCounts(
                    requested_count=requested_count,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                    content_count=candidate_count("content"),
                    comment_count=candidate_count("comment"),
                )
        finally:
            session.close()

    @staticmethod
    def _require_request_scope(
        session: Session,
        *,
        request: ProviderRequestV1,
        fence: JobExecutionFence,
    ) -> None:
        ownership = session.execute(
            select(
                collection_scopes_table.c.run_id,
                collection_scopes_table.c.platform,
                collection_runs_table.c.job_id,
            )
            .select_from(
                collection_scopes_table.join(
                    collection_runs_table,
                    collection_scopes_table.c.run_id == collection_runs_table.c.id,
                )
            )
            .where(collection_scopes_table.c.id == request.scope_id)
        ).one_or_none()
        if ownership is None:
            raise LeaseLostError("Provider Request Scope 不属于当前 Job Fence")
        if (
            ownership.run_id != request.run_id
            or ownership.platform != request.platform
            or ownership.job_id != fence.job_id
        ):
            raise LeaseLostError("Provider Request Scope 不属于当前 Job Fence")


__all__ = [
    "CollectionScopeExecutionCounts",
    "PostgresFencedProviderAttemptPreparer",
]
