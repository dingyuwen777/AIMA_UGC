"""Excel Import Job 的版本化 Payload 与共享 Runtime 注册。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aima_ugc.contracts.analysis import RelevanceSnapshotV1
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


class ImportKeywordSelectionSnapshot(BaseModel):
    """Excel Import 使用的多词包并集快照；Worker 不再读取实时词包。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["import-keyword-selection.v1"] = "import-keyword-selection.v1"
    keyword_packs: tuple[ImportKeywordPackSnapshot, ...] = Field(min_length=1, max_length=20)
    effective_keywords: tuple[str, ...] = Field(min_length=1)


class ImportJobPayload(BaseModel):
    """兼容旧单词包 Job；新任务使用 keyword_selection 冻结执行输入。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.import-excel.v1"] = "ingestion.import-excel.v1"
    relevance: RelevanceSnapshotV1 | None = None
    keyword_selection: ImportKeywordSelectionSnapshot | None = None

    @model_validator(mode="after")
    def validate_snapshot(self) -> ImportJobPayload:
        if (self.relevance is None) == (self.keyword_selection is None):
            raise ValueError("Import Job 必须且只能冻结一种关键词快照")
        return self


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
    "register_import_job",
]
