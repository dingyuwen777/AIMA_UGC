"""Canonical V1 内容聚合读取结构。"""

from typing import Literal

from pydantic import AwareDatetime, Field

from .base import CanonicalBaseModel, NonNegativeInt
from .comment import CanonicalCommentV1
from .content import CanonicalContentV1


class CanonicalCommentCoverageV1(CanonicalBaseModel):
    status: Literal["complete", "partial", "not_requested", "unavailable"]
    reported_total: NonNegativeInt | None = None
    captured_count: NonNegativeInt
    observed_at: AwareDatetime


class CanonicalCommentThreadV1(CanonicalBaseModel):
    root_comment: CanonicalCommentV1
    replies: list[CanonicalCommentV1] = Field(default_factory=list)
    coverage: CanonicalCommentCoverageV1


class CanonicalContentAggregateV1(CanonicalBaseModel):
    schema_version: Literal["content.aggregate.v1"] = "content.aggregate.v1"
    content: CanonicalContentV1
    comment_coverage: CanonicalCommentCoverageV1
    comment_threads: list[CanonicalCommentThreadV1] = Field(default_factory=list)
    unthreaded_comments: list[CanonicalCommentV1] = Field(default_factory=list)
