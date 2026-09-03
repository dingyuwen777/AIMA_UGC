"""显式 Content Analysis 的版本化 durable Job。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

CONTENT_ANALYSIS_JOB_TYPE = "analysis.content-label.v1"
CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION = "analysis.content-label.v1"
CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS = 1800
CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS = 3
CONTENT_ANALYSIS_PLAN_JOB_TYPE = "analysis.content-run-plan.v1"
CONTENT_ANALYSIS_PLAN_JOB_PAYLOAD_VERSION = "analysis.content-run-plan.v1"
CONTENT_ANALYSIS_PLAN_JOB_TIMEOUT_SECONDS = 1800
CONTENT_ANALYSIS_PLAN_JOB_MAX_ATTEMPTS = 3

_ANALYSIS_ALL_SCOPE_MARKER_KEY = "__analysis_scope"
_ANALYSIS_ALL_SCOPE_MARKER_VALUE = "all"


def analysis_all_scope_filter_snapshot() -> dict[str, object]:
    """返回只供 Analysis Run 持久化使用的公开 all Scope 内部标记。"""

    return {_ANALYSIS_ALL_SCOPE_MARKER_KEY: _ANALYSIS_ALL_SCOPE_MARKER_VALUE}


def is_analysis_all_scope_filter_snapshot(value: object) -> bool:
    """只识别新 all Run 的专用标记，不重解释历史空 query 快照。"""

    return value == analysis_all_scope_filter_snapshot()


class ContentAnalysisJobPayload(BaseModel):
    """业务选择已冻结到 Analysis Request；Payload 只携带稳定父 ID。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["analysis.content-label.v1"] = "analysis.content-label.v1"
    request_id: UUID
    run_id: UUID | None = None
    shard_no: int | None = None


class ContentAnalysisPlanJobPayload(BaseModel):
    """Planner 在数据库冻结 Run 目标，并创建有界数量的 Shard Job。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["analysis.content-run-plan.v1"] = "analysis.content-run-plan.v1"
    run_id: UUID


class ContentAnalysisJobExecutor(Protocol):
    def execute(
        self,
        *,
        payload: ContentAnalysisJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ContentAnalysisPlanJobExecutor(Protocol):
    def execute_plan(
        self,
        *,
        payload: ContentAnalysisPlanJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class ContentAnalysisJobHandler:
    def __init__(self, executor: ContentAnalysisJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, ContentAnalysisJobPayload):
            raise TypeError("Content Analysis Job Handler 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute(payload=payload, fence=context.fence, context=context)


class ContentAnalysisPlanJobHandler:
    def __init__(self, executor: ContentAnalysisPlanJobExecutor) -> None:
        self._executor = executor

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, ContentAnalysisPlanJobPayload):
            raise TypeError("Content Analysis Planner 收到错误 Payload 类型")
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        return self._executor.execute_plan(payload=payload, fence=context.fence, context=context)


def register_content_analysis_job(
    registry: JobRegistry,
    handler: ContentAnalysisJobHandler,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
    planner_handler: ContentAnalysisPlanJobHandler | None = None,
    planner_terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    registry.register(
        job_type=CONTENT_ANALYSIS_JOB_TYPE,
        payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
        payload_model=ContentAnalysisJobPayload,
        handler=handler,
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
    if planner_handler is not None:
        registry.register(
            job_type=CONTENT_ANALYSIS_PLAN_JOB_TYPE,
            payload_version=CONTENT_ANALYSIS_PLAN_JOB_PAYLOAD_VERSION,
            payload_model=ContentAnalysisPlanJobPayload,
            handler=planner_handler,
            retry_on_timeout=True,
            terminal_callback=planner_terminal_callback,
        )


__all__ = [
    "CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS",
    "CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION",
    "CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS",
    "CONTENT_ANALYSIS_JOB_TYPE",
    "CONTENT_ANALYSIS_PLAN_JOB_MAX_ATTEMPTS",
    "CONTENT_ANALYSIS_PLAN_JOB_PAYLOAD_VERSION",
    "CONTENT_ANALYSIS_PLAN_JOB_TIMEOUT_SECONDS",
    "CONTENT_ANALYSIS_PLAN_JOB_TYPE",
    "ContentAnalysisJobExecutor",
    "ContentAnalysisJobHandler",
    "ContentAnalysisJobPayload",
    "ContentAnalysisPlanJobExecutor",
    "ContentAnalysisPlanJobHandler",
    "ContentAnalysisPlanJobPayload",
    "analysis_all_scope_filter_snapshot",
    "is_analysis_all_scope_filter_snapshot",
    "register_content_analysis_job",
]
