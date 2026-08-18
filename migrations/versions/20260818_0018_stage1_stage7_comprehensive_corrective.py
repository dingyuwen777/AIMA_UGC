"""补齐 Stage 1-7 动作恢复、Canonical 子实体与来源约束。

Revision ID: 20260818_0018
Revises: 20260817_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260818_0018"
down_revision: str | Sequence[str] | None = "20260817_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_POLICY = """{
  "comments_enabled": true,
  "comment_trigger": "new_or_comment_changed",
  "comment_mode": "adaptive",
  "full_fetch_threshold": 50,
  "sample_target": 50,
  "reply_target_per_root": 5,
  "comment_sort": "latest_if_supported",
  "comment_refresh_when_count_unchanged": false,
  "auto_deep_collection": false
}"""

_EXISTING_SOURCE_TABLES = (
    "content_versions",
    "content_metric_observations",
    "comment_versions",
    "comment_metric_observations",
    "comment_coverage_observations",
)
_NEW_SOURCE_TABLES = (
    "content_external_ids",
    "content_media",
    "content_topics",
    "content_mentions",
    "content_locations",
    "comment_media",
    "comment_mentions",
    "comment_locations",
    "comment_thread_coverage_observations",
)


def _source_columns() -> tuple[sa.Column, sa.Column, sa.Column]:
    return (
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_source_fk(table_name: str) -> None:
    op.create_foreign_key(
        f"fk_{table_name}_attempt_raw_source",
        table_name,
        "provider_request_attempts",
        ["provider_attempt_id", "raw_artifact_id"],
        ["id", "raw_artifact_id"],
    )


def _preflight_existing_sources() -> None:
    bind = op.get_bind()
    for table_name in _EXISTING_SOURCE_TABLES:
        mismatches = bind.execute(
            sa.text(
                f"SELECT count(*) FROM {table_name} source "
                "JOIN provider_request_attempts attempt "
                "ON attempt.id = source.provider_attempt_id "
                "WHERE attempt.raw_artifact_id IS DISTINCT FROM source.raw_artifact_id"
            )
        ).scalar_one()
        if mismatches:
            raise RuntimeError(
                f"{table_name} 存在 {mismatches} 条 Attempt/Raw 来源不一致历史数据，"
                "拒绝创建复合来源约束"
            )


def _create_media_table(table_name: str, parent_table: str, parent_column: str) -> None:
    op.create_table(
        table_name,
        sa.Column(parent_column, sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("external_media_id", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("preview_url", sa.Text()),
        sa.Column("width", sa.BigInteger()),
        sa.Column("height", sa.BigInteger()),
        sa.Column("duration_ms", sa.BigInteger()),
        sa.Column("mime_type", sa.Text()),
        sa.Column("alt_text", sa.Text()),
        *_source_columns(),
        sa.CheckConstraint(
            "position >= 0",
            name="position_nonnegative",
        ),
        sa.CheckConstraint(
            "media_type in ('image','video','live_photo','audio','cover','other')",
            name="media_type_allowed",
        ),
        sa.ForeignKeyConstraint([parent_column], [f"{parent_table}.id"]),
        sa.PrimaryKeyConstraint(parent_column, "position"),
    )


def _create_mentions_table(table_name: str, parent_table: str, parent_column: str) -> None:
    op.create_table(
        table_name,
        sa.Column(parent_column, sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("external_account_id", sa.Text()),
        sa.Column("handle", sa.Text()),
        sa.Column("display_name", sa.Text()),
        sa.Column("profile_url", sa.Text()),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("bio", sa.Text()),
        sa.Column("verified", sa.Boolean()),
        sa.Column("verification_label", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("follower_count", sa.BigInteger()),
        sa.Column("following_count", sa.BigInteger()),
        sa.Column("content_count", sa.BigInteger()),
        sa.Column("total_like_count", sa.BigInteger()),
        sa.Column("alternate_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("display_text", sa.Text()),
        *_source_columns(),
        sa.CheckConstraint(
            "position >= 0",
            name="position_nonnegative",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(alternate_ids) = 'object'",
            name="alternate_ids_object",
        ),
        sa.ForeignKeyConstraint([parent_column], [f"{parent_table}.id"]),
        sa.PrimaryKeyConstraint(parent_column, "position"),
    )


def _create_locations_table(table_name: str, parent_table: str, parent_column: str) -> None:
    op.create_table(
        table_name,
        sa.Column(parent_column, sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("location_type", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("country", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        *_source_columns(),
        sa.CheckConstraint(
            "position >= 0",
            name="position_nonnegative",
        ),
        sa.CheckConstraint(
            "location_type in ('place','ip_region')",
            name="location_type_allowed",
        ),
        sa.CheckConstraint(
            "latitude is null or latitude between -90 and 90",
            name="latitude_range",
        ),
        sa.CheckConstraint(
            "longitude is null or longitude between -180 and 180",
            name="longitude_range",
        ),
        sa.ForeignKeyConstraint([parent_column], [f"{parent_table}.id"]),
        sa.PrimaryKeyConstraint(parent_column, "position"),
    )


def upgrade() -> None:
    _preflight_existing_sources()
    op.create_unique_constraint(
        "uq_provider_request_attempts_id_raw_artifact",
        "provider_request_attempts",
        ["id", "raw_artifact_id"],
    )

    op.create_table(
        "collection_plan_decision_policies",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(policy) = 'object'",
            name="policy_object",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["collection_plans.id"]),
        sa.PrimaryKeyConstraint("plan_id"),
    )
    escaped_policy = _DEFAULT_POLICY.replace("'", "''")
    op.execute(
        sa.text(
            "INSERT INTO collection_plan_decision_policies(plan_id, policy, updated_at) "
            f"SELECT id, '{escaped_policy}'::jsonb, clock_timestamp() FROM collection_plans"
        )
    )

    op.create_table(
        "collection_content_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("external_content_id", sa.Text(), nullable=False),
        sa.Column("search_provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("search_raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("search_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_exists", sa.Boolean(), nullable=False),
        sa.Column("previous_comment_count", sa.BigInteger()),
        sa.Column("initial_business_changed", sa.Boolean(), nullable=False),
        sa.Column("detail_action", sa.Text(), nullable=False),
        sa.Column("detail_reason", sa.Text(), nullable=False),
        sa.Column("comment_action", sa.Text(), nullable=False),
        sa.Column("comment_reason", sa.Text(), nullable=False),
        sa.Column("comment_target", sa.Integer()),
        sa.Column("reply_target_per_root", sa.Integer()),
        sa.Column("resolved_comment_count", sa.BigInteger()),
        sa.Column(
            "detail_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "comments_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(external_content_id) > 0",
            name="external_content_id_nonempty",
        ),
        sa.CheckConstraint(
            "previous_comment_count is null or previous_comment_count >= 0",
            name="previous_count_nonneg",
        ),
        sa.CheckConstraint(
            "detail_action in ('fetch','skip')",
            name="detail_action_allowed",
        ),
        sa.CheckConstraint(
            "comment_action in "
            "('skip','fetch_adaptive','fetch_incremental','refresh_controlled',"
            "'probe_first_page','defer_until_detail')",
            name="comment_action_allowed",
        ),
        sa.CheckConstraint(
            "comment_target is null or comment_target >= 1",
            name="comment_target_positive",
        ),
        sa.CheckConstraint(
            "reply_target_per_root is null or reply_target_per_root >= 1",
            name="reply_target_positive",
        ),
        sa.CheckConstraint(
            "resolved_comment_count is null or resolved_comment_count >= 0",
            name="resolved_count_nonneg",
        ),
        sa.CheckConstraint(
            "comments_completed = false or detail_completed = true or detail_action = 'skip'",
            name="completion_order",
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["collection_scopes.id"]),
        sa.ForeignKeyConstraint(
            ["search_provider_attempt_id", "search_raw_artifact_id"],
            ["provider_request_attempts.id", "provider_request_attempts.raw_artifact_id"],
            name="fk_collection_actions_search_source",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_id", "external_content_id"),
    )

    op.create_table(
        "content_external_ids",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("id_type", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        *_source_columns(),
        sa.CheckConstraint(
            "char_length(id_type) > 0",
            name="id_type_nonempty",
        ),
        sa.CheckConstraint(
            "char_length(external_id) > 0",
            name="external_id_nonempty",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "id_type"),
    )
    _create_media_table("content_media", "contents", "content_id")
    op.create_table(
        "content_topics",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("external_topic_id", sa.Text()),
        sa.Column("url", sa.Text()),
        *_source_columns(),
        sa.CheckConstraint(
            "position >= 0",
            name="position_nonnegative",
        ),
        sa.CheckConstraint(
            "char_length(name) > 0",
            name="name_nonempty",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "position"),
    )
    _create_mentions_table("content_mentions", "contents", "content_id")
    _create_locations_table("content_locations", "contents", "content_id")
    _create_media_table("comment_media", "comments", "comment_id")
    _create_mentions_table("comment_mentions", "comments", "comment_id")
    _create_locations_table("comment_locations", "comments", "comment_id")

    op.create_table(
        "comment_thread_coverage_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("root_comment_id", sa.Text(), nullable=False),
        *_source_columns(),
        sa.Column("coverage", sa.Text(), nullable=False),
        sa.Column("reported_total", sa.BigInteger()),
        sa.Column("captured_count", sa.BigInteger(), nullable=False),
        sa.Column("target_count", sa.BigInteger()),
        sa.Column("stop_reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "char_length(root_comment_id) > 0",
            name="root_id_nonempty",
        ),
        sa.CheckConstraint(
            "coverage in ('complete','partial','not_requested','unavailable')",
            name="coverage_allowed",
        ),
        sa.CheckConstraint(
            "captured_count >= 0",
            name="captured_nonneg",
        ),
        sa.CheckConstraint(
            "reported_total is null or reported_total >= 0",
            name="reported_nonneg",
        ),
        sa.CheckConstraint(
            "target_count is null or target_count >= 0",
            name="target_nonneg",
        ),
        sa.CheckConstraint(
            "coverage <> 'complete' or reported_total is null or captured_count >= reported_total",
            name="complete_count",
        ),
        sa.CheckConstraint(
            "coverage not in ('not_requested','unavailable') or captured_count = 0",
            name="nonfetch_zero",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_id",
            "root_comment_id",
            "provider_attempt_id",
            "raw_artifact_id",
            name="uq_comment_thread_coverage_source",
        ),
    )

    for table_name in (*_EXISTING_SOURCE_TABLES, *_NEW_SOURCE_TABLES):
        _create_source_fk(table_name)


def downgrade() -> None:
    for table_name in _EXISTING_SOURCE_TABLES:
        op.drop_constraint(
            f"fk_{table_name}_attempt_raw_source",
            table_name,
            type_="foreignkey",
        )

    for table_name in reversed(_NEW_SOURCE_TABLES):
        op.drop_table(table_name)

    op.drop_table("collection_content_actions")
    op.drop_table("collection_plan_decision_policies")
    op.drop_constraint(
        "uq_provider_request_attempts_id_raw_artifact",
        "provider_request_attempts",
        type_="unique",
    )
