"""报告生成与已生成文件的飞书发布使用同一 durable Runtime。"""

from collections.abc import Callable
from typing import Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from aima_ugc.platform.jobs import JobHandlerResult, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

REPORT_GENERATION_JOB: Final = "reporting.report-generation.v1"
REPORT_PUBLICATION_JOB: Final = "reporting.report-publication.v1"
REPORT_JOB_TIMEOUT_SECONDS = 1800


class ReportGenerationPayload(BaseModel):
    """仅通过持久报告身份恢复完整生成依据。"""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["reporting.report-generation.v1"] = REPORT_GENERATION_JOB
    report_run_id: UUID


class ReportPublicationPayload(BaseModel):
    """发布只读取已提交产物，不包含模型调用参数。"""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["reporting.report-publication.v1"] = REPORT_PUBLICATION_JOB
    report_run_id: UUID


def register_report_jobs(
    registry: JobRegistry,
    *,
    generate: Callable[[ReportGenerationPayload, JobExecutionContextProtocol], JobHandlerResult],
    publish: Callable[[ReportPublicationPayload, JobExecutionContextProtocol], JobHandlerResult],
) -> None:
    """复用有界指数退避、Lease、Deadline、取消与接管。"""
    registry.register(
        job_type=REPORT_GENERATION_JOB,
        payload_version=REPORT_GENERATION_JOB,
        payload_model=ReportGenerationPayload,
        handler=cast(
            Callable[[BaseModel, JobExecutionContextProtocol], JobHandlerResult], generate
        ),
        retry_on_timeout=True,
        retry_delay_cap_seconds=300,
    )
    registry.register(
        job_type=REPORT_PUBLICATION_JOB,
        payload_version=REPORT_PUBLICATION_JOB,
        payload_model=ReportPublicationPayload,
        handler=cast(Callable[[BaseModel, JobExecutionContextProtocol], JobHandlerResult], publish),
        retry_on_timeout=True,
        retry_delay_cap_seconds=300,
    )
