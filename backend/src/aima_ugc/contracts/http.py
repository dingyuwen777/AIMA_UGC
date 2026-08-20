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


class ContentAnalysisJobResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    stale: int = Field(ge=0)


class DataExportJobResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: UUID
    artifact_id: UUID
    content_count: int = Field(ge=0)
    analyzed_count: int = Field(ge=0)
    unanalyzed_count: int = Field(ge=0)
    comment_count: int = Field(ge=0)


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job_type: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    attempt: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    progress: int = Field(ge=0, le=100)
    error_code: str | None = None
    result: (
        ImportJobResultResponse
        | ContentAnalysisJobResultResponse
        | DataExportJobResultResponse
        | None
    ) = None
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


type ContentAnalysisStatus = Literal["pending", "completed", "stale"]


class ContentLabelPairResponse(BaseModel):
    """按模型重要性顺序返回的一个一级/二级标签对。"""

    model_config = ConfigDict(extra="forbid")

    primary_label: str
    secondary_label: str


class ContentAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ContentAnalysisStatus
    sentiment: str | None = None
    labels: tuple[ContentLabelPairResponse, ...] = ()
    analyzed_at: datetime | None = None
    model_provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def validate_completed_shape(self) -> ContentAnalysisResponse:
        if self.status == "completed":
            if self.sentiment is None or self.analyzed_at is None or not self.labels:
                raise ValueError("completed Analysis 必须包含情感、标签与分析时间")
        elif self.sentiment is not None or self.labels or self.analyzed_at is not None:
            raise ValueError("非 completed Analysis 不能携带结果字段")
        return self


class ContentMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    favorite_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    repost_count: int | None = Field(default=None, ge=0)
    view_count: int | None = Field(default=None, ge=0)
    play_count: int | None = Field(default=None, ge=0)


class ContentSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str
    provider_attempt_id: UUID | None = None
    raw_artifact_id: UUID | None = None
    import_batch_id: UUID | None = None
    collection_run_id: UUID | None = None


class ContentMediaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int = Field(ge=0)
    media_type: str
    url: str | None = None
    preview_url: str | None = None
    alt_text: str | None = None


class ContentListItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    platform: str
    external_content_id: str
    content_type: str
    title: str | None = None
    text: str | None = None
    author_display_name: str | None = None
    published_at: datetime | None = None
    last_seen_at: datetime
    content_url: str | None = None
    metrics: ContentMetricsResponse
    analysis: ContentAnalysisResponse
    source: ContentSourceResponse


class ContentFilterSnapshot(BaseModel):
    """可序列化并冻结到 Analysis/Export Request 的查询条件。"""

    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=500)
    platforms: tuple[str, ...] = Field(default=(), max_length=20)
    content_types: tuple[str, ...] = Field(default=(), max_length=20)
    analysis_status: ContentAnalysisStatus | None = None
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)
    primary_label: str | None = Field(default=None, min_length=1, max_length=256)
    secondary_label: str | None = Field(default=None, min_length=1, max_length=256)
    published_from: datetime | None = None
    published_to: datetime | None = None
    source_identifier: UUID | None = None

    @field_validator("published_from", "published_to")
    @classmethod
    def validate_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("时间筛选必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_date_order(self) -> ContentFilterSnapshot:
        if (
            self.published_from is not None
            and self.published_to is not None
            and self.published_from > self.published_to
        ):
            raise ValueError("published_from 不能晚于 published_to")
        return self


class ContentListQuery(ContentFilterSnapshot):
    model_config = ConfigDict(extra="forbid")

    cursor: str | None = Field(default=None, min_length=1, max_length=4096)
    limit: int = Field(default=20, ge=1, le=100)


class ContentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ContentListItemResponse, ...]
    next_cursor: str | None = None
    has_more: bool


class ContentCommentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    external_comment_id: str
    author_display_name: str | None = None
    text: str | None = None
    published_at: datetime | None = None
    like_count: int | None = Field(default=None, ge=0)
    reply_count: int | None = Field(default=None, ge=0)


class CommentCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage: str
    reported_total: int | None = Field(default=None, ge=0)
    collected_count: int = Field(ge=0)
    observed_at: datetime


class ContentDetailResponse(ContentListItemResponse):
    model_config = ConfigDict(extra="forbid")

    media: tuple[ContentMediaResponse, ...] = ()
    comments: tuple[ContentCommentResponse, ...] = ()
    comment_coverage: CommentCoverageResponse | None = None
    source_records: tuple[ContentSourceResponse, ...] = ()


class ContentTargetSelection(BaseModel):
    """HTTP 层选择语义；Service 会立刻冻结 Content ID + Version。"""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["query", "selected"]
    filters: ContentFilterSnapshot | None = None
    content_ids: tuple[UUID, ...] = Field(default=(), max_length=1000)

    @model_validator(mode="after")
    def validate_scope(self) -> ContentTargetSelection:
        if self.scope == "selected":
            if not self.content_ids or self.filters is not None:
                raise ValueError("selected 必须且只能提供非空 content_ids")
        elif self.content_ids:
            raise ValueError("query 不能提供 content_ids")
        if len(self.content_ids) != len(set(self.content_ids)):
            raise ValueError("content_ids 不能重复")
        return self


class ContentAnalysisSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: ContentTargetSelection


class ContentAnalysisCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    job_id: UUID
    target_count: int = Field(gt=0)
    status: Literal["queued"] = "queued"


class DataExportSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: ContentTargetSelection
    format: Literal["xlsx"] = "xlsx"


class DataExportCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: UUID
    job_id: UUID
    target_count: int = Field(gt=0)
    status: Literal["queued"] = "queued"


class DataExportStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_count: int = Field(ge=0)
    analyzed_count: int = Field(ge=0)
    unanalyzed_count: int = Field(ge=0)
    comment_count: int = Field(ge=0)


class DataExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job: JobStatusResponse
    artifact_id: UUID | None = None
    filename: str | None = None
    stats: DataExportStatsResponse | None = None
    created_at: datetime
    completed_at: datetime | None = None


class DataExportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[DataExportResponse, ...]


__all__ = [
    "CommentCoverageResponse",
    "ContentAnalysisCreatedResponse",
    "ContentAnalysisJobResultResponse",
    "ContentAnalysisResponse",
    "ContentAnalysisStatus",
    "ContentAnalysisSubmitRequest",
    "ContentCommentResponse",
    "ContentDetailResponse",
    "ContentFilterSnapshot",
    "ContentLabelPairResponse",
    "ContentListItemResponse",
    "ContentListQuery",
    "ContentListResponse",
    "ContentMediaResponse",
    "ContentMetricsResponse",
    "ContentSourceResponse",
    "ContentTargetSelection",
    "DataExportCreatedResponse",
    "DataExportJobResultResponse",
    "DataExportListResponse",
    "DataExportResponse",
    "DataExportStatsResponse",
    "DataExportSubmitRequest",
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
