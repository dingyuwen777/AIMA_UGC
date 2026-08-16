"""正式 Collection Run Job 的 Payload、Handler 与 Registry 装配边界。"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

COLLECTION_RUN_JOB_TYPE = "collection.run.v1"
COLLECTION_RUN_PAYLOAD_VERSION = "collection.run.v1"


class CollectionRunJobPayload(BaseModel):
    """Worker 通过当前 Job ID 反查 Run；Payload 不复制 Run ID、Plan 或 Secret。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["collection.run.v1"] = "collection.run.v1"


class CollectionRunJobExecutor(Protocol):
    """正式 Collection Run 业务执行器；Job Handler 只负责稳定 Runtime 边界。"""

    def execute(
        self,
        *,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class CollectionRunJobHandler:
    """从当前 Job Fence 进入 Collection 执行链，不信任 Payload 业务标识。"""

    def __init__(self, executor: CollectionRunJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, CollectionRunJobPayload):
            raise TypeError("Collection Run Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(fence=context.fence, context=context)


def register_collection_run_job(
    registry: JobRegistry,
    handler: CollectionRunJobHandler,
) -> None:
    """把正式 Scheduler Job 类型注册到共享 PostgreSQL Job Runtime。"""
    registry.register(
        job_type=COLLECTION_RUN_JOB_TYPE,
        payload_version=COLLECTION_RUN_PAYLOAD_VERSION,
        payload_model=CollectionRunJobPayload,
        handler=handler,
    )


__all__ = [
    "COLLECTION_RUN_JOB_TYPE",
    "COLLECTION_RUN_PAYLOAD_VERSION",
    "CollectionRunJobExecutor",
    "CollectionRunJobHandler",
    "CollectionRunJobPayload",
    "register_collection_run_job",
]
