"""Stage 7 Collection Decision 与 Provider Capability V1 Contract。"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aima_ugc.contracts.provider.base import OperationName, PlatformName, ProviderName, StableCode

BusinessOperation = Literal["keyword_search", "content_detail", "comments", "sub_comments"]
DetailAction = Literal["fetch", "skip"]
CommentAction = Literal[
    "skip",
    "fetch_adaptive",
    "fetch_incremental",
    "refresh_controlled",
    "probe_first_page",
    "defer_until_detail",
]
ReplyAction = Literal["skip", "fetch_target", "probe_first_page"]
DetailReason = Literal[
    "detail_operation_unavailable",
    "manual_deep_collection",
    "scheduled_refresh_checkpoint",
    "new_content",
    "search_missing_required_fields",
    "configured_business_change",
    "unchanged",
]
CommentReason = Literal[
    "comments_disabled",
    "comments_operation_unavailable",
    "comments_unavailable",
    "provider_reported_zero",
    "comment_count_unchanged",
    "comment_count_unchanged_refresh",
    "new_content_comments",
    "comment_count_became_known",
    "comment_count_increased_incremental",
    "comment_count_increased_refresh",
    "comment_count_decreased",
    "comment_count_unknown_detail_required",
    "comment_count_unknown_probe",
]
ReplyReason = Literal[
    "sub_comments_unavailable",
    "reply_count_zero",
    "reply_count_positive",
    "reply_count_unknown_probe",
]


class CollectionBaseModel(BaseModel):
    """Collection V1 事实快照：拒绝额外字段并冻结实例。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CollectionSearchConfig(CollectionBaseModel):
    """Provider-neutral 搜索配置；合法值仍由当前 Platform Capability 决定。"""

    sort_mode: StableCode | None = None
    published_within: StableCode | None = None
    duration: StableCode | None = None
    content_type: StableCode | None = None


class ProviderOperationCapabilityV1(CollectionBaseModel):
    """一个 Provider + Platform 业务 Operation 可公开配置的能力。"""

    business_operation: BusinessOperation
    provider_operations: tuple[OperationName, ...] = Field(min_length=1)
    supported_sort_modes: tuple[StableCode, ...] = ()
    supported_time_filters: tuple[StableCode, ...] = ()
    supported_duration_filters: tuple[StableCode, ...] = ()
    supported_content_types: tuple[StableCode, ...] = ()
    native_time_filter: bool = False
    observes_comment_count: bool = False
    observes_comment_permission: bool = False
    comment_sort_modes: tuple[StableCode, ...] = ()
    supports_reply_count: bool = False
    supports_sub_comments: bool = False
    supports_incremental_comment_sort: bool = False
    provider_page_size_policy: Literal["fixed", "provider_default", "configurable", "unknown"] = (
        "unknown"
    )
    optional_enrichments: tuple[StableCode, ...] = ()


class ProviderPlatformCapabilityV1(CollectionBaseModel):
    """一个 Provider + Platform 当前已验证/实现的业务能力集合。"""

    schema_version: Literal["provider-platform-capability.v1"] = "provider-platform-capability.v1"
    provider: ProviderName
    platform: PlatformName
    operations: tuple[ProviderOperationCapabilityV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_business_operations(self) -> Self:
        operations = [item.business_operation for item in self.operations]
        if len(operations) != len(set(operations)):
            raise ValueError("Provider Platform Capability 存在重复业务 Operation")
        return self

    def operation(
        self, business_operation: BusinessOperation
    ) -> ProviderOperationCapabilityV1 | None:
        """按规范化业务 Operation 读取能力；不存在时返回 None。"""
        return next(
            (item for item in self.operations if item.business_operation == business_operation),
            None,
        )


class CollectionDecisionPolicyV1(CollectionBaseModel):
    """Stage 7 当前已批准的采集决策业务参数。"""

    comments_enabled: bool = True
    comment_trigger: Literal["new_or_comment_changed"] = "new_or_comment_changed"
    comment_mode: Literal["adaptive"] = "adaptive"
    full_fetch_threshold: int = Field(default=50, ge=1)
    sample_target: int = Field(default=50, ge=1)
    reply_target_per_root: int = Field(default=5, ge=1)
    comment_sort: Literal["latest_if_supported"] = "latest_if_supported"
    comment_refresh_when_count_unchanged: bool = False
    auto_deep_collection: bool = False


class ContentObservationV1(CollectionBaseModel):
    """Decision Service 所需的本次规范化内容事实，不包含 Provider Raw。"""

    comment_count: int | None = Field(default=None, ge=0)
    comments_available: bool | None = None
    search_missing_required_fields: bool = False
    business_changed: bool = False


class PreviousContentStateV1(CollectionBaseModel):
    """Decision Service 所需的上次当前状态最小快照。"""

    comment_count: int | None = Field(default=None, ge=0)


class CollectionDecisionContextV1(CollectionBaseModel):
    """不属于 Provider Raw 的显式业务触发上下文。"""

    manual_deep_collection: bool = False
    scheduled_refresh_checkpoint: bool = False


class CollectionDecisionRequestV1(CollectionBaseModel):
    """一次内容级后续采集决策的完整输入。"""

    schema_version: Literal["collection-decision-request.v1"] = "collection-decision-request.v1"
    current: ContentObservationV1
    previous: PreviousContentStateV1 | None = None
    context: CollectionDecisionContextV1 = Field(default_factory=CollectionDecisionContextV1)
    policy: CollectionDecisionPolicyV1 = Field(default_factory=CollectionDecisionPolicyV1)
    capability: ProviderPlatformCapabilityV1


class CollectionDecisionV1(CollectionBaseModel):
    """可审计的内容级详情/评论动作与原因。"""

    schema_version: Literal["collection-decision.v1"] = "collection-decision.v1"
    detail_action: DetailAction
    detail_reason: DetailReason
    comment_action: CommentAction
    comment_reason: CommentReason
    comment_target: int | None = Field(default=None, ge=1)
    reply_target_per_root: int | None = Field(default=None, ge=1)


class ReplyDecisionRequestV1(CollectionBaseModel):
    """一条一级评论是否继续抓二级回复的决策输入。"""

    schema_version: Literal["collection-reply-decision-request.v1"] = (
        "collection-reply-decision-request.v1"
    )
    reply_count: int | None = Field(default=None, ge=0)
    policy: CollectionDecisionPolicyV1 = Field(default_factory=CollectionDecisionPolicyV1)
    capability: ProviderPlatformCapabilityV1


class ReplyDecisionV1(CollectionBaseModel):
    """一条一级评论的二级回复动作与稳定原因。"""

    schema_version: Literal["collection-reply-decision.v1"] = "collection-reply-decision.v1"
    action: ReplyAction
    reason: ReplyReason
    target: int | None = Field(default=None, ge=1)
