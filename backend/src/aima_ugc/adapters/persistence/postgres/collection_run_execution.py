"""Collection Run/Scope 状态推进的 PostgreSQL Fencing Gateway。"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionRunRecord,
    CollectionScopeRecord,
)
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .collection import PostgresCollectionRepository
from .jobs import PostgresJobRepository


class PostgresCollectionRunExecutionGateway:
    """每个业务可见状态事务先验证当前 Job Fencing，再复用 Collection 唯一写 Owner。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None:
        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                repository = PostgresCollectionRepository(session)
                run = repository.get_run_by_job_id(fence.job_id)
                if run is None:
                    return None
                return CollectionExecution(run=run, scopes=tuple(repository.list_scopes(run.id)))
        finally:
            session.close()

    def start_run(
        self,
        run_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CollectionRunRecord:
        session = self._session_factory()
        try:
            with session.begin():
                repository = self._locked_repository(session, fence)
                self._require_run(repository, fence=fence, run_id=run_id)
                return repository.start_run(run_id)
        finally:
            session.close()

    def start_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CollectionScopeRecord:
        session = self._session_factory()
        try:
            with session.begin():
                repository = self._locked_repository(session, fence)
                self._require_scope(repository, fence=fence, scope_id=scope_id)
                return repository.start_scope(scope_id)
        finally:
            session.close()

    def finish_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
        status: str,
        stop_reason: str | None,
        pagination_state: dict[str, object],
        stats: dict[str, object],
    ) -> CollectionScopeRecord:
        session = self._session_factory()
        try:
            with session.begin():
                repository = self._locked_repository(session, fence)
                self._require_scope(repository, fence=fence, scope_id=scope_id)
                return repository.finish_scope(
                    scope_id,
                    status=status,
                    stop_reason=stop_reason,
                    pagination_state=pagination_state,
                    stats=stats,
                )
        finally:
            session.close()

    def finish_run(
        self,
        run_id: UUID,
        *,
        fence: JobExecutionFence,
        status: str,
        requested_count: int,
        succeeded_count: int,
        failed_count: int,
        content_count: int,
        comment_count: int,
        error_summary: str | None,
    ) -> CollectionRunRecord:
        session = self._session_factory()
        try:
            with session.begin():
                repository = self._locked_repository(session, fence)
                self._require_run(repository, fence=fence, run_id=run_id)
                return repository.finish_run(
                    run_id,
                    status=status,
                    requested_count=requested_count,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                    content_count=content_count,
                    comment_count=comment_count,
                    error_summary=error_summary,
                )
        finally:
            session.close()

    @staticmethod
    def _locked_repository(
        session: Session,
        fence: JobExecutionFence,
    ) -> PostgresCollectionRepository:
        PostgresJobRepository(session).lock_current_execution(fence)
        return PostgresCollectionRepository(session)

    @staticmethod
    def _require_run(
        repository: PostgresCollectionRepository,
        *,
        fence: JobExecutionFence,
        run_id: UUID,
    ) -> CollectionRunRecord:
        run = repository.get_run_by_job_id(fence.job_id)
        if run is None or run.id != run_id:
            raise LeaseLostError("Collection Run 不属于当前 Job Fence")
        return run

    @classmethod
    def _require_scope(
        cls,
        repository: PostgresCollectionRepository,
        *,
        fence: JobExecutionFence,
        scope_id: UUID,
    ) -> CollectionScopeRecord:
        run = repository.get_run_by_job_id(fence.job_id)
        if run is None:
            raise LeaseLostError("Collection Run 不属于当前 Job Fence")
        scope = next((item for item in repository.list_scopes(run.id) if item.id == scope_id), None)
        if scope is None:
            raise LeaseLostError("Collection Scope 不属于当前 Job Fence")
        return scope


__all__ = ["PostgresCollectionRunExecutionGateway"]
