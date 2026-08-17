"""Collection live runtime 的 Fenced Provider Request/Attempt 准备入口。"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import (
    PreparedProviderAttempt,
    ProviderPersistenceConflictError,
    ProviderPersistenceService,
)
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .jobs import PostgresJobRepository
from .provider import PostgresProviderRepository


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
        """恢复时优先复用同一逻辑 Request 下尚未发送的 reserved Attempt。"""
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
                reserved_attempts = [
                    attempt
                    for attempt in repository.list_attempts(persisted_request.id)
                    if attempt.dispatch_status == "reserved"
                ]
                if len(reserved_attempts) > 1:
                    raise ProviderPersistenceConflictError(
                        "同一 Provider Request 存在多个 reserved Attempt，无法安全恢复"
                    )

                resolved_attempt_id = (
                    reserved_attempts[0].id if reserved_attempts else attempt_id
                )
                return service.prepare_billable_attempt(
                    request=request,
                    provider_config_id=provider_config_id,
                    attempt_id=resolved_attempt_id,
                    billing=billing,
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


__all__ = ["PostgresFencedProviderAttemptPreparer"]
