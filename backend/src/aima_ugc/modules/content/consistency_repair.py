"""有界历史一致性修复的 Content Owner 与版本化 Job 边界。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.modules.vehicles.brand_vehicle import BrandVehicleCatalogSnapshot
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

CONTENT_CONSISTENCY_REPAIR_JOB_TYPE: Literal["content.consistency-repair.v1"] = (
    "content.consistency-repair.v1"
)
CONTENT_CONSISTENCY_REPAIR_MAX_CONTENTS = 10_000


@dataclass(frozen=True, slots=True)
class ContentConsistencyRepairRun:
    """冻结目录、显式目标范围、已提交检查点与累计进度。"""

    id: UUID
    job_id: UUID
    catalog_snapshot: BrandVehicleCatalogSnapshot
    source_collection_run_id: UUID | None
    checkpoint_content_id: UUID | None
    batch_size: int
    max_contents: int
    target_count: int
    processed_count: int
    candidate_count: int
    brand_changed_count: int
    reused_count: int
    existing_reuse_count: int
    unmatched_count: int
    analysis_reasons: dict[str, int]
    created_by: str
    created_at: datetime
    updated_at: datetime


class ContentConsistencyRepairPayload(BaseModel):
    """只传递稳定 Run 身份；旧 Worker 不会领取新 Job type。"""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["content.consistency-repair.v1"] = CONTENT_CONSISTENCY_REPAIR_JOB_TYPE
    run_id: UUID


class ContentConsistencyRepairExecutor(Protocol):
    """复用统一 Job Runtime 执行可恢复短事务批次。"""

    def execute(
        self,
        *,
        payload: ContentConsistencyRepairPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ContentConsistencyRepairHandler:
    """将 Job 的取消与 Fence 交给唯一生产执行器。"""

    def __init__(self, executor: ContentConsistencyRepairExecutor) -> None:
        """绑定生产修复执行器。"""
        self._executor = executor

    def __call__(
        self, payload: BaseModel, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        """取消优先，禁止把错误协议当成已完成修复。"""
        if not isinstance(payload, ContentConsistencyRepairPayload):
            raise TypeError("Content Consistency Repair 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_content_consistency_repair_job(
    registry: JobRegistry,
    handler: ContentConsistencyRepairHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册新协议，不复用旧重分类 Job 的语义。"""
    registry.register(
        job_type=CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,
        payload_version=CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,
        payload_model=ContentConsistencyRepairPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
