"""Canonical V1 内容聚合读取结构。"""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from .base import CanonicalBaseModel, NonNegativeInt
from .comment import CanonicalCommentV1
from .content import CanonicalContentV1
from .source import CanonicalSourceV1


class CanonicalCommentCoverageV1(CanonicalBaseModel):
    status: Literal["complete", "partial", "not_requested", "unavailable"]
    reported_total: NonNegativeInt | None = None
    captured_count: NonNegativeInt
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.reported_total is not None and self.captured_count > self.reported_total:
            raise ValueError("captured_count 不能大于 reported_total")
        if self.status in {"not_requested", "unavailable"} and self.captured_count != 0:
            raise ValueError("未请求或不可用时 captured_count 必须为 0")
        return self


class CanonicalCommentThreadV1(CanonicalBaseModel):
    root_comment: CanonicalCommentV1
    replies: list[CanonicalCommentV1] = Field(default_factory=list)
    coverage: CanonicalCommentCoverageV1

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        root = self.root_comment
        if root.parent_comment_id is not None:
            raise ValueError("线程根评论的 parent_comment_id 必须为空")
        if root.root_comment_id not in {None, root.external_comment_id}:
            raise ValueError("线程根评论的 root_comment_id 必须为空或等于自身 ID")
        for reply in self.replies:
            if reply.platform != root.platform:
                raise ValueError("同一评论线程的平台必须一致")
            if reply.external_content_id != root.external_content_id:
                raise ValueError("同一评论线程必须属于同一内容")
            if reply.root_comment_id != root.external_comment_id:
                raise ValueError("回复的 root_comment_id 必须指向线程根评论")
        return self


class CanonicalAggregateSystemV1(CanonicalBaseModel):
    first_seen_at: AwareDatetime
    last_seen_at: AwareDatetime
    latest_observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_seen_range(self) -> Self:
        if self.first_seen_at > self.last_seen_at:
            raise ValueError("first_seen_at 不能晚于 last_seen_at")
        return self


class CanonicalContentAggregateV1(CanonicalBaseModel):
    schema_version: Literal["content.aggregate.v1"] = "content.aggregate.v1"
    content: CanonicalContentV1
    comment_coverage: CanonicalCommentCoverageV1
    comment_threads: list[CanonicalCommentThreadV1] = Field(default_factory=list)
    unthreaded_comments: list[CanonicalCommentV1] = Field(default_factory=list)
    system: CanonicalAggregateSystemV1
    lineage: list[CanonicalSourceV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content_relationships(self) -> Self:
        comments = list(self.unthreaded_comments)
        for thread in self.comment_threads:
            comments.append(thread.root_comment)
            comments.extend(thread.replies)

        for comment in comments:
            if comment.platform != self.content.platform:
                raise ValueError("聚合内评论平台必须与内容平台一致")
            if comment.external_content_id != self.content.external_content_id:
                raise ValueError("聚合内评论必须属于当前内容")

        if len(comments) != self.comment_coverage.captured_count:
            raise ValueError("comment_coverage.captured_count 必须等于聚合内已采集评论数")
        return self
