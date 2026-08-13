"""Canonical V1 评论原子 Observation。"""

from typing import Literal

from pydantic import AwareDatetime, Field

from .author import CanonicalAuthorV1
from .base import CanonicalObservationModel, Identifier, PlatformName
from .media import CanonicalLocationV1, CanonicalMediaV1, CanonicalMentionV1
from .metrics import CanonicalMetricsV1
from .source import CanonicalSourceV1


class CanonicalCommentV1(CanonicalObservationModel):
    """一条评论或回复的完整原子事实。"""

    schema_version: Literal["comment.v1"] = "comment.v1"
    platform: PlatformName
    external_content_id: Identifier
    external_comment_id: Identifier
    alternate_ids: dict[str, Identifier] = Field(default_factory=dict)
    root_comment_id: Identifier | None = None
    parent_comment_id: Identifier | None = None
    author: CanonicalAuthorV1 | None = None
    text: str | None = None
    published_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    observed_at: AwareDatetime
    metrics: CanonicalMetricsV1 = Field(default_factory=CanonicalMetricsV1)
    media: list[CanonicalMediaV1] = Field(default_factory=list)
    mentions: list[CanonicalMentionV1] = Field(default_factory=list)
    locations: list[CanonicalLocationV1] = Field(default_factory=list)
    is_by_content_author: bool | None = None
    status: str | None = None
    source: CanonicalSourceV1
