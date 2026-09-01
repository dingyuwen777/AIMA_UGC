"""Excel Import Job 的版本化 Payload 与共享 Runtime 注册。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import (
    JobExecutionFence,
    JobHandlerResult,
    JobRecord,
    JobRegistry,
)
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

IMPORT_JOB_TYPE = "ingestion.import-excel.v1"
IMPORT_JOB_PAYLOAD_VERSION = "ingestion.import-excel.v1"
IMPORT_JOB_TIMEOUT_SECONDS = 1800
IMPORT_JOB_MAX_ATTEMPTS = 10


class ImportKeywordPackSnapshot(BaseModel):
    """一次 Excel Import 创建时冻结的词包版本身份。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version: int = Field(gt=0)


class ImportVehicleModelSnapshot(BaseModel):
    """一次 Import 创建时冻结的车型版本和非歧义别名。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version: int = Field(gt=0)
    aliases: tuple[str, ...] = Field(min_length=1)


class ImportKeywordSelectionSnapshot(BaseModel):
    """Excel Import 使用的多词包并集快照；Worker 不再读取实时词包。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["import-keyword-selection.v1"] = "import-keyword-selection.v1"
    keyword_packs: tuple[ImportKeywordPackSnapshot, ...] = Field(default=(), max_length=20)
    effective_keywords: tuple[str, ...] = ()
    vehicle_catalog_version: int = Field(default=1, gt=0)
    vehicle_models: tuple[ImportVehicleModelSnapshot, ...] = Field(default=(), max_length=100)
    match_mode: Literal["keyword_or_x_vehicle_or"] = "keyword_or_x_vehicle_or"

    @model_validator(mode="after")
    def validate_dimensions(self) -> ImportKeywordSelectionSnapshot:
        """至少选择一个资源维度，并保持词包与关键词同时存在。"""

        if not self.keyword_packs and not self.vehicle_models:
            raise ValueError("Import 至少需要一个词包或车型")
        if bool(self.keyword_packs) != bool(self.effective_keywords):
            raise ValueError("词包与 effective_keywords 必须同时存在")
        return self


class ImportJobPayload(BaseModel):
    """冻结 Excel Import 创建时选择的多词包执行快照。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.import-excel.v1"] = "ingestion.import-excel.v1"
    keyword_selection: ImportKeywordSelectionSnapshot


class ImportJobExecutor(Protocol):
    """正式 Excel Import 业务执行器边界。"""

    def execute(
        self,
        *,
        payload: ImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ImportJobHandler:
    """从当前 Job Fence 进入 Import 链路；Executor 再核对 Payload 与 Batch。"""

    def __init__(self, executor: ImportJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, ImportJobPayload):
            raise TypeError("Import Job Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_import_job(
    registry: JobRegistry,
    handler: ImportJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """把 Excel Import 注册到现有 PostgreSQL Job Runtime。"""

    registry.register(
        job_type=IMPORT_JOB_TYPE,
        payload_version=IMPORT_JOB_PAYLOAD_VERSION,
        payload_model=ImportJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "IMPORT_JOB_MAX_ATTEMPTS",
    "IMPORT_JOB_PAYLOAD_VERSION",
    "IMPORT_JOB_TIMEOUT_SECONDS",
    "IMPORT_JOB_TYPE",
    "ImportJobExecutor",
    "ImportJobHandler",
    "ImportJobPayload",
    "ImportKeywordPackSnapshot",
    "ImportKeywordSelectionSnapshot",
    "ImportVehicleModelSnapshot",
    "register_import_job",
]
