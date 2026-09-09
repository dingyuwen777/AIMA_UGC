"""Excel Import Job 的版本化 Payload 与共享 Runtime 注册。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.platform.jobs import (
    JobExecutionFence,
    JobHandlerResult,
    JobRecord,
    JobRegistry,
)
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

# v1 常量继续保留给升级前已经持久化的 queued/running Job。
IMPORT_JOB_TYPE = "ingestion.import-excel.v1"
IMPORT_JOB_PAYLOAD_VERSION = "ingestion.import-excel.v1"
LEGACY_IMPORT_JOB_TYPE = IMPORT_JOB_TYPE
LEGACY_IMPORT_JOB_PAYLOAD_VERSION = IMPORT_JOB_PAYLOAD_VERSION
BRAND_VEHICLE_IMPORT_JOB_TYPE = "ingestion.import-excel.v2"
BRAND_VEHICLE_IMPORT_JOB_PAYLOAD_VERSION = "ingestion.import-excel.v2"
IMPORT_JOB_TIMEOUT_SECONDS = 1800
IMPORT_JOB_MAX_ATTEMPTS = 10


class ImportKeywordPackSnapshot(BaseModel):
    """一次 legacy Excel Import 创建时冻结的词包版本身份。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version: int = Field(gt=0)


class ImportVehicleModelSnapshot(BaseModel):
    """一次 legacy Import 创建时冻结的车型版本和非歧义别名。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version: int = Field(gt=0)
    aliases: tuple[str, ...] = Field(min_length=1)


class ImportKeywordSelectionSnapshot(BaseModel):
    """升级前 Excel Import 的 Keyword/Vehicle 选择快照；仅用于兼容既有任务。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["import-keyword-selection.v1"] = "import-keyword-selection.v1"
    keyword_packs: tuple[ImportKeywordPackSnapshot, ...] = Field(default=(), max_length=20)
    effective_keywords: tuple[str, ...] = ()
    vehicle_catalog_version: int = Field(default=1, gt=0)
    vehicle_models: tuple[ImportVehicleModelSnapshot, ...] = Field(default=(), max_length=100)
    match_mode: Literal["keyword_or_x_vehicle_or"] = "keyword_or_x_vehicle_or"

    @model_validator(mode="after")
    def validate_dimensions(self) -> ImportKeywordSelectionSnapshot:
        """兼容 v1：至少选择一个资源维度，并保持词包与关键词同时存在。"""

        if not self.keyword_packs and not self.vehicle_models:
            raise ValueError("Import 至少需要一个词包或车型")
        if bool(self.keyword_packs) != bool(self.effective_keywords):
            raise ValueError("词包与 effective_keywords 必须同时存在")
        return self


class ImportJobPayload(BaseModel):
    """legacy v1 Payload；名称保持不变以保证旧 Worker 代码可继续解释。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.import-excel.v1"] = "ingestion.import-excel.v1"
    keyword_selection: ImportKeywordSelectionSnapshot


class BrandVehicleImportJobPayload(BaseModel):
    """Stage 3 v2 Payload；只携带冻结 Brand/Vehicle Filter Snapshot。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.import-excel.v2"] = "ingestion.import-excel.v2"
    filter_snapshot: BrandVehicleFilterSnapshot


type AnyImportJobPayload = ImportJobPayload | BrandVehicleImportJobPayload


class ImportJobExecutor(Protocol):
    """正式 Excel Import 业务执行器边界，同时承担 v1/v2 兼容。"""

    def execute(
        self,
        *,
        payload: AnyImportJobPayload,
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
        """按显式 Payload 类型分发，拒绝任何未注册的隐式版本升级。"""

        if not isinstance(payload, (ImportJobPayload, BrandVehicleImportJobPayload)):
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
    """并行注册 legacy v1 与 Stage 3 v2；旧任务不会被新 Payload Model 误读。"""

    registry.register(
        job_type=LEGACY_IMPORT_JOB_TYPE,
        payload_version=LEGACY_IMPORT_JOB_PAYLOAD_VERSION,
        payload_model=ImportJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
    registry.register(
        job_type=BRAND_VEHICLE_IMPORT_JOB_TYPE,
        payload_version=BRAND_VEHICLE_IMPORT_JOB_PAYLOAD_VERSION,
        payload_model=BrandVehicleImportJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "AnyImportJobPayload",
    "BRAND_VEHICLE_IMPORT_JOB_PAYLOAD_VERSION",
    "BRAND_VEHICLE_IMPORT_JOB_TYPE",
    "IMPORT_JOB_MAX_ATTEMPTS",
    "IMPORT_JOB_PAYLOAD_VERSION",
    "IMPORT_JOB_TIMEOUT_SECONDS",
    "IMPORT_JOB_TYPE",
    "LEGACY_IMPORT_JOB_PAYLOAD_VERSION",
    "LEGACY_IMPORT_JOB_TYPE",
    "BrandVehicleImportJobPayload",
    "ImportJobExecutor",
    "ImportJobHandler",
    "ImportJobPayload",
    "ImportKeywordPackSnapshot",
    "ImportKeywordSelectionSnapshot",
    "ImportVehicleModelSnapshot",
    "register_import_job",
]
