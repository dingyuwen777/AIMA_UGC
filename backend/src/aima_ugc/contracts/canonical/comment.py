"""Canonical V1 评论原子 Observation。"""

from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

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

    @field_validator("observed_fields")
    @classmethod
    def validate_observed_paths(cls, value: list[str]) -> list[str]:
        direct = {
            "alternate_ids",
            "root_comment_id",
            "parent_comment_id",
            "text",
            "published_at",
            "source_updated_at",
            "media",
            "mentions",
            "locations",
            "is_by_content_author",
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
            raise ValueError(f"评论 observed_fields 包含未声明或过粗的路径: {path}")
        return value
