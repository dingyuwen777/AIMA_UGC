"""Persistent Canonical Replay 的版本化 Job 与持久运行边界。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Protocol, cast
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
CANONICAL_REPLAY_ARTIFACTS_PER_RUN: Final[Literal[100]] = 100
CANONICAL_REPLAY_FAST_BATCH_SIZE: Final[Literal[1000]] = 1000
CANONICAL_REPLAY_REVERSAL_JOB_TYPE = "ingestion.canonical-replay-reversal.v1"
CANONICAL_REPLAY_REVERSAL_JOB_PAYLOAD_VERSION = "ingestion.canonical-replay-reversal.v1"

CanonicalReplaySourceKind = Literal[
    "excel_import_v2",
    "data_import_canonical_chunk_v2",
    "tikhub_search_attempt_v1",
]
CanonicalReplayLifecycleStatus = Literal[
    "active",
    "cancelling",
    "reverting",
    "reverted",
    "revert_failed",
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
class CanonicalReplayAllRequestRecord:
    """一次全历史 Replay 请求冻结的输入清单摘要。"""

    id: UUID
    client_idempotency_key: str
    selection_digest: str
    artifact_count: int
    run_count: int
    artifacts_per_run: int
    batch_size: int
    created_by: str
    created_at: datetime
    reversible: bool
    lifecycle_status: CanonicalReplayLifecycleStatus
    reversal_job_id: UUID | None
    cancellation_requested_at: datetime | None
    reversal_requested_at: datetime | None
    reversed_at: datetime | None
    reversal_requested_by: str | None
    reversal_request_id: str | None
    reverted_content_count: int
    hidden_content_count: int
    retained_content_count: int
    skipped_content_count: int
    restored_evidence_count: int
    skipped_evidence_count: int


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
    all_request_id: UUID | None = None
    all_request_ordinal: int | None = None


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


class CanonicalReplayReversalJobPayload(BaseModel):
    """异步撤回只携带父请求身份，贡献账本留在数据库。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ingestion.canonical-replay-reversal.v1"] = (
        "ingestion.canonical-replay-reversal.v1"
    )
    request_id: UUID


class CanonicalReplayJobExecutor(Protocol):
    """在当前 Fence 下执行可恢复 Replay。"""

    def execute(
        self,
        *,
        payload: CanonicalReplayJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class CanonicalReplayReversalJobExecutor(Protocol):
    """在当前 Fence 下逆序撤回一个全历史 Replay 的已提交贡献。"""

    def execute(
        self,
        *,
        payload: CanonicalReplayReversalJobPayload,
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


class CanonicalReplayReversalJobHandler:
    """把统一 Job Runtime 委托给 Replay 撤回执行器。"""

    def __init__(self, executor: CanonicalReplayReversalJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, CanonicalReplayReversalJobPayload):
            raise TypeError("Canonical Replay Reversal Handler 收到错误 Payload 类型")
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


def register_canonical_replay_reversal_job(
    registry: JobRegistry,
    handler: CanonicalReplayReversalJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册可恢复、可重试的 Replay 撤回 Job。"""

    registry.register(
        job_type=CANONICAL_REPLAY_REVERSAL_JOB_TYPE,
        payload_version=CANONICAL_REPLAY_REVERSAL_JOB_PAYLOAD_VERSION,
        payload_model=CanonicalReplayReversalJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "CANONICAL_REPLAY_ARTIFACTS_PER_RUN",
    "CANONICAL_REPLAY_FAST_BATCH_SIZE",
    "CANONICAL_REPLAY_JOB_MAX_ATTEMPTS",
    "CANONICAL_REPLAY_JOB_PAYLOAD_VERSION",
    "CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS",
    "CANONICAL_REPLAY_JOB_TYPE",
    "CANONICAL_REPLAY_REVERSAL_JOB_PAYLOAD_VERSION",
    "CANONICAL_REPLAY_REVERSAL_JOB_TYPE",
    "CanonicalReplayArtifactRecord",
    "CanonicalReplayAllRequestRecord",
    "CanonicalReplayCounters",
    "CanonicalReplayLifecycleStatus",
    "CanonicalReplayJobExecutor",
    "CanonicalReplayJobHandler",
    "CanonicalReplayJobPayload",
    "CanonicalReplayReversalJobExecutor",
    "CanonicalReplayReversalJobHandler",
    "CanonicalReplayReversalJobPayload",
    "CanonicalReplayRunRecord",
    "CanonicalReplaySourceKind",
    "dump_filter_snapshot",
    "load_filter_snapshot",
    "register_canonical_replay_job",
    "register_canonical_replay_reversal_job",
]
