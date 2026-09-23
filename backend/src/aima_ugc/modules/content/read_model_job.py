"""声音广场历史投影回填的版本化持久 Job 边界。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import (
    JobExecutionFence,
    JobHandlerResult,
    JobRecord,
    JobRegistry,
)
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

VOICE_PLAZA_PROJECTION_JOB_TYPE = "content.voice-plaza-projection-backfill.v1"
VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION = "content.voice-plaza-projection-backfill.v1"
VOICE_PLAZA_PROJECTION_JOB_PRIORITY = -50
VOICE_PLAZA_PROJECTION_JOB_TIMEOUT_SECONDS = 1_800
VOICE_PLAZA_PROJECTION_JOB_MAX_ATTEMPTS = 10


class VoicePlazaProjectionJobPayload(BaseModel):
    """回填游标保存在 Content Owner 状态表，Payload 只冻结协议版本。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["content.voice-plaza-projection-backfill.v1"] = (
        "content.voice-plaza-projection-backfill.v1"
    )
    generation: int = Field(ge=1)


class VoicePlazaProjectionJobExecutor(Protocol):
    """在当前 Fence 下分批推进声音广场投影。"""

    def execute(
        self,
        *,
        payload: VoicePlazaProjectionJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class VoicePlazaProjectionJobHandler:
    """把统一 Job Runtime 委托给 Content 投影回填执行器。"""

    def __init__(self, executor: VoicePlazaProjectionJobExecutor) -> None:
        """绑定唯一生产执行器。"""

        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """先收敛取消，再携带当前 Fencing Token 执行。"""

        if not isinstance(payload, VoicePlazaProjectionJobPayload):
            raise TypeError("Voice Plaza Projection Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(
            payload=payload,
            fence=context.fence,
            context=context,
        )


def register_voice_plaza_projection_job(
    registry: JobRegistry,
    handler: VoicePlazaProjectionJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册可由 Deadline 接管重试、终态串接下一切片的分块回填 Job。"""

    registry.register(
        job_type=VOICE_PLAZA_PROJECTION_JOB_TYPE,
        payload_version=VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION,
        payload_model=VoicePlazaProjectionJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "VOICE_PLAZA_PROJECTION_JOB_MAX_ATTEMPTS",
    "VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION",
    "VOICE_PLAZA_PROJECTION_JOB_PRIORITY",
    "VOICE_PLAZA_PROJECTION_JOB_TIMEOUT_SECONDS",
    "VOICE_PLAZA_PROJECTION_JOB_TYPE",
    "VoicePlazaProjectionJobExecutor",
    "VoicePlazaProjectionJobHandler",
    "VoicePlazaProjectionJobPayload",
    "register_voice_plaza_projection_job",
]
