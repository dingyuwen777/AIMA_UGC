"""Import、Keyword 与 Relevance 公共 HTTP Request / Response 契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

type ImportBatchStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]

type ImportStage = Literal[
    "queued",
    "reading",
    "mapping",
    "filtering",
    "deduplicating",
    "ingesting",
    "succeeded",
    "failed",
    "cancelled",
]


class HttpErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    code: str
    message: str


class HttpErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    request_id: str
    errors: tuple[HttpErrorItem, ...] = ()


class ImportStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows_seen: int = Field(default=0, ge=0)
    rows_matched: int = Field(default=0, ge=0)
    rows_filtered_out: int = Field(default=0, ge=0)
    duplicates_removed: int = Field(default=0, ge=0)
    rows_ingested: int = Field(default=0, ge=0)
    rows_rejected: int = Field(default=0, ge=0)


class ImportJobResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    rows_ingested: int = Field(ge=0)


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job_type: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    attempt: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    progress: int = Field(ge=0, le=100)
    error_code: str | None = None
    result: ImportJobResultResponse | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ImportBatchCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    job_id: UUID
    status: Literal["queued"] = "queued"


class ImportBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    input_artifact_id: UUID
    source_filename: str | None = None
    status: ImportBatchStatus
    stage: ImportStage
    stats: ImportStatsResponse
    error_summary: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    job: JobStatusResponse


class ImportBatchListQuery(BaseModel):
    """采集运行中心的稳定筛选与 Cursor 查询契约。"""

    model_config = ConfigDict(extra="forbid")

    identifier: UUID | None = None
    status: ImportBatchStatus | None = None
    stage: ImportStage | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("created_from", "created_to")
    @classmethod
    def validate_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("时间筛选必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_date_order(self) -> ImportBatchListQuery:
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from 不能晚于 created_to")
        return self


class ImportBatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ImportBatchResponse, ...]
    next_cursor: str | None = None
    has_more: bool


class ImportBatchSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_count: int = Field(ge=0)
    completed_today_count: int = Field(ge=0)
    rows_ingested_today: int = Field(ge=0)
    as_of: datetime


class KeywordPackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Keyword Pack 名称不能为空")
        return value


class KeywordPackKeywordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    priority: int = 100
    enabled: bool = True
    note: str = Field(default="", max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("关键词不能为空")
        return value


class KeywordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    platform: str = "all"
    enabled: bool
    priority: int
    note: str


class KeywordPackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    description: str
    enabled: bool
    version: int = Field(gt=0)
    keywords: tuple[KeywordResponse, ...]


class GlobalRelevanceConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword_pack_id: UUID


class GlobalRelevanceConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword_pack_id: UUID
    keyword_pack_version: int = Field(gt=0)
    version: int = Field(gt=0)
    effective_keywords: tuple[str, ...]
    updated_at: datetime


__all__ = [
    "GlobalRelevanceConfigRequest",
    "GlobalRelevanceConfigResponse",
    "HttpErrorItem",
    "HttpErrorResponse",
    "ImportBatchListQuery",
    "ImportBatchListResponse",
    "ImportBatchCreatedResponse",
    "ImportBatchResponse",
    "ImportBatchStatus",
    "ImportBatchSummaryResponse",
    "ImportJobResultResponse",
    "ImportStatsResponse",
    "ImportStage",
    "JobStatusResponse",
    "KeywordPackCreateRequest",
    "KeywordPackKeywordCreateRequest",
    "KeywordPackResponse",
    "KeywordResponse",
]
