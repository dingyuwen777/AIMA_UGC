"""管理员飞书发布 Job 的版本化 Payload 与注册边界。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

FEISHU_REPORT_PUBLICATION_JOB_TYPE = "administration.feishu-report-publication.v1"
FEISHU_REPORT_PUBLICATION_PAYLOAD_VERSION = "administration.feishu-report-publication.v1"
FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE = "administration.feishu-representative-selection.v1"
FEISHU_REPRESENTATIVE_SELECTION_PAYLOAD_VERSION = (
    "administration.feishu-representative-selection.v1"
)
FEISHU_PUBLICATION_TIMEOUT_SECONDS = 1800
FEISHU_PUBLICATION_MAX_ATTEMPTS = 3


class FeishuReportPublicationJobPayload(BaseModel):
    """报告发布 Job 的完整输入快照；不依赖单独业务表。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["administration.feishu-report-publication.v1"] = (
        "administration.feishu-report-publication.v1"
    )
    input_artifact_id: UUID
    previous_input_artifact_id: UUID
    input_filename: str = Field(min_length=1, max_length=255)
    previous_input_filename: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    dry_run: bool = True
    # Worker 在外部副作用成功后写回的 durable resource identities。
    # 允许为空以兼容已经入队但尚未开始执行的旧 Job。
    publication_checkpoint: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_date_range(self) -> FeishuReportPublicationJobPayload:
        if self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


class FeishuRepresentativeSelectionJobPayload(BaseModel):
    """代表性筛选发布 Job 的完整输入快照。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["administration.feishu-representative-selection.v1"] = (
        "administration.feishu-representative-selection.v1"
    )
    input_artifact_id: UUID
    input_filename: str = Field(min_length=1, max_length=255)


class FeishuPublicationJobExecutor(Protocol):
    """Worker 对两个发布用例的最小执行边界。"""

    def execute_report(
        self,
        *,
        payload: FeishuReportPublicationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...

    def execute_representative_selection(
        self,
        *,
        payload: FeishuRepresentativeSelectionJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class FeishuReportPublicationJobHandler:
    def __init__(self, executor: FeishuPublicationJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, FeishuReportPublicationJobPayload):
            raise TypeError("报告发布 Job Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute_report(
            payload=payload,
            fence=context.fence,
            context=context,
        )


class FeishuRepresentativeSelectionJobHandler:
    def __init__(self, executor: FeishuPublicationJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, FeishuRepresentativeSelectionJobPayload):
            raise TypeError("代表性筛选发布 Job Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute_representative_selection(
            payload=payload,
            fence=context.fence,
            context=context,
        )


def register_feishu_publication_jobs(
    registry: JobRegistry,
    executor: FeishuPublicationJobExecutor,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    """注册两个相互独立的发布 Job，不增加第二套队列。"""

    registry.register(
        job_type=FEISHU_REPORT_PUBLICATION_JOB_TYPE,
        payload_version=FEISHU_REPORT_PUBLICATION_PAYLOAD_VERSION,
        payload_model=FeishuReportPublicationJobPayload,
        handler=FeishuReportPublicationJobHandler(executor),
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
    registry.register(
        job_type=FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE,
        payload_version=FEISHU_REPRESENTATIVE_SELECTION_PAYLOAD_VERSION,
        payload_model=FeishuRepresentativeSelectionJobPayload,
        handler=FeishuRepresentativeSelectionJobHandler(executor),
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "FEISHU_PUBLICATION_MAX_ATTEMPTS",
    "FEISHU_PUBLICATION_TIMEOUT_SECONDS",
    "FEISHU_REPORT_PUBLICATION_JOB_TYPE",
    "FEISHU_REPORT_PUBLICATION_PAYLOAD_VERSION",
    "FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE",
    "FEISHU_REPRESENTATIVE_SELECTION_PAYLOAD_VERSION",
    "FeishuPublicationJobExecutor",
    "FeishuReportPublicationJobHandler",
    "FeishuReportPublicationJobPayload",
    "FeishuRepresentativeSelectionJobHandler",
    "FeishuRepresentativeSelectionJobPayload",
    "register_feishu_publication_jobs",
]
