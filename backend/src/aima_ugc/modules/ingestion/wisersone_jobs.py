"""每个网站查询阶段使用同一 PG Job Runtime，正常等待不消耗失败重试。"""

from collections.abc import Callable
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

WISERSONE_JOB_TYPE: Final = "ingestion.wisersone-download.v1"
WISERSONE_TERMINAL = frozenset({"succeeded", "partial_failed", "failed", "cancelled", "attention"})


class WisersOneJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ingestion.wisersone-download.v1"] = WISERSONE_JOB_TYPE
    download_id: UUID
    step: int = Field(ge=0)
    operation: Literal["observe", "cancel"] = "observe"


def register_wisersone_job(
    registry: JobRegistry,
    handler: Callable[[BaseModel, JobExecutionContextProtocol], JobHandlerResult],
    *,
    terminal_callback: Callable[[Session, JobRecord], None],
) -> None:
    registry.register(
        job_type=WISERSONE_JOB_TYPE,
        payload_version=WISERSONE_JOB_TYPE,
        payload_model=WisersOneJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
