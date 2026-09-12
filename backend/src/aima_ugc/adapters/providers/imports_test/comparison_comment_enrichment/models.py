"""跨品牌车型共现帖子评论补采的离线输出模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehiclePairRecordV1,
)
from aima_ugc.contracts.canonical import CanonicalCommentV1


class _CommentEnrichmentBaseModel(BaseModel):
    """离线评论补采模型统一拒绝未声明字段。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CommentFetchFailureV1(_CommentEnrichmentBaseModel):
    """记录单帖评论补采中可安全持久化的 Provider 永久失败。"""

    stage: Literal["comments", "replies"]
    root_comment_id: str | None = Field(default=None, min_length=1, max_length=512)
    status_code: int = Field(ge=400, le=499)
    code: str = Field(min_length=1, max_length=128)
    safe_summary: str = Field(min_length=1, max_length=1024)
    raw_locator: str = Field(min_length=1, max_length=4096)


class CommentFetchCoverageV1(_CommentEnrichmentBaseModel):
    """描述一篇帖子本次评论补采的可验证覆盖范围。"""

    coverage: Literal["complete", "partial", "unavailable"]
    reported_total: int | None = Field(default=None, ge=0)
    root_comment_count: int = Field(ge=0)
    reply_count: int = Field(ge=0)
    request_count: int = Field(ge=0)
    root_stop_reason: str | None = Field(default=None, max_length=256)
    failures: tuple[CommentFetchFailureV1, ...] = ()

    @model_validator(mode="after")
    def validate_coverage(self) -> CommentFetchCoverageV1:
        """禁止把包含永久失败的记录标记为 complete。"""

        if self.coverage == "complete" and self.failures:
            raise ValueError("存在 Provider 永久失败时 coverage 不能为 complete")
        if self.coverage == "unavailable" and (self.root_comment_count or self.reply_count):
            raise ValueError("unavailable 不能同时声明已采集评论")
        return self


class VehiclePairCommentRecordV1(_CommentEnrichmentBaseModel):
    """保持一帖一行并附加该帖完整 Canonical 评论集合。"""

    schema_version: Literal["vehicle-pair-comment-record.v1"] = "vehicle-pair-comment-record.v1"
    record: VehiclePairRecordV1
    comments: tuple[CanonicalCommentV1, ...] = ()
    comment_fetch: CommentFetchCoverageV1

    @model_validator(mode="after")
    def validate_comments(self) -> VehiclePairCommentRecordV1:
        """保证评论归属、唯一性和 coverage 计数与实际 payload 一致。"""

        content = self.record.record.content
        keys: list[tuple[str, str]] = []
        root_count = 0
        reply_count = 0
        for comment in self.comments:
            if comment.platform != content.platform:
                raise ValueError("评论平台必须与帖子平台一致")
            if comment.external_content_id != content.external_content_id:
                raise ValueError("评论 external_content_id 必须与帖子一致")
            keys.append((comment.external_content_id, comment.external_comment_id))
            if (
                comment.root_comment_id == comment.external_comment_id
                and comment.parent_comment_id is None
            ):
                root_count += 1
            else:
                reply_count += 1
        if len(keys) != len(set(keys)):
            raise ValueError("同一帖子评论不能重复")
        if root_count != self.comment_fetch.root_comment_count:
            raise ValueError("一级评论计数与 comment_fetch 不一致")
        if reply_count != self.comment_fetch.reply_count:
            raise ValueError("二级回复计数与 comment_fetch 不一致")
        return self


__all__ = [
    "CommentFetchCoverageV1",
    "CommentFetchFailureV1",
    "VehiclePairCommentRecordV1",
]
