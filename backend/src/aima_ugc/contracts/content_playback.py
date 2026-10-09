"""受控同源视频播放的公共请求和状态，不向浏览器返回 CDN 来源。"""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from aima_ugc.contracts.base import AimaHttpModel

type ContentPlaybackStatus = Literal["ready", "preparing", "unavailable", "cooldown"]


class ContentMediaPlaybackPrepareRequest(AimaHttpModel):
    """用户播放或一次恢复时准备；绑定已有 Job 的观察永不创建新任务。"""

    model_config = ConfigDict(extra="forbid")
    failed_source_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    observed_job_id: UUID | None = None

    @model_validator(mode="after")
    def require_single_intent(self) -> Self:
        """观察与恢复分别具有只读和收费边界，不能合并成一个请求意图。"""
        if self.observed_job_id is not None and self.failed_source_revision is not None:
            raise ValueError("observed_job_id 与 failed_source_revision 不能同时提供")
        return self


class ContentMediaPlaybackResponse(AimaHttpModel):
    """preparing 携带 job_id；以 observed_job_id 只读轮询取得当前状态或会话。"""

    model_config = ConfigDict(extra="forbid")
    content_id: UUID
    position: int = Field(ge=0)
    status: ContentPlaybackStatus
    generation: int = Field(ge=0)
    source_revision: str
    stream_url: str | None = None
    job_id: UUID | None = None
    cooldown_until: datetime | None = None
    failure_code: str | None = None
