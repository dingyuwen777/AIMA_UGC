"""Replay Run 内分片 Job 的版本化 Payload。"""

from __future__ import annotations

from collections.abc import Callable
from math import ceil
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

from .canonical_replay import CANONICAL_REPLAY_BACKGROUND_PRIORITY

REPLAY_SHARD_JOB_TYPE = "ingestion.canonical-replay-shard.v1"
REPLAY_SHARD_JOB_PRIORITY = CANONICAL_REPLAY_BACKGROUND_PRIORITY


def select_replay_shard_count(
    *,
    compressed_bytes: int,
    available_workers: int,
    sampled_rows: int,
    matched_rows: int,
) -> int:
    """输入要足够大且预检样本主要需入库，才承担每片重读输入的成本。"""

    if (
        compressed_bytes < 0
        or available_workers < 1
        or sampled_rows < 0
        or not 0 <= matched_rows <= sampled_rows
    ):
        raise ValueError("Replay 输入大小、Worker 预算或样本计数无效")
    by_input_size = ceil(compressed_bytes / (2 * 1024 * 1024))
    # 每片重新校验并解析全部压缩输入；低命中率实测会让并行反而变慢。
    if (
        available_workers < 2
        or by_input_size < 3
        or sampled_rows < 64
        or matched_rows * 2 < sampled_rows
    ):
        return 1
    return min(available_workers * 2, by_input_size)


class CanonicalReplayShardJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shard_id: UUID


class CanonicalReplayShardExecutor(Protocol):
    def execute_child(
        self, *, shard_id: UUID, fence: JobExecutionFence, context: JobExecutionContextProtocol
    ) -> JobHandlerResult: ...


class CanonicalReplayShardJobHandler:
    def __init__(self, executor: CanonicalReplayShardExecutor) -> None:
        self._executor = executor

    def __call__(
        self, payload: BaseModel, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        if not isinstance(payload, CanonicalReplayShardJobPayload):
            raise TypeError("Canonical Replay 分片 Payload 类型不匹配")
        return self._executor.execute_child(
            shard_id=payload.shard_id, fence=context.fence, context=context
        )


def register_replay_shard_job(
    registry: JobRegistry,
    handler: CanonicalReplayShardJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    registry.register(
        job_type=REPLAY_SHARD_JOB_TYPE,
        payload_version=REPLAY_SHARD_JOB_TYPE,
        payload_model=CanonicalReplayShardJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "CanonicalReplayShardJobHandler",
    "CanonicalReplayShardJobPayload",
    "REPLAY_SHARD_JOB_PRIORITY",
    "register_replay_shard_job",
    "select_replay_shard_count",
]
