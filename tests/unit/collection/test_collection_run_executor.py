"""Collection Run Job 的 Scope 隔离与终态聚合测试。"""

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

_NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class _Context:
    def __init__(self, *, cancel_after_heartbeats: int | None = None) -> None:
        self._fence = JobExecutionFence(job_id=uuid4(), lease_token="lease")
        self._cancel_after = cancel_after_heartbeats
        self.heartbeats: list[int] = []

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        self.heartbeats.append(progress)

    def cancel_requested(self) -> bool:
        return self._cancel_after is not None and len(self.heartbeats) >= self._cancel_after


class _Gateway:
    def __init__(self, execution: CollectionExecution) -> None:
        self.execution = execution
        self.started_scopes: list[UUID] = []
        self.finished_scopes: list[tuple[UUID, str, str | None]] = []
        self.finished_run: tuple[str, dict[str, int]] | None = None

    def _check_fence(self, fence: JobExecutionFence) -> None:
        assert fence.job_id == self.execution.run.job_id

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None:
        self._check_fence(fence)
        return self.execution

    def start_run(
        self,
        run_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CollectionRunRecord:
        self._check_fence(fence)
        assert run_id == self.execution.run.id
        return self.execution.run

    def start_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CollectionScopeRecord:
        self._check_fence(fence)
        self.started_scopes.append(scope_id)
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
        self._check_fence(fence)
        self.finished_scopes.append((scope_id, status, stop_reason))
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
        self._check_fence(fence)
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
        self._results = results
        self.calls: list[UUID] = []

    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: _Context,
    ) -> CollectionScopeExecutionResult:
        self.calls.append(scope.id)
        result = self._results[scope.id]
        if isinstance(result, Exception):
            raise result
        return result


def _execution(scope_count: int = 2) -> CollectionExecution:
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
        for index in range(scope_count)
    )
    return CollectionExecution(run=run, scopes=scopes)


def _result(
    *,
    status: str = "succeeded",
    requests: int = 1,
    contents: int = 2,
    comments: int = 0,
) -> CollectionScopeExecutionResult:
    return CollectionScopeExecutionResult(
        status=status,
        stop_reason="provider_exhausted",
        pagination_state={"page": 1},
        stats={"requests": requests, "contents": contents, "comments": comments},
        requested_count=requests,
        succeeded_count=requests if status != "failed" else 0,
        failed_count=requests if status == "failed" else 0,
        content_count=contents,
        comment_count=comments,
    )


def test_executor_finishes_successful_run_with_aggregated_scope_counts() -> None:
    execution = _execution()
    context = _Context()
    context._fence = JobExecutionFence(job_id=execution.run.job_id, lease_token="lease")
    gateway = _Gateway(execution)
    scope_executor = _ScopeExecutor({scope.id: _result() for scope in execution.scopes})

    result = CollectionRunExecutor(gateway=gateway, scope_executor=scope_executor).execute(
        fence=context.fence,
        context=context,
    )

    assert result == JobHandlerResult.succeeded(
        {
            "run_id": str(execution.run.id),
            "status": "succeeded",
            "requested_count": 2,
            "succeeded_count": 2,
            "failed_count": 0,
            "content_count": 4,
            "comment_count": 0,
        }
    )
    assert gateway.finished_run == (
        "succeeded",
        {
            "requested_count": 2,
            "succeeded_count": 2,
            "failed_count": 0,
            "content_count": 4,
            "comment_count": 0,
        },
    )
    assert [status for _, status, _ in gateway.finished_scopes] == ["succeeded", "succeeded"]


def test_executor_isolates_scope_exception_and_marks_run_partial_success() -> None:
    execution = _execution()
    context = _Context()
    context._fence = JobExecutionFence(job_id=execution.run.job_id, lease_token="lease")
    gateway = _Gateway(execution)
    first, second = execution.scopes
    scope_executor = _ScopeExecutor(
        {
            first.id: RuntimeError("provider response contained sensitive text"),
            second.id: _result(),
        }
    )

    result = CollectionRunExecutor(gateway=gateway, scope_executor=scope_executor).execute(
        fence=context.fence,
        context=context,
    )

    assert result.outcome == "succeeded"
    assert result.result is not None
    assert result.result["status"] == "partial_success"
    assert scope_executor.calls == [first.id, second.id]
    assert gateway.finished_scopes[0] == (first.id, "failed", "scope_execution_failed")
    assert gateway.finished_run is not None
    assert gateway.finished_run[0] == "partial_success"


def test_executor_stops_before_next_scope_when_job_is_cancel_requested() -> None:
    execution = _execution()
    context = _Context(cancel_after_heartbeats=1)
    context._fence = JobExecutionFence(job_id=execution.run.job_id, lease_token="lease")
    gateway = _Gateway(execution)
    scope_executor = _ScopeExecutor({scope.id: _result() for scope in execution.scopes})

    result = CollectionRunExecutor(gateway=gateway, scope_executor=scope_executor).execute(
        fence=context.fence,
        context=context,
    )

    assert result == JobHandlerResult.cancelled()
    assert len(scope_executor.calls) == 1
    assert gateway.finished_run is not None
    assert gateway.finished_run[0] == "cancelled"
