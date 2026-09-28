"""数据导入撤销的持久 Job Contract 与注册入口。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

DATA_IMPORT_REVOCATION_JOB_TYPE = "ingestion.data-import-revocation.v1"


class DataImportRevocationJobPayload(BaseModel):
    """只携带持久请求身份；原因和操作者保存在撤销事实，不进 Job Payload。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID


class DataImportRevocationJobExecutor(Protocol):
    """Job Handler 调用的撤销执行边界。"""

    def execute(
        self,
        *,
        payload: DataImportRevocationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class DataImportRevocationJobHandler:
    """把统一 Job Runtime 委托给数据导入撤销执行器。"""

    def __init__(self, executor: DataImportRevocationJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, DataImportRevocationJobPayload):
            raise TypeError("Data Import Revocation Handler 收到错误 Payload 类型")
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_data_import_revocation_job(
    registry: JobRegistry,
    handler: DataImportRevocationJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册可重试、可接管的导入撤销 Job。"""

    registry.register(
        job_type=DATA_IMPORT_REVOCATION_JOB_TYPE,
        payload_version=DATA_IMPORT_REVOCATION_JOB_TYPE,
        payload_model=DataImportRevocationJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "DATA_IMPORT_REVOCATION_JOB_TYPE",
    "DataImportRevocationJobHandler",
    "DataImportRevocationJobPayload",
    "register_data_import_revocation_job",
]
