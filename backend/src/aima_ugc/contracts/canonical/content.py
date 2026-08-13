"""Canonical V1 内容原子 Observation。"""

from typing import Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field

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
