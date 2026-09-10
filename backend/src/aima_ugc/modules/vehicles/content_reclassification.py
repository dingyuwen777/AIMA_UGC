"""旧 Content 品牌车型重分类的版本化持久 Job 边界。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import (
    JobExecutionFence,
    JobHandlerResult,
    JobRecord,
    JobRegistry,
)
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

from .brand_vehicle import BrandVehicleCatalogSnapshot

CONTENT_RECLASSIFICATION_JOB_TYPE = "vehicles.content-reclassification.v1"
CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION = "vehicles.content-reclassification.v1"
CONTENT_RECLASSIFICATION_JOB_TIMEOUT_SECONDS = 86_400
CONTENT_RECLASSIFICATION_JOB_MAX_ATTEMPTS = 10

_CATALOG_SNAPSHOT_ADAPTER = TypeAdapter(BrandVehicleCatalogSnapshot)


@dataclass(frozen=True, slots=True)
class ContentReclassificationRunRecord:
    """重分类 Run 的冻结范围、检查点与累计对账统计。"""

    id: UUID
    job_id: UUID
    catalog_snapshot: BrandVehicleCatalogSnapshot
    shard_index: int
    shard_count: int
    start_after_content_id: UUID | None
    end_at_content_id: UUID | None
    checkpoint_content_id: UUID | None
    batch_size: int
    max_contents: int
    processed_count: int
    matched_count: int
    unmatched_count: int
    brand_evidence_count: int
    vehicle_evidence_count: int
    conflict_count: int
    brand_locked_count: int
    vehicle_locked_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ContentReclassificationCandidate:
    """一个 Current Content 及其重分类前已有的有效车型事实。"""

    content_id: UUID
    content_version: int
    title: str | None
    text: str | None
    existing_vehicle_ids: tuple[UUID, ...]
    manual_vehicle_ids: tuple[UUID, ...] | None


@dataclass(frozen=True, slots=True)
class ReclassificationBatchCounters:
    """一个已提交批次对 Run 累计统计的增量。"""

    processed_count: int
    matched_count: int
    unmatched_count: int
    brand_evidence_count: int
    vehicle_evidence_count: int
    conflict_count: int
    brand_locked_count: int
    vehicle_locked_count: int


def dump_catalog_snapshot(snapshot: BrandVehicleCatalogSnapshot) -> dict[str, object]:
    """把冻结目录编码为 JSONB 安全结构，不丢失 UUID 与时间语义。"""

    return cast(
        dict[str, object],
        _CATALOG_SNAPSHOT_ADAPTER.dump_python(snapshot, mode="json"),
    )


def load_catalog_snapshot(value: object) -> BrandVehicleCatalogSnapshot:
    """从持久化 JSONB 严格恢复冻结目录。"""

    return _CATALOG_SNAPSHOT_ADAPTER.validate_python(value)


class ContentReclassificationJobPayload(BaseModel):
    """只携带稳定 Run 身份；目录快照和检查点保存在 Vehicles Owner 表。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["vehicles.content-reclassification.v1"] = (
        "vehicles.content-reclassification.v1"
    )
    run_id: UUID


class ContentReclassificationJobExecutor(Protocol):
    """在当前 Fence 下执行可恢复重分类 Run。"""

    def execute(
        self,
        *,
        payload: ContentReclassificationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ContentReclassificationJobHandler:
    """把 Platform Job Runtime 委托给 Vehicles 重分类执行器。"""

    def __init__(self, executor: ContentReclassificationJobExecutor) -> None:
        """绑定唯一生产执行器。"""

        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """先收敛取消，再以当前 Fencing Token 进入执行器。"""

        if not isinstance(payload, ContentReclassificationJobPayload):
            raise TypeError("Content Reclassification Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_content_reclassification_job(
    registry: JobRegistry,
    handler: ContentReclassificationJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册支持 Deadline 重试和终态回调的重分类 Job。"""

    registry.register(
        job_type=CONTENT_RECLASSIFICATION_JOB_TYPE,
        payload_version=CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION,
        payload_model=ContentReclassificationJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "CONTENT_RECLASSIFICATION_JOB_MAX_ATTEMPTS",
    "CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION",
    "CONTENT_RECLASSIFICATION_JOB_TIMEOUT_SECONDS",
    "CONTENT_RECLASSIFICATION_JOB_TYPE",
    "ContentReclassificationJobExecutor",
    "ContentReclassificationJobHandler",
    "ContentReclassificationJobPayload",
    "ContentReclassificationCandidate",
    "ContentReclassificationRunRecord",
    "ReclassificationBatchCounters",
    "dump_catalog_snapshot",
    "load_catalog_snapshot",
    "register_content_reclassification_job",
]
