"""管理员飞书发布 API 的稳定 HTTP Contract。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from aima_ugc.contracts.base import AimaHttpModel as BaseModel

FeishuPublicationKind = Literal["report", "representative_selection"]
FeishuPublicationStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class FeishuReportPublicationResult(BaseModel):
    """报告发布成功后的安全结果；不暴露本地临时路径或 Secret。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["report"] = "report"
    dry_run: bool = False
    native_document_url: str | None = None
    editable_chart_sheet_url: str | None = None
    representative_table_url: str | None = None
    representative_table_name: str | None = None
    representative_count: int = Field(default=0, ge=0)
    representative_created_count: int = Field(default=0, ge=0)
    representative_updated_count: int = Field(default=0, ge=0)
    representative_verified_count: int = Field(default=0, ge=0)
    content_rows: int = Field(ge=0)
    label_rows: int = Field(ge=0)
    comment_rows: int = Field(ge=0)
    start_date: date
    end_date: date


class FeishuRepresentativeSelectionResult(BaseModel):
    """代表性筛选多维表发布后的安全结果。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["representative_selection"] = "representative_selection"
    target_table_id: str
    target_table_name: str
    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    verified_count: int = Field(ge=0)
    verification_errors: tuple[str, ...] = ()


FeishuPublicationResult = FeishuReportPublicationResult | FeishuRepresentativeSelectionResult


class FeishuPublicationCreatedResponse(BaseModel):
    """管理员发布请求入队后的 202 响应。"""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    kind: FeishuPublicationKind
    status: Literal["queued"] = "queued"


class FeishuPublicationJobResponse(BaseModel):
    """管理员发布任务查询响应。"""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: FeishuPublicationKind
    status: FeishuPublicationStatus
    attempt: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    progress: int = Field(ge=0, le=100)
    error_code: str | None = None
    source_filenames: tuple[str, ...] = ()
    result: FeishuPublicationResult | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


__all__ = [
    "FeishuPublicationCreatedResponse",
    "FeishuPublicationJobResponse",
    "FeishuPublicationKind",
    "FeishuPublicationResult",
    "FeishuPublicationStatus",
    "FeishuReportPublicationResult",
    "FeishuRepresentativeSelectionResult",
]
