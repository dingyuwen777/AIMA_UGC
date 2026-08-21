"""Import、Keyword 与 Relevance 公共 HTTP Request / Response 契约。"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType
from aima_ugc.contracts.collection.models import BusinessOperation

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


type CollectionPlatform = Literal["xhs", "douyin", "weibo", "bilibili", "kuaishou"]
type CollectionRunMode = Literal["discovery", "batch_supplement"]
type CollectionRuntimeRecordType = Literal[
    "excel_import",
    "tikhub_discovery",
    "tikhub_batch_supplement",
]
type CollectionRuntimeStatus = Literal[
    "queued",
    "running",
    "partial_success",
    "succeeded",
    "failed",
    "cancelled",
]


class CollectionRunPlatformRequest(BaseModel):
    """一次手工 Collection Run 的平台与正式 Provider Config 选择。"""

    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    provider_config_id: UUID


class CollectionRunCreateRequest(BaseModel):
    """Stage 8E 一次性发现或基于 Batch 补采请求。"""

    model_config = ConfigDict(extra="forbid")

    mode: CollectionRunMode
    keywords: tuple[str, ...] = Field(default=(), max_length=100)
    import_batch_id: UUID | None = None
    platforms: tuple[CollectionRunPlatformRequest, ...] = Field(min_length=1, max_length=5)
    include_comments: bool = True
    include_sub_comments: bool = False

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        if len(value) > 100:
            raise ValueError("一次性 Discovery 关键词最多 100 个")
        normalized: list[object] = []
        identities: set[str] = set()
        for raw in value:
            if not isinstance(raw, str):
                normalized.append(raw)
                continue
            text = unicodedata.normalize("NFKC", raw.strip())
            if not text:
                raise ValueError("一次性 Discovery 关键词不能为空")
            if len(text) > 500:
                raise ValueError("一次性 Discovery 关键词最多 500 个字符")
            identity = text.casefold()
            if identity in identities:
                continue
            identities.add(identity)
            normalized.append(text)
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_mode_and_options(self) -> CollectionRunCreateRequest:
        platforms = [item.platform for item in self.platforms]
        if len(platforms) != len(set(platforms)):
            raise ValueError("同一次 Collection Run 的目标平台不得重复")
        if self.mode == "discovery":
            if not self.keywords:
                raise ValueError("主动发现必须提供至少一个一次性 Discovery 关键词")
            if self.import_batch_id is not None:
                raise ValueError("主动发现不能关联 Import Batch")
        else:
            if self.import_batch_id is None:
                raise ValueError("基于 Batch 补采必须提供 import_batch_id")
            if self.keywords:
                raise ValueError("基于 Batch 补采不能提交 Discovery 关键词")
        if self.include_sub_comments and not self.include_comments:
            raise ValueError("采集二级回复时必须同时启用评论采集")
        return self


class CollectionRunCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    job_id: UUID
    mode: CollectionRunMode
    import_batch_id: UUID | None = None
    status: Literal["queued"] = "queued"


class CollectionRunStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    content_count: int = Field(ge=0)
    comment_count: int = Field(ge=0)
    filtered_count: int = Field(default=0, ge=0)


class CollectionScopeResponse(BaseModel):
    """Provider-neutral Scope 进度；不公开 Provider 私有分页状态。"""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    platform: CollectionPlatform
    source_type: str
    operation_group: str
    status: CollectionRuntimeStatus
    progress: int = Field(ge=0, le=100)
    stats: CollectionRunStatsResponse
    stop_reason: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CollectionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    job_id: UUID
    mode: CollectionRunMode
    import_batch_id: UUID | None = None
    status: CollectionRuntimeStatus
    stage: str
    progress: int = Field(ge=0, le=100)
    attempt: int = Field(ge=0)
    max_attempts: int = Field(gt=0)
    platforms: tuple[CollectionPlatform, ...]
    keywords: tuple[str, ...] = ()
    stats: CollectionRunStatsResponse
    scopes: tuple[CollectionScopeResponse, ...]
    error_summary: str | None = None
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CollectionProviderConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider: str
    display_name: str


class CollectionCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    platform: CollectionPlatform
    operations: tuple[BusinessOperation, ...] = Field(min_length=1)


class CollectionCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_configs: tuple[CollectionProviderConfigResponse, ...]
    capabilities: tuple[CollectionCapabilityResponse, ...]


class CollectionRuntimeListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=500)
    record_types: tuple[CollectionRuntimeRecordType, ...] = Field(default=(), max_length=3)
    status: CollectionRuntimeStatus | None = None
    stage: str | None = Field(default=None, min_length=1, max_length=100)
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
    def validate_filters(self) -> CollectionRuntimeListQuery:
        if len(self.record_types) != len(set(self.record_types)):
            raise ValueError("运行记录类型筛选不得重复")
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from 不能晚于 created_to")
        return self


class CollectionRuntimeItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: UUID
    job_id: UUID
    record_type: CollectionRuntimeRecordType
    display_name: str
    status: CollectionRuntimeStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    import_batch_id: UUID | None = None
    collection_run_id: UUID | None = None
    source_filename: str | None = None
    platforms: tuple[CollectionPlatform, ...] = ()
    keywords: tuple[str, ...] = ()
    import_stats: ImportStatsResponse | None = None
    collection_stats: CollectionRunStatsResponse | None = None
    error_summary: str | None = None
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CollectionRuntimeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CollectionRuntimeItemResponse, ...]
    next_cursor: str | None = None
    has_more: bool


class CollectionRuntimeSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_count: int = Field(ge=0)
    completed_today_count: int = Field(ge=0)
    contents_ingested_today: int = Field(ge=0)
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


class KeywordPackListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class KeywordPackSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    description: str
    enabled: bool
    version: int = Field(gt=0)
    keyword_count: int = Field(ge=0)


class KeywordPackListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[KeywordPackSummaryResponse, ...]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class ResourceEnabledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


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


class CollectionPlanPlatformRequest(BaseModel):
    """Plan 只选择稳定 Provider Config，不接收 Provider 私有配置。"""

    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    provider_config_id: UUID


class CollectionPlanCreateRequest(BaseModel):
    """Stage 8F 周期 Plan 创建 Contract；一次性运行继续使用 Stage 8E。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    schedule_expr: str = Field(min_length=1, max_length=100)
    platforms: tuple[CollectionPlanPlatformRequest, ...] = Field(min_length=1, max_length=5)
    keyword_pack_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    enabled: bool = True

    @field_validator("name", "schedule_expr", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Plan 名称和 Cron 表达式不能为空")
        return value

    @model_validator(mode="after")
    def validate_unique_relations(self) -> CollectionPlanCreateRequest:
        platforms = [item.platform for item in self.platforms]
        if len(platforms) != len(set(platforms)):
            raise ValueError("同一 Plan 的目标平台不得重复")
        if len(self.keyword_pack_ids) != len(set(self.keyword_pack_ids)):
            raise ValueError("同一 Plan 的 Discovery 词包不得重复")
        return self


class CollectionPlanPlatformResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    provider_config_id: UUID


class CollectionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    enabled: bool
    schedule_expr: str
    timezone: Literal["Asia/Shanghai"]
    schedule_version: int = Field(gt=0)
    next_run_at: datetime | None = None
    last_scheduled_at: datetime | None = None
    detail_policy: Literal["on_change"]
    comment_policy: Literal["adaptive"]
    platforms: tuple[CollectionPlanPlatformResponse, ...]
    keyword_pack_ids: tuple[UUID, ...]
    created_at: datetime
    updated_at: datetime


class CollectionPlanListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    platform: CollectionPlatform | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class CollectionPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CollectionPlanResponse, ...]
    total: int = Field(ge=0)
    enabled_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


type ContentAnalysisStatus = Literal["pending", "completed", "stale"]


class ContentLabelPairResponse(BaseModel):
    """按模型重要性顺序返回的一个一级/二级标签对。"""

    model_config = ConfigDict(extra="forbid")

    primary_label: str
    secondary_label: str


class ContentAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ContentAnalysisStatus
    relevance: ContentRelevance | None = None
    voice_type: ContentVoiceType | None = None
    sentiment: str | None = None
    labels: tuple[ContentLabelPairResponse, ...] = ()
    analyzed_at: datetime | None = None
    model_provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def validate_completed_shape(self) -> ContentAnalysisResponse:
        if self.status == "completed":
            if self.relevance is None or self.voice_type is None:
                raise ValueError("completed Analysis 必须包含相关性与发声类型")
            if self.relevance == "relevant":
                if self.sentiment is None or self.analyzed_at is None or not self.labels:
                    raise ValueError("relevant completed Analysis 必须包含情感、标签与分析时间")
            elif self.sentiment is not None or self.labels or self.analyzed_at is None:
                raise ValueError("irrelevant completed Analysis 只能携带分类和分析时间")
        elif (
            any(
                value is not None
                for value in (
                    self.relevance,
                    self.voice_type,
                    self.sentiment,
                    self.analyzed_at,
                )
            )
            or self.labels
        ):
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
    relevance: ContentRelevance | None = None
    voice_type: ContentVoiceType | None = None
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
    "CollectionCapabilitiesResponse",
    "CollectionCapabilityResponse",
    "CollectionPlanCreateRequest",
    "CollectionPlanListQuery",
    "CollectionPlanListResponse",
    "CollectionPlanPlatformRequest",
    "CollectionPlanPlatformResponse",
    "CollectionPlanResponse",
    "CollectionPlatform",
    "CollectionProviderConfigResponse",
    "CollectionRunCreateRequest",
    "CollectionRunCreatedResponse",
    "CollectionRunMode",
    "CollectionRunPlatformRequest",
    "CollectionRunResponse",
    "CollectionRunStatsResponse",
    "CollectionScopeResponse",
    "CollectionRuntimeItemResponse",
    "CollectionRuntimeListQuery",
    "CollectionRuntimeListResponse",
    "CollectionRuntimeRecordType",
    "CollectionRuntimeStatus",
    "CollectionRuntimeSummaryResponse",
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
    "KeywordPackListQuery",
    "KeywordPackListResponse",
    "KeywordPackKeywordCreateRequest",
    "KeywordPackResponse",
    "KeywordPackSummaryResponse",
    "KeywordResponse",
    "ResourceEnabledRequest",
]
