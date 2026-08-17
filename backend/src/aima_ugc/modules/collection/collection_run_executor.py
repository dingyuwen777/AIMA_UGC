"""Collection Run Job 的 Scope 编排与终态聚合。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError

from .execution import CollectionExecution, CollectionRunRecord, CollectionScopeRecord

CollectionScopeTerminalStatus = Literal[
    "partial_success",
    "succeeded",
    "failed",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class CollectionScopeExecutionResult:
    """单个 Scope 执行完成后交给 Run 聚合器的稳定结果。"""

    status: CollectionScopeTerminalStatus
    stop_reason: str | None
    pagination_state: dict[str, object]
    stats: dict[str, object]
    requested_count: int
    succeeded_count: int
    failed_count: int
    content_count: int
    comment_count: int

    def __post_init__(self) -> None:
        counts = (
            self.requested_count,
            self.succeeded_count,
            self.failed_count,
            self.content_count,
            self.comment_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Collection Scope 聚合计数不能为负数")


class CollectionRunExecutionGateway(Protocol):
    """Run Executor 所需的最小状态推进边界；所有业务可见写入必须携带当前 Fence。"""

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None: ...

    def start_run(
        self,
        run_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CollectionRunRecord: ...

    def start_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CollectionScopeRecord: ...

    def finish_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
        status: str,
        stop_reason: str | None,
        pagination_state: dict[str, object],
        stats: dict[str, object],
    ) -> CollectionScopeRecord: ...

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
    ) -> CollectionRunRecord: ...


class CollectionScopeExecutor(Protocol):
    """执行一个 Scope；Provider/Raw/Mapper/Ingestion 细节留在 Scope 实现内。"""

    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: JobExecutionContextProtocol,
    ) -> CollectionScopeExecutionResult: ...


@dataclass(slots=True)
class _RunTotals:
    requested_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    content_count: int = 0
    comment_count: int = 0

    def add(self, result: CollectionScopeExecutionResult) -> None:
        self.requested_count += result.requested_count
        self.succeeded_count += result.succeeded_count
        self.failed_count += result.failed_count
        self.content_count += result.content_count
        self.comment_count += result.comment_count

    def payload(self) -> dict[str, int]:
        return {
            "requested_count": self.requested_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "content_count": self.content_count,
            "comment_count": self.comment_count,
        }


class CollectionRunExecutor:
    """按 Scope 隔离执行一个 Collection Run，并聚合最终状态。"""

    def __init__(
        self,
        *,
        gateway: CollectionRunExecutionGateway,
        scope_executor: CollectionScopeExecutor,
    ) -> None:
        self._gateway = gateway
        self._scope_executor = scope_executor

    def execute(
        self,
        *,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        execution = self._gateway.load(fence)
        if execution is None:
            return JobHandlerResult.failed("collection_run_not_found")

        run = self._gateway.start_run(execution.run.id, fence=fence)
        totals = _RunTotals()
        failed_scopes = 0
        partial_scopes = 0
        total_scopes = len(execution.scopes)

        for index, queued_scope in enumerate(execution.scopes):
            if context.cancel_requested():
                self._finish_run(
                    run=run,
                    fence=fence,
                    status="cancelled",
                    totals=totals,
                    error_summary="cancel_requested",
                )
                return JobHandlerResult.cancelled()

            scope = self._gateway.start_scope(queued_scope.id, fence=fence)
            try:
                scope_result = self._scope_executor.execute(
                    run=run,
                    scope=scope,
                    context=context,
                )
            except LeaseLostError:
                raise
            except Exception:
                failed_scopes += 1
                self._gateway.finish_scope(
                    scope.id,
                    fence=fence,
                    status="failed",
                    stop_reason="scope_execution_failed",
                    pagination_state=dict(scope.pagination_state),
                    stats=dict(scope.stats),
                )
            else:
                totals.add(scope_result)
                self._gateway.finish_scope(
                    scope.id,
                    fence=fence,
                    status=scope_result.status,
                    stop_reason=scope_result.stop_reason,
                    pagination_state=dict(scope_result.pagination_state),
                    stats=dict(scope_result.stats),
                )
                if scope_result.status == "failed":
                    failed_scopes += 1
                elif scope_result.status == "partial_success":
                    partial_scopes += 1
                elif scope_result.status == "cancelled":
                    self._finish_run(
                        run=run,
                        fence=fence,
                        status="cancelled",
                        totals=totals,
                        error_summary="scope_cancelled",
                    )
                    return JobHandlerResult.cancelled()

            if total_scopes:
                context.heartbeat(progress=((index + 1) * 100) // total_scopes)

        if failed_scopes == total_scopes and total_scopes > 0:
            run_status = "failed"
        elif failed_scopes or partial_scopes:
            run_status = "partial_success"
        else:
            run_status = "succeeded"

        error_summary = "scope_execution_failed" if failed_scopes else None
        self._finish_run(
            run=run,
            fence=fence,
            status=run_status,
            totals=totals,
            error_summary=error_summary,
        )
        if run_status == "failed":
            return JobHandlerResult.failed("collection_run_failed")
        return JobHandlerResult.succeeded(
            {
                "run_id": str(run.id),
                "status": run_status,
                **totals.payload(),
            }
        )

    def _finish_run(
        self,
        *,
        run: CollectionRunRecord,
        fence: JobExecutionFence,
        status: str,
        totals: _RunTotals,
        error_summary: str | None,
    ) -> CollectionRunRecord:
        return self._gateway.finish_run(
            run.id,
            fence=fence,
            status=status,
            requested_count=totals.requested_count,
            succeeded_count=totals.succeeded_count,
            failed_count=totals.failed_count,
            content_count=totals.content_count,
            comment_count=totals.comment_count,
            error_summary=error_summary,
        )


__all__ = [
    "CollectionRunExecutionGateway",
    "CollectionRunExecutor",
    "CollectionScopeExecutionResult",
    "CollectionScopeExecutor",
]
