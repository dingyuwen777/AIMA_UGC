"""Collection Run 状态推进必须复用当前 Job Fencing Token。"""

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

_NOW = datetime(2026, 8, 17, tzinfo=UTC)


class _Context:
    def __init__(self, fence: JobExecutionFence) -> None:
        self._fence = fence

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


class _FencedGateway:
    def __init__(self, execution: CollectionExecution, expected_fence: JobExecutionFence) -> None:
        self.execution = execution
        self.expected_fence = expected_fence
        self.observed: list[JobExecutionFence] = []

    def _check(self, fence: JobExecutionFence) -> None:
        assert fence == self.expected_fence
        self.observed.append(fence)

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None:
        self._check(fence)
        return self.execution if fence.job_id == self.execution.run.job_id else None

    def start_run(self, run_id: UUID, *, fence: JobExecutionFence) -> CollectionRunRecord:
        self._check(fence)
        assert run_id == self.execution.run.id
        return self.execution.run

    def start_scope(self, scope_id: UUID, *, fence: JobExecutionFence) -> CollectionScopeRecord:
        self._check(fence)
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
        self._check(fence)
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
        self._check(fence)
        assert run_id == self.execution.run.id
        return self.execution.run


class _ScopeExecutor:
    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: _Context,
    ) -> CollectionScopeExecutionResult:
        return CollectionScopeExecutionResult(
            status="succeeded",
            stop_reason="provider_exhausted",
            pagination_state={},
            stats={},
            requested_count=1,
            succeeded_count=1,
            failed_count=0,
            content_count=1,
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
    scope = CollectionScopeRecord(
        id=uuid4(),
        run_id=run_id,
        platform="xhs",
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
    return CollectionExecution(run=run, scopes=(scope,))


def test_executor_passes_current_fence_to_every_gateway_state_transition() -> None:
    execution = _execution()
    fence = JobExecutionFence(job_id=execution.run.job_id, lease_token="lease-token")
    gateway = _FencedGateway(execution, fence)

    result = CollectionRunExecutor(
        gateway=gateway,
        scope_executor=_ScopeExecutor(),
    ).execute(
        fence=fence,
        context=_Context(fence),
    )

    assert result == JobHandlerResult.succeeded(
        {
            "run_id": str(execution.run.id),
            "status": "succeeded",
            "requested_count": 1,
            "succeeded_count": 1,
            "failed_count": 0,
            "content_count": 1,
            "comment_count": 0,
        }
    )
    assert gateway.observed == [fence, fence, fence, fence, fence]
