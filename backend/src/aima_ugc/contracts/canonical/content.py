"""Canonical V1 内容原子 Observation。"""

from typing import Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, field_validator

from .author import CanonicalAuthorV1
from .base import CanonicalObservationModel, Identifier, PlatformName
from .media import (
    CanonicalLocationV1,
    CanonicalMediaV1,
    CanonicalMentionV1,
    CanonicalTopicV1,
)
from .metrics import CanonicalMetricsV1
from .source import CanonicalSourceV1


class CanonicalContentV1(CanonicalObservationModel):
    """一条帖子、笔记、视频或微博的完整原子事实。"""

    schema_version: Literal["content.v1"] = "content.v1"
    platform: PlatformName
    external_content_id: Identifier
    alternate_ids: dict[str, Identifier] = Field(default_factory=dict)
    content_type: str
    title: str | None = None
    text: str | None = None
    canonical_url: AnyHttpUrl | None = None
    share_url: AnyHttpUrl | None = None
    author: CanonicalAuthorV1 | None = None
    published_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    observed_at: AwareDatetime
    media: list[CanonicalMediaV1] = Field(default_factory=list)
    topics: list[CanonicalTopicV1] = Field(default_factory=list)
    mentions: list[CanonicalMentionV1] = Field(default_factory=list)
    locations: list[CanonicalLocationV1] = Field(default_factory=list)
    metrics: CanonicalMetricsV1 = Field(default_factory=CanonicalMetricsV1)
    status: str | None = None
    source: CanonicalSourceV1

    @field_validator("observed_fields")
    @classmethod
    def validate_observed_paths(cls, value: list[str]) -> list[str]:
        direct = {
            "alternate_ids",
            "content_type",
            "title",
            "text",
            "canonical_url",
            "share_url",
            "published_at",
            "source_updated_at",
            "media",
            "topics",
            "mentions",
            "locations",
            "status",
        }
        author_fields = set(CanonicalAuthorV1.model_fields)
        metric_fields = set(CanonicalMetricsV1.model_fields) - {"schema_version"}
        for path in value:
            if path in direct:
                continue
            if path.startswith("author.") and path.removeprefix("author.") in author_fields:
                continue
            if path.startswith("metrics.") and path.removeprefix("metrics.") in metric_fields:
                continue
            raise ValueError(f"内容 observed_fields 包含未声明或过粗的路径: {path}")
        return value
