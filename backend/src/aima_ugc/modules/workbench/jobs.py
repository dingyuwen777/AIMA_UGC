"""工作台聚合快照的版本化持久 Job 边界。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.contracts.workbench import WorkbenchQuery
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

WORKBENCH_SNAPSHOT_JOB_TYPE = "workbench.snapshot-refresh.v1"
WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION = "workbench.snapshot-refresh.v1"
# 用户可见快照高于普通批量导入/重放，仍低于取消与撤回等恢复动作。
WORKBENCH_SNAPSHOT_JOB_PRIORITY = 10
WORKBENCH_SNAPSHOT_JOB_TIMEOUT_SECONDS = 900
WORKBENCH_SNAPSHOT_JOB_MAX_ATTEMPTS = 3


class WorkbenchSnapshotJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["workbench.snapshot-refresh.v1"] = "workbench.snapshot-refresh.v1"
    module: Literal["mind", "trend"]
    query_hash: str
    query: WorkbenchQuery
    source_revision: int
    refresh_generation: int
    analysis_scheme_version_id: UUID


class WorkbenchSnapshotJobExecutor(Protocol):
    def execute(
        self,
        *,
        payload: WorkbenchSnapshotJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class WorkbenchSnapshotJobHandler:
    def __init__(self, executor: WorkbenchSnapshotJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, WorkbenchSnapshotJobPayload):
            raise TypeError("Workbench Snapshot Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_workbench_snapshot_job(
    registry: JobRegistry,
    handler: WorkbenchSnapshotJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    registry.register(
        job_type=WORKBENCH_SNAPSHOT_JOB_TYPE,
        payload_version=WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION,
        payload_model=WorkbenchSnapshotJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "WORKBENCH_SNAPSHOT_JOB_MAX_ATTEMPTS",
    "WORKBENCH_SNAPSHOT_JOB_PAYLOAD_VERSION",
    "WORKBENCH_SNAPSHOT_JOB_PRIORITY",
    "WORKBENCH_SNAPSHOT_JOB_TIMEOUT_SECONDS",
    "WORKBENCH_SNAPSHOT_JOB_TYPE",
    "WorkbenchSnapshotJobExecutor",
    "WorkbenchSnapshotJobHandler",
    "WorkbenchSnapshotJobPayload",
    "register_workbench_snapshot_job",
]
