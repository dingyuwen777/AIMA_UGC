"""Provider-neutral 统一数据 Excel V1 契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType


class _ExportBaseModel(BaseModel):
    """统一导出契约拒绝未声明字段，避免调用方私自扩展 Workbook Schema。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class UnifiedDataExcelLabelPairV1(_ExportBaseModel):
    """Excel 标签明细与主表多行展示共用的一级/二级标签对。"""

    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)


class UnifiedDataExcelAnalysisV1(_ExportBaseModel):
    """Excel 展示所需的分析投影；兼容单标签字符串并可携带完整标签对。"""

    relevance: ContentRelevance = "relevant"
    voice_type: ContentVoiceType = "unknown"
    is_user_voice: bool = False
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)
    primary_label: str = Field(default="", max_length=4096)
    secondary_label: str = Field(default="", max_length=4096)
    label_pairs: tuple[UnifiedDataExcelLabelPairV1, ...] = ()
    model: str | None = Field(default=None, max_length=256)
    prompt_version: str | None = Field(default=None, max_length=256)
    taxonomy_version: str | None = Field(default=None, max_length=256)

    @field_validator("label_pairs")
    @classmethod
    def validate_unique_label_pairs(
        cls, value: tuple[UnifiedDataExcelLabelPairV1, ...]
    ) -> tuple[UnifiedDataExcelLabelPairV1, ...]:
        keys = [(item.primary_label, item.secondary_label) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Excel Analysis label_pairs 不能重复")
        return value

    @model_validator(mode="after")
    def validate_user_voice_consistency(self) -> UnifiedDataExcelAnalysisV1:
        if self.is_user_voice != (self.voice_type == "user_voice"):
            raise ValueError("Excel Analysis is_user_voice 必须由 voice_type 派生")
        return self


class UnifiedDataExcelContentV1(_ExportBaseModel):
    """统一数据 Excel 的单条内容投影。"""

    platform: str = Field(min_length=1, max_length=64)
    external_content_id: str = Field(min_length=1, max_length=512)
    source_item_id: str | None = Field(default=None, max_length=512)
    content_type: str | None = Field(default=None, max_length=64)
    title: str | None = None
    text: str | None = None
    author_display_name: str | None = Field(default=None, max_length=1024)
    published_at: AwareDatetime | None = None
    content_url: str | None = Field(default=None, max_length=4096)
    author_follower_count: int | None = Field(default=None, ge=0)
    author_following_count: int | None = Field(default=None, ge=0)
    author_content_count: int | None = Field(default=None, ge=0)
    author_total_like_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    favorite_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    repost_count: int | None = Field(default=None, ge=0)
    view_count: int | None = Field(default=None, ge=0)
    play_count: int | None = Field(default=None, ge=0)
    danmaku_count: int | None = Field(default=None, ge=0)
    coin_count: int | None = Field(default=None, ge=0)
    download_count: int | None = Field(default=None, ge=0)
    matched_keywords: tuple[str, ...] = ()
    analysis: UnifiedDataExcelAnalysisV1 | None = None
    source_provider: str | None = Field(default=None, max_length=64)
    raw_locator: str | None = Field(default=None, max_length=4096)
    coverage: str | None = Field(default=None, max_length=1024)


class UnifiedDataExcelCommentV1(_ExportBaseModel):
    """统一数据 Excel 的单条评论投影。"""

    platform: str = Field(min_length=1, max_length=64)
    external_content_id: str = Field(min_length=1, max_length=512)
    level: str = Field(min_length=1, max_length=64)
    external_comment_id: str = Field(min_length=1, max_length=512)
    root_comment_id: str | None = Field(default=None, max_length=512)
    parent_comment_id: str | None = Field(default=None, max_length=512)
    author_display_name: str | None = Field(default=None, max_length=1024)
    text: str | None = None
    published_at: AwareDatetime | None = None
    like_count: int | None = Field(default=None, ge=0)
    reply_count: int | None = Field(default=None, ge=0)
    source_provider: str | None = Field(default=None, max_length=64)
    raw_locator: str | None = Field(default=None, max_length=4096)


class UnifiedDataExcelV1(_ExportBaseModel):
    """一个内容区块及其稳定关联评论的统一 Excel 输入契约。"""

    schema_version: Literal["unified-data-excel.v1"] = "unified-data-excel.v1"
    content: UnifiedDataExcelContentV1
    comments: tuple[UnifiedDataExcelCommentV1, ...] = ()
