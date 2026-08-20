"""统一 Excel 导出的版本化 durable Job。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

DATA_EXPORT_JOB_TYPE = "reporting.content-export-excel.v1"
DATA_EXPORT_JOB_PAYLOAD_VERSION = "reporting.content-export-excel.v1"
DATA_EXPORT_JOB_TIMEOUT_SECONDS = 1800
DATA_EXPORT_JOB_MAX_ATTEMPTS = 3
MAX_EXPORT_ARTIFACT_BYTES = 500 * 1024 * 1024


class DataExportJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reporting.content-export-excel.v1"] = (
        "reporting.content-export-excel.v1"
    )
    export_id: UUID


class DataExportJobExecutor(Protocol):
    def execute(
        self,
        *,
        payload: DataExportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class DataExportJobHandler:
    def __init__(self, executor: DataExportJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, DataExportJobPayload):
            raise TypeError("Data Export Job Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_data_export_job(
    registry: JobRegistry,
    handler: DataExportJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    registry.register(
        job_type=DATA_EXPORT_JOB_TYPE,
        payload_version=DATA_EXPORT_JOB_PAYLOAD_VERSION,
        payload_model=DataExportJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "DATA_EXPORT_JOB_MAX_ATTEMPTS",
    "DATA_EXPORT_JOB_PAYLOAD_VERSION",
    "DATA_EXPORT_JOB_TIMEOUT_SECONDS",
    "DATA_EXPORT_JOB_TYPE",
    "MAX_EXPORT_ARTIFACT_BYTES",
    "DataExportJobExecutor",
    "DataExportJobHandler",
    "DataExportJobPayload",
    "register_data_export_job",
]
