"""Collection Run 运行前准备编排测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from aima_ugc.modules.collection.collection_run_executor import (
    CollectionRunExecutor,
    CollectionScopeExecutionResult,
)
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionRunRecord,
    CollectionScopeRecord,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult

_NOW = datetime(2026, 8, 17, 0, 30, tzinfo=UTC)


class _Context:
    def __init__(self, fence: JobExecutionFence) -> None:
        self._fence = fence
        self.heartbeats: list[int] = []

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        self.heartbeats.append(progress)

    def cancel_requested(self) -> bool:
        return False


class _Gateway:
    def __init__(self, execution: CollectionExecution) -> None:
        self.execution = execution

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None:
        assert fence.job_id == self.execution.run.job_id
        return self.execution

    def start_run(self, run_id: UUID, *, fence: JobExecutionFence) -> CollectionRunRecord:
        assert run_id == self.execution.run.id
        return self.execution.run

    def start_scope(self, scope_id: UUID, *, fence: JobExecutionFence) -> CollectionScopeRecord:
        return next(scope for scope in self.execution.scopes if scope.id == scope_id)

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
        return next(scope for scope in self.execution.scopes if scope.id == scope_id)

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
        return self.execution.run


class _RunPreparer:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, tuple[UUID, ...], JobExecutionFence]] = []

    def prepare(
        self,
        *,
        execution: CollectionExecution,
        fence: JobExecutionFence,
    ) -> None:
        self.calls.append(
            (
                execution.run.id,
                tuple(scope.id for scope in execution.scopes),
                fence,
            )
        )


class _ScopeExecutor:
    def __init__(self, preparer: _RunPreparer) -> None:
        self._preparer = preparer
        self.calls: list[UUID] = []

    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: _Context,
    ) -> CollectionScopeExecutionResult:
        assert self._preparer.calls, "Run 预算/路由准备必须早于任何 Scope 执行"
        self.calls.append(scope.id)
        return CollectionScopeExecutionResult(
            status="succeeded",
            stop_reason="provider_exhausted",
            pagination_state={},
            stats={},
            requested_count=0,
            succeeded_count=0,
            failed_count=0,
            content_count=0,
            comment_count=0,
        )


def _execution() -> CollectionExecution:
    run_id = uuid4()
    job_id = uuid4()
    run = CollectionRunRecord(
        id=run_id,
        job_id=job_id,
        manual_plan_id=None,
        occurrence_id=None,
        trigger_type="scheduled",
        config_snapshot={"schema_version": "collection-run-config.v1"},
        status="queued",
        started_at=None,
        finished_at=None,
        requested_count=0,
        succeeded_count=0,
        failed_count=0,
        content_count=0,
        comment_count=0,
        error_summary=None,
        created_at=_NOW,
    )
    scopes = tuple(
        CollectionScopeRecord(
            id=uuid4(),
            run_id=run_id,
            platform=platform,
            source_type="keyword_search",
            source_value="爱玛",
            operation_group="content_discovery",
            status="queued",
            pagination_state={},
            progress=0,
            stop_reason=None,
            stats={},
            started_at=None,
            finished_at=None,
        )
        for platform in ("xhs", "douyin")
    )
    return CollectionExecution(run=run, scopes=scopes)


def test_run_preparer_receives_full_execution_before_first_scope() -> None:
    execution = _execution()
    fence = JobExecutionFence(job_id=execution.run.job_id, lease_token="lease-token")
    preparer = _RunPreparer()
    scope_executor = _ScopeExecutor(preparer)

    result = CollectionRunExecutor(
        gateway=_Gateway(execution),
        run_preparer=preparer,
        scope_executor=scope_executor,
    ).execute(fence=fence, context=_Context(fence))

    assert result == JobHandlerResult.succeeded(
        {
            "run_id": str(execution.run.id),
            "status": "succeeded",
            "requested_count": 0,
            "succeeded_count": 0,
            "failed_count": 0,
            "content_count": 0,
            "comment_count": 0,
        }
    )
    assert preparer.calls == [
        (execution.run.id, tuple(scope.id for scope in execution.scopes), fence)
    ]
    assert scope_executor.calls == [scope.id for scope in execution.scopes]
