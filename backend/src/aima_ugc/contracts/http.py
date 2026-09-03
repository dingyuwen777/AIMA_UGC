"""Import、Keyword 与 Relevance 公共 HTTP Request / Response 契约。"""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, computed_field, field_validator, model_validator

from aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType
from aima_ugc.contracts.base import AimaHttpModel as BaseModel
from aima_ugc.contracts.collection.models import BusinessOperation, CollectionSearchConfig
from aima_ugc.contracts.platform import PlatformName, PlatformScope, normalize_platform_name
from aima_ugc.platform.time import to_beijing

from .product import ContentAvailabilityResponse

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
        return to_beijing(value) if value is not None else None

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


type CollectionPlatform = PlatformName


def _normalize_platform_input(value: object) -> object:
    if isinstance(value, str):
        return normalize_platform_name(value)
    return value


def _normalize_platform_inputs(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return tuple(_normalize_platform_input(item) for item in value)
    return value


type CollectionRunMode = Literal["discovery", "batch_supplement"]
type CollectionRuntimeRecordType = Literal[
    "excel_import",
    "data_import_campaign",
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
    search_config: CollectionSearchConfig | None = None

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return _normalize_platform_input(value)


class CollectionRunCreateRequest(BaseModel):
    """一次性发现从 Keyword Pack 冻结关键词；Batch Supplement 只补既有内容。"""

    model_config = ConfigDict(extra="forbid")

    mode: CollectionRunMode
    keyword_pack_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    import_batch_id: UUID | None = None
    data_import_campaign_id: UUID | None = None
    platforms: tuple[CollectionRunPlatformRequest, ...] = Field(min_length=1, max_length=5)
    include_comments: bool = True
    include_sub_comments: bool = False

    @model_validator(mode="after")
    def validate_mode_and_options(self) -> CollectionRunCreateRequest:
        platforms = [item.platform for item in self.platforms]
        if len(platforms) != len(set(platforms)):
            raise ValueError("同一次 Collection Run 的目标平台不得重复")
        if len(self.keyword_pack_ids) != len(set(self.keyword_pack_ids)):
            raise ValueError("同一次 Collection Run 的词包不得重复")
        if len(self.vehicle_model_ids) != len(set(self.vehicle_model_ids)):
            raise ValueError("同一次 Collection Run 的车型不得重复")
        if self.mode == "discovery":
            if not self.keyword_pack_ids and not self.vehicle_model_ids:
                raise ValueError("主动发现必须至少选择一个 Keyword Pack 或车型")
            if self.import_batch_id is not None or self.data_import_campaign_id is not None:
                raise ValueError("主动发现不能关联数据导入来源")
        else:
            if (self.import_batch_id is None) == (self.data_import_campaign_id is None):
                raise ValueError(
                    "基于数据导入补采必须且只能提供 import_batch_id 或 data_import_campaign_id"
                )
            if self.keyword_pack_ids:
                raise ValueError("基于 Batch 补采不能提交 Keyword Pack")
            if self.vehicle_model_ids:
                raise ValueError("基于 Batch 补采不能提交车型")
            if any(item.search_config is not None for item in self.platforms):
                raise ValueError("基于 Batch 补采不能提交关键词搜索配置")
        if self.include_sub_comments and not self.include_comments:
            raise ValueError("采集二级回复时必须同时启用评论采集")
        return self


class CollectionRunCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    job_id: UUID
    mode: CollectionRunMode
    import_batch_id: UUID | None = None
    data_import_campaign_id: UUID | None = None
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
    data_import_campaign_id: UUID | None = None
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


class CollectionSearchCapabilityResponse(BaseModel):
    """前端配置 Search 所需的合法选项与手工发现默认值。"""

    model_config = ConfigDict(extra="forbid")

    supported_sort_modes: tuple[str, ...]
    supported_time_filters: tuple[str, ...]
    supported_duration_filters: tuple[str, ...]
    supported_content_types: tuple[str, ...]
    manual_default: CollectionSearchConfig


class CollectionCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    platform: CollectionPlatform
    operations: tuple[BusinessOperation, ...] = Field(min_length=1)
    search: CollectionSearchCapabilityResponse | None


class CollectionCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_configs: tuple[CollectionProviderConfigResponse, ...]
    capabilities: tuple[CollectionCapabilityResponse, ...]


class CollectionBatchSupplementTargetResponse(BaseModel):
    """一个平台当前真实可创建 Batch Supplement Scope 的目标数。"""

    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    target_count: int = Field(gt=0)


class CollectionBatchSupplementEligibilityResponse(BaseModel):
    """前端 Batch Supplement 平台资格；不公开 Provider 私有身份或 AI 结果正文。"""

    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    targets: tuple[CollectionBatchSupplementTargetResponse, ...]


class CollectionCampaignSupplementEligibilityResponse(BaseModel):
    """前端 Campaign Supplement 平台资格；目标来自逐行来源账本。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    targets: tuple[CollectionBatchSupplementTargetResponse, ...]


class CollectionRuntimeListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=500)
    record_types: tuple[CollectionRuntimeRecordType, ...] = Field(default=(), max_length=4)
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
        return to_beijing(value) if value is not None else None

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
    job_id: UUID | None = None
    record_type: CollectionRuntimeRecordType
    display_name: str
    status: CollectionRuntimeStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    import_batch_id: UUID | None = None
    data_import_campaign_id: UUID | None = None
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


class ContentSupplementStatusResponse(BaseModel):
    """声音广场只读补采状态；不公开 Provider 私有请求与原始错误详情。"""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    status: CollectionRuntimeStatus
    stop_reason: str | None = None
    updated_at: datetime


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


class KeywordPackCreateRequest(BaseModel):
    """创建词包；可在同一事务中携带初始关键词，旧客户端仍可省略。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    keywords: tuple[KeywordPackKeywordCreateRequest, ...] = Field(default=(), max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Keyword Pack 名称不能为空")
        return value


class KeywordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    platform_scope: PlatformScope = "all"
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
    """Plan 逐平台提交 Provider-neutral 搜索配置，不接收 Provider 私有参数。"""

    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    provider_config_id: UUID
    search_config: CollectionSearchConfig

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return _normalize_platform_input(value)


class CollectionPlanCreateRequest(BaseModel):
    """Stage 8F 周期 Plan 创建 Contract；一次性运行继续使用 Stage 8E。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    schedule_expr: str = Field(min_length=1, max_length=100)
    platforms: tuple[CollectionPlanPlatformRequest, ...] = Field(min_length=1, max_length=5)
    keyword_pack_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
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
        if len(self.vehicle_model_ids) != len(set(self.vehicle_model_ids)):
            raise ValueError("同一 Plan 的车型不得重复")
        if not self.keyword_pack_ids and not self.vehicle_model_ids:
            raise ValueError("Plan 必须至少选择一个 Keyword Pack 或车型")
        return self


class CollectionPlanPlatformResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    provider_config_id: UUID
    search_config: CollectionSearchConfig


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
    vehicle_model_ids: tuple[UUID, ...] = ()
    created_at: datetime
    updated_at: datetime


class CollectionPlanListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    platform: CollectionPlatform | None = None
    offset: int = Field(default=0, ge=0)

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return _normalize_platform_input(value)

    limit: int = Field(default=20, ge=1, le=100)


class CollectionPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CollectionPlanResponse, ...]
    total: int = Field(ge=0)
    enabled_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


type ContentAnalysisStatus = Literal["pending", "completed", "stale"]
type ContentRelevanceSource = Literal["ai", "manual_review"]


class ContentLabelPairResponse(BaseModel):
    """按模型重要性顺序返回的一个一级/二级标签对。"""

    model_config = ConfigDict(extra="forbid")

    primary_label: str
    secondary_label: str


class ContentAnalysisTaxonomyLabelResponse(BaseModel):
    """只读 Taxonomy 中一个一级标签及其有序二级标签。"""

    model_config = ConfigDict(extra="forbid")

    primary_label: str = Field(min_length=1, max_length=256)
    secondary_labels: tuple[str, ...] = Field(min_length=1)


class ContentAnalysisTaxonomyResponse(BaseModel):
    """供业务页面消费的安全 Prompt Taxonomy 投影。"""

    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(min_length=1, max_length=128)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1, max_length=128)
    taxonomy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sentiments: tuple[str, ...] = Field(min_length=1)
    voice_types: tuple[str, ...] = Field(min_length=1)
    labels: tuple[ContentAnalysisTaxonomyLabelResponse, ...] = Field(min_length=1)


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
    latest_run_id: UUID | None = None
    latest_run_status: str | None = None
    manual_locked_dimensions: tuple[Literal["voice_type", "sentiment", "labels"], ...] = ()

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


class ContentVehicleEvidenceResponse(BaseModel):
    """一个车型关联的可追溯证据。"""

    model_config = ConfigDict(extra="forbid")
    source: Literal["alias_match", "ai_candidate", "manual_review", "import"]
    matched_text: str | None = None
    source_field: str | None = None
    catalog_version: int = Field(gt=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    is_manual_locked: bool = False


class ContentVehicleResponse(BaseModel):
    """内容当前车型及其全部有效证据。"""

    model_config = ConfigDict(extra="forbid")
    vehicle_model_id: UUID
    code: str
    display_name: str
    evidences: tuple[ContentVehicleEvidenceResponse, ...] = Field(min_length=1)


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
    content_version: int = Field(gt=0)
    platform: PlatformName
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
    effective_relevance: ContentRelevance | None = None
    relevance_source: ContentRelevanceSource | None = None
    source: ContentSourceResponse
    vehicles: tuple[ContentVehicleResponse, ...] = ()
    availability: ContentAvailabilityResponse | None = None

    @model_validator(mode="after")
    def validate_relevance_projection(self) -> ContentListItemResponse:
        if (self.effective_relevance is None) != (self.relevance_source is None):
            raise ValueError("effective_relevance 与 relevance_source 必须同时为空或同时存在")
        if self.relevance_source == "ai" and (
            self.analysis.status != "completed"
            or self.analysis.relevance != self.effective_relevance
        ):
            raise ValueError("AI relevance_source 必须与当前 completed Analysis 原判一致")
        return self


class ContentFilterSnapshot(BaseModel):
    """可序列化并冻结到 Analysis/Export Request 的查询条件。"""

    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=500)
    platforms: tuple[PlatformName, ...] = Field(default=(), max_length=5)
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
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)

    @field_validator("platforms", mode="before")
    @classmethod
    def normalize_platforms(cls, value: object) -> object:
        return _normalize_platform_inputs(value)

    @field_validator("published_from", "published_to")
    @classmethod
    def validate_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("时间筛选必须包含时区")
        return to_beijing(value) if value is not None else None

    @model_validator(mode="after")
    def validate_date_order(self) -> ContentFilterSnapshot:
        if (
            self.published_from is not None
            and self.published_to is not None
            and self.published_from > self.published_to
        ):
            raise ValueError("published_from 不能晚于 published_to")
        if len(self.vehicle_model_ids) != len(set(self.vehicle_model_ids)):
            raise ValueError("vehicle_model_ids 不能重复")
        return self


class ContentListQuery(ContentFilterSnapshot):
    model_config = ConfigDict(extra="forbid")

    cursor: str | None = Field(default=None, min_length=1, max_length=4096)
    limit: int = Field(default=20, ge=1, le=100)


class ContentCountRequest(BaseModel):
    """独立 Count 请求；不改变声音广场 Cursor 分页。"""

    model_config = ConfigDict(extra="forbid")
    filters: ContentFilterSnapshot = Field(default_factory=ContentFilterSnapshot)
    count_mode: Literal["none", "exact", "estimated"] = "none"
    exact_limit: int | None = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_count_mode(self) -> ContentCountRequest:
        """exact 必须显式给出扫描上限，其他模式不得携带该字段。"""

        if self.count_mode == "exact" and self.exact_limit is None:
            raise ValueError("exact count_mode 必须设置 exact_limit")
        if self.count_mode != "exact" and self.exact_limit is not None:
            raise ValueError("只有 exact count_mode 可以设置 exact_limit")
        return self


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
    supplement_status: ContentSupplementStatusResponse | None = None
    source_records: tuple[ContentSourceResponse, ...] = ()


class ContentTargetSelection(BaseModel):
    """HTTP 层选择语义；新版 Run 由 Planner 异步冻结 Content ID + Version。"""

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
    run_id: UUID | None = None
    shard_count: int = Field(default=1, ge=1)


AnalysisRunIntent = Literal["initial_analysis", "manual_reanalysis"]
AnalysisRunStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "partial_failed",
    "failed",
    "cancelling",
    "cancelled",
]


class AnalysisRunTargetSelection(BaseModel):
    """Analysis Run 公开目标：显式选择或数据库当前全部 Content。"""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["selected", "all"] = "selected"
    content_ids: tuple[UUID, ...] = Field(default=(), max_length=1000)

    @model_validator(mode="after")
    def validate_scope_and_content_ids(self) -> AnalysisRunTargetSelection:
        if len(self.content_ids) != len(set(self.content_ids)):
            raise ValueError("content_ids 不能重复")
        if self.scope == "selected" and not self.content_ids:
            raise ValueError("selected Scope 必须提供至少一个 content_id")
        if self.scope == "all" and self.content_ids:
            raise ValueError("all Scope 不能提交 content_ids")
        return self


class AnalysisContentRunPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: AnalysisRunTargetSelection


class AnalysisContentRunPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_count: int = Field(gt=0)
    shard_count: int = Field(gt=0)
    shard_size: int = Field(gt=0)
    analysis_scheme_version_id: UUID | None = None
    prompt_version: str
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    taxonomy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_provider: str
    model: str
    generation_config: dict[str, object]
    generation_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    cost_estimate_available: bool = False
    cost_estimate_note: str


class AnalysisContentRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    targets: AnalysisRunTargetSelection
    expected_target_count: int = Field(gt=0)
    expected_configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_intent: AnalysisRunIntent = "manual_reanalysis"


class AnalysisContentRunStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    stale: int = Field(default=0, ge=0)
    cancelled: int = Field(default=0, ge=0)


class AnalysisContentRunShardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    job_id: UUID
    shard_no: int = Field(ge=0)
    target_count: int = Field(gt=0)
    status: str
    progress: int = Field(ge=0, le=100)
    error_code: str | None = None


class AnalysisContentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    planner_job_id: UUID
    sequence_no: int = Field(gt=0)
    status: AnalysisRunStatus
    run_intent: AnalysisRunIntent
    scope: Literal["all", "query", "selected"]
    target_count: int = Field(gt=0)
    shard_count: int = Field(gt=0)
    shard_size: int = Field(gt=0)
    analysis_scheme_version_id: UUID | None = None
    prompt_version: str
    prompt_sha256: str
    taxonomy_sha256: str
    model_provider: str
    model: str
    generation_config: dict[str, object]
    generation_config_hash: str
    error_code: str | None = None
    stats: AnalysisContentRunStatsResponse = AnalysisContentRunStatsResponse()
    shards: tuple[AnalysisContentRunShardResponse, ...] = ()
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisContentRunCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    planner_job_id: UUID
    target_count: int = Field(gt=0)
    shard_count: int = Field(gt=0)
    status: Literal["queued"] = "queued"


class AnalysisContentRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[AnalysisContentRunResponse, ...]


type ExportColumnKey = Literal[
    "platform",
    "external_content_id",
    "source_item_id",
    "content_type",
    "content_url",
    "title",
    "text",
    "author_display_name",
    "author_follower_count",
    "author_following_count",
    "author_content_count",
    "author_total_like_count",
    "published_at",
    "voice_type",
    "sentiment",
    "primary_label",
    "secondary_label",
    "vehicles",
    "availability",
    "like_count",
    "comment_count",
    "favorite_count",
    "share_count",
    "repost_count",
    "view_count",
    "play_count",
    "danmaku_count",
    "coin_count",
    "download_count",
    "matched_keywords",
    "analysis_model",
    "prompt_version",
    "taxonomy_version",
    "source_provider",
    "raw_locator",
    "coverage",
]


class DataExportSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: ContentTargetSelection
    format: Literal["xlsx"] = "xlsx"
    columns: tuple[ExportColumnKey, ...] = Field(default=(), max_length=100)

    @field_validator("columns")
    @classmethod
    def validate_unique_columns(
        cls, value: tuple[ExportColumnKey, ...]
    ) -> tuple[ExportColumnKey, ...]:
        """列 key 必须非空且不重复；白名单由 Reporting Owner 校验。"""

        if any(not item.strip() or item != item.strip() for item in value):
            raise ValueError("columns 必须是无首尾空白的非空 key")
        if len(value) != len(set(value)):
            raise ValueError("columns 不能重复")
        return value


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
    columns: tuple[str, ...] = ()
    column_catalog_version: int = Field(default=1, gt=0)


class DataExportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[DataExportResponse, ...]


type HistoricalCampaignStatus = Literal[
    "uploading",
    "discovering",
    "snapshotting",
    "ready",
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "succeeded",
    "partial_failed",
    "failed",
]
type DataImportSourceKind = Literal["local_upload", "server_path"]
type DataImportIngestionPolicy = Literal["standard_observation", "historical_fill_only"]
type HistoricalCampaignItemStatus = Literal[
    "discovered",
    "snapshotting",
    "ready",
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
]


class HistoricalDirectoryListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(default="", max_length=1024)
    cursor: str | None = Field(default=None, max_length=2048)
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        return _historical_relative_path(value)


class HistoricalDirectoryEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str
    name: str
    kind: Literal["directory", "file"]
    byte_size: int | None = Field(default=None, ge=0)
    modified_at_ns: int = Field(ge=0)


class HistoricalDirectoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    unavailable_reason: str | None = None
    items: tuple[HistoricalDirectoryEntryResponse, ...] = ()
    next_cursor: str | None = None
    has_more: bool = False

    @model_validator(mode="after")
    def validate_availability(self) -> HistoricalDirectoryListResponse:
        if self.available and self.unavailable_reason is not None:
            raise ValueError("可用目录响应不能包含 unavailable_reason")
        if not self.available and (self.items or self.next_cursor or self.has_more):
            raise ValueError("不可用目录响应不能伪造枚举结果")
        return self


class HistoricalCampaignCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    relative_paths: tuple[str, ...] = Field(min_length=1, max_length=1000)
    recursive: bool = False
    keyword_pack_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    profile: Literal["aima-monitoring-excel.v1"] = "aima-monitoring-excel.v1"
    ingestion_policy: DataImportIngestionPolicy = "historical_fill_only"

    @field_validator("relative_paths")
    @classmethod
    def validate_relative_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_historical_relative_path(item) for item in value)
        if len(set(normalized)) != len(normalized):
            raise ValueError("relative_paths 不能重复")
        return normalized

    @field_validator("keyword_pack_ids")
    @classmethod
    def validate_keyword_pack_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(set(value)) != len(value):
            raise ValueError("keyword_pack_ids 不能重复")
        return value

    @model_validator(mode="after")
    def validate_matching_resources(self) -> HistoricalCampaignCreateRequest:
        """历史 Campaign 至少冻结词包或车型中的一个维度。"""

        if len(self.vehicle_model_ids) != len(set(self.vehicle_model_ids)):
            raise ValueError("vehicle_model_ids 不能重复")
        if not self.keyword_pack_ids and not self.vehicle_model_ids:
            raise ValueError("必须至少选择一个 Keyword Pack 或车型")
        return self


class LocalDataImportFileManifest(BaseModel):
    """声明浏览器显式选择的一个本地 XLSX；绝不承载本机绝对路径。"""

    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(min_length=1, max_length=1024)
    byte_size: int = Field(ge=1, le=500 * 1024 * 1024)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalized = _historical_relative_path(value)
        if not normalized.casefold().endswith(".xlsx"):
            raise ValueError("本地导入清单只允许 .xlsx 文件")
        return normalized


class LocalDataImportCampaignCreateRequest(BaseModel):
    """建立本地文件暂存 Campaign；文件字节随后按 Item 分别流式上传。"""

    model_config = ConfigDict(extra="forbid")

    client_idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    files: tuple[LocalDataImportFileManifest, ...] = Field(min_length=1, max_length=1000)
    keyword_pack_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    profile: Literal["aima-monitoring-excel.v1"] = "aima-monitoring-excel.v1"
    ingestion_policy: DataImportIngestionPolicy = "standard_observation"

    @field_validator("files")
    @classmethod
    def validate_files(
        cls,
        value: tuple[LocalDataImportFileManifest, ...],
    ) -> tuple[LocalDataImportFileManifest, ...]:
        paths = tuple(item.relative_path for item in value)
        if len(set(paths)) != len(paths):
            raise ValueError("本地导入清单 relative_path 不能重复")
        return value

    @field_validator("keyword_pack_ids")
    @classmethod
    def validate_keyword_pack_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(set(value)) != len(value):
            raise ValueError("keyword_pack_ids 不能重复")
        return value

    @model_validator(mode="after")
    def validate_matching_resources(self) -> LocalDataImportCampaignCreateRequest:
        """本地 Campaign 至少冻结词包或车型中的一个维度。"""

        if len(self.vehicle_model_ids) != len(set(self.vehicle_model_ids)):
            raise ValueError("vehicle_model_ids 不能重复")
        if not self.keyword_pack_ids and not self.vehicle_model_ids:
            raise ValueError("必须至少选择一个 Keyword Pack 或车型")
        return self


class LocalDataImportUploadItemResponse(BaseModel):
    """返回客户端下一步逐项上传所需的稳定 Item 身份。"""

    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    relative_path: str


class LocalDataImportCampaignCreatedResponse(BaseModel):
    """返回本地 Campaign 及其冻结上传清单。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    upload_items: tuple[LocalDataImportUploadItemResponse, ...]


class LocalDataImportFileUploadedResponse(BaseModel):
    """确认一个本地文件已形成服务器端不可变 Source Artifact。"""

    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    item_id: UUID
    artifact_id: UUID
    sha256: str = Field(min_length=64, max_length=64)
    byte_size: int = Field(ge=1)


class HistoricalCampaignStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: int = Field(default=0, ge=0)
    filled: int = Field(default=0, ge=0)
    updated: int = Field(default=0, ge=0)
    unchanged: int = Field(default=0, ge=0)
    conflict: int = Field(default=0, ge=0)
    filtered: int = Field(default=0, ge=0)
    duplicate: int = Field(default=0, ge=0)
    invalid: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)


class HistoricalCampaignProgressResponse(BaseModel):
    """返回可由持久状态重建的 Campaign 预检与迁移进度。"""

    model_config = ConfigDict(extra="forbid")

    preflight_completed_file_count: int = Field(ge=0)
    preflight_percent: int = Field(ge=0, le=100)
    migration_completed_row_count: int = Field(ge=0)
    migration_percent: int = Field(ge=0, le=100)


class HistoricalCampaignResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: HistoricalCampaignStatus
    source_kind: DataImportSourceKind = "server_path"
    ingestion_policy: DataImportIngestionPolicy = "historical_fill_only"
    declared_file_count: int = Field(default=0, ge=0)
    root_relative_path: str
    recursive: bool
    discovered_file_count: int = Field(ge=0)
    ready_item_count: int = Field(ge=0)
    total_rows: int = Field(ge=0)
    failed_chunk_count: int = Field(default=0, ge=0)
    progress: HistoricalCampaignProgressResponse
    stats: HistoricalCampaignStatsResponse = Field(default_factory=HistoricalCampaignStatsResponse)
    error_summary: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @computed_field
    def can_start(self) -> bool:
        return (
            self.status == "ready"
            and self.discovered_file_count > 0
            and (self.ready_item_count == self.discovered_file_count)
        )


class HistoricalCampaignCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: UUID
    discovery_job_id: UUID


class HistoricalCampaignListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[HistoricalCampaignResponse, ...]


class HistoricalCampaignItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    parent_item_id: UUID | None = None
    item_kind: Literal["source_file", "chunk"]
    relative_path: str
    ordinal: int | None = Field(default=None, ge=0)
    artifact_id: UUID | None = None
    sha256: str | None = None
    row_start: int | None = Field(default=None, ge=1)
    row_end: int | None = Field(default=None, ge=1)
    row_count: int = Field(ge=0)
    status: HistoricalCampaignItemStatus
    attempt_count: int = Field(ge=0)
    stats: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class HistoricalCampaignItemListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[HistoricalCampaignItemResponse, ...]
    total_count: int = Field(default=0, ge=0)
    has_more: bool = False


class HistoricalCampaignConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_item_id: UUID
    source_row_ordinal: int = Field(ge=1)
    content_id: UUID
    field_name: str
    content_version: int = Field(ge=1)
    current_value_hash: str
    historical_value_hash: str
    created_at: datetime


class HistoricalCampaignConflictListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[HistoricalCampaignConflictResponse, ...]
    total_count: int = Field(default=0, ge=0)
    has_more: bool = False


def _historical_relative_path(value: str) -> str:
    if "\x00" in value or "\\" in value or ":" in value or value.startswith("//"):
        raise ValueError("历史路径必须是无歧义的 POSIX 相对路径")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError("历史路径必须位于批准根目录内")
    return "/".join(part for part in path.parts if part not in {"", "."})


__all__ = [
    "AnalysisRunTargetSelection",
    "CommentCoverageResponse",
    "CollectionBatchSupplementEligibilityResponse",
    "CollectionBatchSupplementTargetResponse",
    "CollectionCampaignSupplementEligibilityResponse",
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
    "CollectionSearchCapabilityResponse",
    "CollectionSearchConfig",
    "ContentAnalysisCreatedResponse",
    "ContentAnalysisJobResultResponse",
    "ContentAnalysisResponse",
    "ContentAnalysisStatus",
    "ContentAnalysisSubmitRequest",
    "ContentAnalysisTaxonomyLabelResponse",
    "ContentAnalysisTaxonomyResponse",
    "ContentCommentResponse",
    "ContentCountRequest",
    "ContentDetailResponse",
    "ContentFilterSnapshot",
    "ContentLabelPairResponse",
    "ContentListItemResponse",
    "ContentListQuery",
    "ContentListResponse",
    "ContentMediaResponse",
    "ContentMetricsResponse",
    "ContentRelevanceSource",
    "ContentSourceResponse",
    "ContentSupplementStatusResponse",
    "ContentTargetSelection",
    "DataExportCreatedResponse",
    "DataExportJobResultResponse",
    "DataExportListResponse",
    "DataExportResponse",
    "DataExportStatsResponse",
    "DataExportSubmitRequest",
    "ExportColumnKey",
    "DataImportIngestionPolicy",
    "DataImportSourceKind",
    "GlobalRelevanceConfigRequest",
    "GlobalRelevanceConfigResponse",
    "HistoricalCampaignConflictListResponse",
    "HistoricalCampaignConflictResponse",
    "HistoricalCampaignCreateRequest",
    "HistoricalCampaignCreatedResponse",
    "HistoricalCampaignItemListResponse",
    "HistoricalCampaignItemResponse",
    "HistoricalCampaignListResponse",
    "HistoricalCampaignResponse",
    "HistoricalCampaignStatsResponse",
    "HistoricalCampaignStatus",
    "HistoricalDirectoryEntryResponse",
    "HistoricalDirectoryListQuery",
    "HistoricalDirectoryListResponse",
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
    "LocalDataImportCampaignCreateRequest",
    "LocalDataImportCampaignCreatedResponse",
    "LocalDataImportFileManifest",
    "LocalDataImportFileUploadedResponse",
    "LocalDataImportUploadItemResponse",
    "ResourceEnabledRequest",
]
