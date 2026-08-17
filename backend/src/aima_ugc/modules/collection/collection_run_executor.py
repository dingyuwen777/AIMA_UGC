"""Collection Run Job 的 Scope 编排、恢复与终态聚合。"""

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
_SCOPE_TERMINAL_STATUSES: frozenset[CollectionScopeTerminalStatus] = frozenset(
    {"partial_success", "succeeded", "failed", "cancelled"}
)


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


class CollectionScopeRetryableError(RuntimeError):
    """Scope 遇到可重试外部失败时携带 durable checkpoint 返回 Job Runtime。"""

    def __init__(
        self,
        *,
        error_code: str,
        pagination_state: dict[str, object],
        progress: int,
        stats: dict[str, object],
        requested_count: int,
        succeeded_count: int,
        failed_count: int,
        content_count: int,
        comment_count: int,
    ) -> None:
        super().__init__(error_code)
        if not error_code:
            raise ValueError("可重试 Scope 错误必须包含 error_code")
        if progress < 0 or progress > 99:
            raise ValueError("可重试 Scope checkpoint progress 必须在 0..99")
        counts = (
            requested_count,
            succeeded_count,
            failed_count,
            content_count,
            comment_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("可重试 Scope checkpoint 计数不能为负数")
        self.error_code = error_code
        self.pagination_state = dict(pagination_state)
        self.progress = progress
        self.stats = dict(stats)
        self.requested_count = requested_count
        self.succeeded_count = succeeded_count
        self.failed_count = failed_count
        self.content_count = content_count
        self.comment_count = comment_count


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

    def checkpoint_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
        pagination_state: dict[str, object],
        progress: int,
        stats: dict[str, object],
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

    def add_persisted_scope(self, scope: CollectionScopeRecord) -> None:
        """恢复时从 Scope durable stats 复用已终态结果，不重新执行业务副作用。"""
        self.requested_count += _stat_int(scope.stats, "requested_count")
        self.succeeded_count += _stat_int(scope.stats, "succeeded_count")
        self.failed_count += _stat_int(scope.stats, "failed_count")
        self.content_count += _stat_int(scope.stats, "content_count")
        self.comment_count += _stat_int(scope.stats, "comment_count")

    def payload(self) -> dict[str, int]:
        return {
            "requested_count": self.requested_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "content_count": self.content_count,
            "comment_count": self.comment_count,
        }


class CollectionRunExecutor:
    """按 Scope 隔离执行一个 Collection Run，并在 Lease takeover 后从 durable 状态恢复。"""

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

        for index, persisted_scope in enumerate(execution.scopes):
            if persisted_scope.status in _SCOPE_TERMINAL_STATUSES:
                totals.add_persisted_scope(persisted_scope)
                if persisted_scope.status == "failed":
                    failed_scopes += 1
                elif persisted_scope.status == "partial_success":
                    partial_scopes += 1
                elif persisted_scope.status == "cancelled":
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
                continue

            if context.cancel_requested():
                self._finish_run(
                    run=run,
                    fence=fence,
                    status="cancelled",
                    totals=totals,
                    error_summary="cancel_requested",
                )
                return JobHandlerResult.cancelled()

            scope = self._gateway.start_scope(persisted_scope.id, fence=fence)
            try:
                scope_result = self._scope_executor.execute(
                    run=run,
                    scope=scope,
                    context=context,
                )
            except LeaseLostError:
                raise
            except CollectionScopeRetryableError as exc:
                self._gateway.checkpoint_scope(
                    scope.id,
                    fence=fence,
                    pagination_state=exc.pagination_state,
                    progress=max(scope.progress, exc.progress),
                    stats=exc.stats,
                )
                return JobHandlerResult.retry(exc.error_code)
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


def _stat_int(stats: dict[str, object], name: str) -> int:
    value = stats.get(name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Collection Scope durable stats.{name} 必须为非负整数")
    return value


__all__ = [
    "CollectionRunExecutionGateway",
    "CollectionRunExecutor",
    "CollectionScopeExecutionResult",
    "CollectionScopeExecutor",
    "CollectionScopeRetryableError",
]
