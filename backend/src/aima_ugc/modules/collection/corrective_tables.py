"""Stage 1-7 全面整改新增的 Collection Owner 稳定表。"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

collection_plan_decision_policies_table = Table(
    "collection_plan_decision_policies",
    metadata,
    Column("plan_id", Uuid(), ForeignKey("collection_plans.id"), primary_key=True),
    Column("policy", JSONB(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("jsonb_typeof(policy) = 'object'", name="policy_object"),
    info={"owner": "collection"},
)

collection_content_actions_table = Table(
    "collection_content_actions",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("scope_id", Uuid(), ForeignKey("collection_scopes.id"), nullable=False),
    Column("external_content_id", Text(), nullable=False),
    Column(
        "search_provider_attempt_id",
        Uuid(),
        ForeignKey("provider_request_attempts.id"),
        nullable=False,
    ),
    Column("search_raw_artifact_id", Uuid(), ForeignKey("artifacts.id"), nullable=False),
    Column("search_observed_at", DateTime(timezone=True), nullable=False),
    Column("previous_exists", Boolean(), nullable=False),
    Column("previous_comment_count", BigInteger()),
    Column("initial_business_changed", Boolean(), nullable=False),
    Column("detail_action", Text(), nullable=False),
    Column("detail_reason", Text(), nullable=False),
    Column("comment_action", Text(), nullable=False),
    Column("comment_reason", Text(), nullable=False),
    Column("comment_target", Integer()),
    Column("reply_target_per_root", Integer()),
    Column("resolved_comment_count", BigInteger()),
    Column("detail_completed", Boolean(), nullable=False, server_default=text("false")),
    Column("comments_completed", Boolean(), nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("scope_id", "external_content_id"),
    CheckConstraint("char_length(external_content_id) > 0", name="external_content_id_nonempty"),
    CheckConstraint(
        "previous_comment_count is null or previous_comment_count >= 0",
        name="previous_comment_count_nonnegative",
    ),
    CheckConstraint("detail_action in ('fetch','skip')", name="detail_action_allowed"),
    CheckConstraint(
        "comment_action in "
        "('skip','fetch_adaptive','fetch_incremental','refresh_controlled',"
        "'probe_first_page','defer_until_detail')",
        name="comment_action_allowed",
    ),
    CheckConstraint(
        "comment_target is null or comment_target >= 1",
        name="comment_target_positive",
    ),
    CheckConstraint(
        "reply_target_per_root is null or reply_target_per_root >= 1",
        name="reply_target_positive",
    ),
    CheckConstraint(
        "resolved_comment_count is null or resolved_comment_count >= 0",
        name="resolved_comment_count_nonnegative",
    ),
    CheckConstraint(
        "comments_completed = false or detail_completed = true or detail_action = 'skip'",
        name="completion_order",
    ),
    info={"owner": "collection"},
)

__all__ = [
    "collection_content_actions_table",
    "collection_plan_decision_policies_table",
]
