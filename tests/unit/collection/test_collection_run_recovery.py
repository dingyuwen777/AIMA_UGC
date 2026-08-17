"""Collection Run 崩溃恢复与可重试 Scope 的回归测试。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aima_ugc.modules.collection.collection_run_executor import (
    CollectionRunExecutor,
    CollectionScopeExecutionResult,
    CollectionScopeRetryableError,
)
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionRunRecord,
    CollectionScopeRecord,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult

_NOW = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)


class _Context:
    def __init__(self, job_id: UUID) -> None:
        self._fence = JobExecutionFence(job_id=job_id, lease_token="lease")
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
        self.started_scopes: list[UUID] = []
        self.checkpoints: list[tuple[UUID, dict[str, object], int, dict[str, object]]] = []
        self.finished_scopes: list[tuple[UUID, str]] = []
        self.finished_run: tuple[str, dict[str, int]] | None = None

    def load(self, fence: JobExecutionFence) -> CollectionExecution:
        assert fence.job_id == self.execution.run.job_id
        return self.execution

    def start_run(self, run_id: UUID, *, fence: JobExecutionFence) -> CollectionRunRecord:
        assert fence.job_id == self.execution.run.job_id
        assert run_id == self.execution.run.id
        return self.execution.run

    def start_scope(self, scope_id: UUID, *, fence: JobExecutionFence) -> CollectionScopeRecord:
        assert fence.job_id == self.execution.run.job_id
        self.started_scopes.append(scope_id)
        return next(scope for scope in self.execution.scopes if scope.id == scope_id)

    def checkpoint_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
        pagination_state: dict[str, object],
        progress: int,
        stats: dict[str, object],
    ) -> CollectionScopeRecord:
        assert fence.job_id == self.execution.run.job_id
        self.checkpoints.append((scope_id, pagination_state, progress, stats))
        scope = next(scope for scope in self.execution.scopes if scope.id == scope_id)
        return replace(
            scope,
            pagination_state=dict(pagination_state),
            progress=progress,
            stats=dict(stats),
        )

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
        assert fence.job_id == self.execution.run.job_id
        self.finished_scopes.append((scope_id, status))
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
        assert fence.job_id == self.execution.run.job_id
        assert run_id == self.execution.run.id
        self.finished_run = (
            status,
            {
                "requested_count": requested_count,
                "succeeded_count": succeeded_count,
                "failed_count": failed_count,
                "content_count": content_count,
                "comment_count": comment_count,
            },
        )
        return self.execution.run


class _ScopeExecutor:
    def __init__(self, results: dict[UUID, CollectionScopeExecutionResult | Exception]) -> None:
        self.results = results
        self.calls: list[UUID] = []

    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: _Context,
    ) -> CollectionScopeExecutionResult:
        self.calls.append(scope.id)
        result = self.results[scope.id]
        if isinstance(result, Exception):
            raise result
        return result


def _execution() -> CollectionExecution:
    run_id = uuid4()
    job_id = uuid4()
    run = CollectionRunRecord(
        id=run_id,
        job_id=job_id,
        manual_plan_id=None,
        occurrence_id=None,
        trigger_type="api",
        config_snapshot={},
        status="running",
        started_at=_NOW,
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
            platform=f"p{index}",
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
        for index in range(2)
    )
    return CollectionExecution(run=run, scopes=scopes)


def _result(*, requests: int = 1, contents: int = 1) -> CollectionScopeExecutionResult:
    return CollectionScopeExecutionResult(
        status="succeeded",
        stop_reason="provider_exhausted",
        pagination_state={"page": 1},
        stats={
            "requested_count": requests,
            "succeeded_count": requests,
            "failed_count": 0,
            "content_count": contents,
            "comment_count": 0,
        },
        requested_count=requests,
        succeeded_count=requests,
        failed_count=0,
        content_count=contents,
        comment_count=0,
    )


def test_executor_skips_terminal_scope_and_reuses_its_persisted_totals() -> None:
    execution = _execution()
    first, second = execution.scopes
    completed = replace(
        first,
        status="succeeded",
        progress=100,
        stop_reason="provider_exhausted",
        stats={
            "requested_count": 2,
            "succeeded_count": 2,
            "failed_count": 0,
            "content_count": 3,
            "comment_count": 4,
        },
        finished_at=_NOW,
    )
    execution = CollectionExecution(run=execution.run, scopes=(completed, second))
    gateway = _Gateway(execution)
    scope_executor = _ScopeExecutor({second.id: _result(requests=1, contents=2)})
    context = _Context(execution.run.job_id)

    result = CollectionRunExecutor(gateway=gateway, scope_executor=scope_executor).execute(
        fence=context.fence,
        context=context,
    )

    assert scope_executor.calls == [second.id]
    assert gateway.started_scopes == [second.id]
    assert result == JobHandlerResult.succeeded(
        {
            "run_id": str(execution.run.id),
            "status": "succeeded",
            "requested_count": 3,
            "succeeded_count": 3,
            "failed_count": 0,
            "content_count": 5,
            "comment_count": 4,
        }
    )


def test_retryable_scope_error_checkpoints_without_terminalizing_run() -> None:
    execution = _execution()
    first, second = execution.scopes
    retryable = CollectionScopeRetryableError(
        error_code="http_500",
        pagination_state={"page": 2},
        progress=17,
        stats={
            "requested_count": 2,
            "succeeded_count": 1,
            "failed_count": 1,
            "content_count": 3,
            "comment_count": 4,
        },
        requested_count=2,
        succeeded_count=1,
        failed_count=1,
        content_count=3,
        comment_count=4,
    )
    gateway = _Gateway(execution)
    scope_executor = _ScopeExecutor({first.id: retryable, second.id: _result()})
    context = _Context(execution.run.job_id)

    result = CollectionRunExecutor(gateway=gateway, scope_executor=scope_executor).execute(
        fence=context.fence,
        context=context,
    )

    assert result == JobHandlerResult.retry("http_500")
    assert scope_executor.calls == [first.id]
    assert gateway.checkpoints == [
        (
            first.id,
            {"page": 2},
            17,
            {
                "requested_count": 2,
                "succeeded_count": 1,
                "failed_count": 1,
                "content_count": 3,
                "comment_count": 4,
            },
        )
    ]
    assert gateway.finished_scopes == []
    assert gateway.finished_run is None
