"""普通导入撤销与重筛撤回共用的持久分片 Job Contract。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

REVERSAL_SHARD_JOB_TYPE = "ingestion.reversal-shard.v1"
REVERSAL_TARGET_CONTENTS_PER_SHARD = 2500
REVERSAL_MIN_PARALLEL_CONTENTS = 3 * REVERSAL_TARGET_CONTENTS_PER_SHARD + 1


class ReversalShardJobPayload(BaseModel):
    """只携带业务工作单元 ID，不复制来源账本或批次状态。"""

    model_config = ConfigDict(extra="forbid")
    shard_id: UUID


class ReversalShardExecutor(Protocol):
    def execute_child(
        self,
        *,
        shard_id: UUID,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ReversalShardJobHandler:
    def __init__(self, executor: ReversalShardExecutor) -> None:
        self._executor = executor

    def __call__(
        self, payload: BaseModel, context: JobExecutionContextProtocol
    ) -> JobHandlerResult:
        if not isinstance(payload, ReversalShardJobPayload):
            raise TypeError("撤回分片 Job Payload 类型不匹配")
        return self._executor.execute_child(
            shard_id=payload.shard_id, fence=context.fence, context=context
        )


def register_reversal_shard_job(
    registry: JobRegistry,
    handler: ReversalShardJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    registry.register(
        job_type=REVERSAL_SHARD_JOB_TYPE,
        payload_version=REVERSAL_SHARD_JOB_TYPE,
        payload_model=ReversalShardJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = ["ReversalShardJobHandler", "ReversalShardJobPayload", "register_reversal_shard_job"]
