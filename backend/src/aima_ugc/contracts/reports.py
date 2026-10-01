"""数据库报告的管理员 HTTP 契约。"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from aima_ugc.contracts.base import AimaHttpModel
from aima_ugc.contracts.http import JobStatusResponse


class ReportSubmitRequest(AimaHttpModel):
    """品牌、可选车型与包含首尾日期的北京时间报告范围。"""

    model_config = ConfigDict(extra="forbid")
    brand_id: UUID
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_scope(self) -> ReportSubmitRequest:
        """拒绝倒置范围及重复车型，防止生成歧义快照。"""
        if self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        if len(set(self.vehicle_model_ids)) != len(self.vehicle_model_ids):
            raise ValueError("车型不能重复")
        return self


class ReportPreflightResponse(AimaHttpModel):
    """实时预检只描述当前事实，创建时会再次检查并冻结。"""

    content_count: int
    previous_content_count: int
    analyzed_count: int
    real_user_count: int
    comment_count: int
    model: str | None
    provider: str | None
    prompt_version: str
    taxonomy_sha256: str
    ready: bool
    warnings: tuple[str, ...] = ()


class ReportArtifactResponse(AimaHttpModel):
    """下载只使用报告内 Artifact 身份，不暴露存储路径。"""

    artifact_id: UUID
    artifact_type: str
    filename: str
    content_type: str
    byte_size: int
    download_url: str


class ReportJobResponse(JobStatusResponse):
    """暴露下一次计划领取时间，让过载重试有可见进度。"""

    available_at: datetime
    timeout_seconds: int
    cancel_requested: bool


class ReportAnalysisBasisResponse(AimaHttpModel):
    """按周期汇总实际采用的历史分析身份，不回显正文或模型输出。"""

    period: Literal["current", "previous"]
    scheme_version_id: UUID
    prompt_version: str
    prompt_sha256: str
    taxonomy_sha256: str
    provider: str
    model: str
    content_count: int
    manual_override_count: int


class ReportResponse(AimaHttpModel):
    """生成与发布分别展示 Job 状态，发布失败不影响已生成文件。"""

    id: UUID
    name: str
    brand_id: UUID
    vehicle_model_ids: tuple[UUID, ...]
    start_date: date
    end_date: date
    status: Literal[
        "queued", "generating", "generated", "published", "failed", "cancelled", "expired"
    ]
    generation_job: ReportJobResponse
    publication_job: ReportJobResponse | None = None
    files: tuple[ReportArtifactResponse, ...] = ()
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    model: str
    prompt_version: str
    provider_config_id: UUID
    provider_revision: int
    scheme_version_id: UUID
    prompt_sha256: str
    taxonomy_sha256: str
    selection_prompt_sha256: str
    analysis_bases: tuple[ReportAnalysisBasisResponse, ...] = ()
    content_count: int
    publication_enabled: bool
    native_document_url: str | None = None
    editable_chart_sheet_url: str | None = None
    representative_table_url: str | None = None


class ReportListResponse(AimaHttpModel):
    """按创建时间降序列出最近报告。"""

    items: tuple[ReportResponse, ...]
