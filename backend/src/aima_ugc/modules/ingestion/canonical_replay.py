"""Persistent Canonical Replay 的版本化 Job 与持久运行边界。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

from .brand_vehicle_filter import BrandVehicleFilterSnapshot

CANONICAL_REPLAY_JOB_TYPE = "ingestion.canonical-replay.v1"
CANONICAL_REPLAY_JOB_PAYLOAD_VERSION = "ingestion.canonical-replay.v1"
CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS = 86_400
CANONICAL_REPLAY_JOB_MAX_ATTEMPTS = 10

CanonicalReplaySourceKind = Literal[
    "excel_import_v2",
    "data_import_canonical_chunk_v2",
    "tikhub_search_attempt_v1",
]

_FILTER_SNAPSHOT_ADAPTER = TypeAdapter(BrandVehicleFilterSnapshot)


@dataclass(frozen=True, slots=True)
class CanonicalReplayArtifactRecord:
    """一个按稳定顺序冻结的 Replay 输入。"""

    run_id: UUID
    ordinal: int
    artifact_id: UUID
    source_kind: CanonicalReplaySourceKind


@dataclass(frozen=True, slots=True)
class CanonicalReplayRunRecord:
    """Replay 的冻结输入、检查点与累计对账统计。"""

    id: UUID
    job_id: UUID
    client_idempotency_key: str
    filter_snapshot: BrandVehicleFilterSnapshot
    requested_brand_ids: tuple[UUID, ...]
    artifact_count: int
    checkpoint_artifact_ordinal: int
    checkpoint_row_number: int
    batch_size: int
    rows_seen: int
    rows_matched: int
    rows_filtered_out: int
    duplicates_removed: int
    rows_ingested: int
    existing_convergence: int
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CanonicalReplayCounters:
    """一个已提交批次的统计增量。"""

    rows_seen: int
    rows_matched: int
    rows_filtered_out: int
    duplicates_removed: int
    rows_ingested: int
    existing_convergence: int


def dump_filter_snapshot(snapshot: BrandVehicleFilterSnapshot) -> dict[str, object]:
    """把冻结 Filter Snapshot 编码为 JSONB 安全结构。"""

    return cast(
        dict[str, object],
        _FILTER_SNAPSHOT_ADAPTER.dump_python(snapshot, mode="json"),
    )


def load_filter_snapshot(value: object) -> BrandVehicleFilterSnapshot:
    """从 JSONB 严格恢复冻结 Filter Snapshot。"""

    return _FILTER_SNAPSHOT_ADAPTER.validate_python(value)


class CanonicalReplayJobPayload(BaseModel):
    """Job 只携带稳定 Run 身份；大输入和快照保存在 Ingestion Owner 表。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.canonical-replay.v1"] = "ingestion.canonical-replay.v1"
    run_id: UUID


class CanonicalReplayJobExecutor(Protocol):
    """在当前 Fence 下执行可恢复 Replay。"""

    def execute(
        self,
        *,
        payload: CanonicalReplayJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class CanonicalReplayJobHandler:
    """把 Platform Job Runtime 委托给 Canonical Replay 执行器。"""

    def __init__(self, executor: CanonicalReplayJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, CanonicalReplayJobPayload):
            raise TypeError("Canonical Replay Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


def register_canonical_replay_job(
    registry: JobRegistry,
    handler: CanonicalReplayJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册支持 Deadline 重试和统一终态的 Replay Job。"""

    registry.register(
        job_type=CANONICAL_REPLAY_JOB_TYPE,
        payload_version=CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
        payload_model=CanonicalReplayJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "CANONICAL_REPLAY_JOB_MAX_ATTEMPTS",
    "CANONICAL_REPLAY_JOB_PAYLOAD_VERSION",
    "CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS",
    "CANONICAL_REPLAY_JOB_TYPE",
    "CanonicalReplayArtifactRecord",
    "CanonicalReplayCounters",
    "CanonicalReplayJobExecutor",
    "CanonicalReplayJobHandler",
    "CanonicalReplayJobPayload",
    "CanonicalReplayRunRecord",
    "CanonicalReplaySourceKind",
    "dump_filter_snapshot",
    "load_filter_snapshot",
    "register_canonical_replay_job",
]
