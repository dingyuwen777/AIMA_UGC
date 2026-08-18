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


def _source_columns() -> tuple[sa.Column, sa.Column, sa.Column]:
    return (
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def _source_foreign_keys(table_name: str) -> None:
    op.create_foreign_key(
        f"fk_{table_name}_provider_attempt_id_provider_request_attempts",
        table_name,
        "provider_request_attempts",
        ["provider_attempt_id"],
        ["id"],
    )
    op.create_foreign_key(
        f"fk_{table_name}_raw_artifact_id_artifacts",
        table_name,
        "artifacts",
        ["raw_artifact_id"],
        ["id"],
    )
    op.create_foreign_key(
        f"fk_{table_name}_attempt_raw_source",
        table_name,
        "provider_request_attempts",
        ["provider_attempt_id", "raw_artifact_id"],
        ["id", "raw_artifact_id"],
    )


def upgrade() -> None:
    op.create_table(
        "collection_plan_decision_policies",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jsonb_typeof(policy) = 'object'", name="ck_collection_plan_decision_policies_policy_object"),
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
        sa.Column("detail_action", sa.Text(), nullable=False),
        sa.Column("detail_reason", sa.Text(), nullable=False),
        sa.Column("comment_action", sa.Text(), nullable=False),
        sa.Column("comment_reason", sa.Text(), nullable=False),
        sa.Column("comment_target", sa.Integer()),
        sa.Column("reply_target_per_root", sa.Integer()),
        sa.Column("resolved_comment_count", sa.BigInteger()),
        sa.Column("detail_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("comments_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(external_content_id) > 0", name="ck_collection_content_actions_external_content_id_nonempty"),
        sa.CheckConstraint("detail_action in ('fetch','skip')", name="ck_collection_content_actions_detail_action_allowed"),
        sa.CheckConstraint(
            "comment_action in ('skip','fetch_adaptive','fetch_incremental','refresh_controlled','probe_first_page','defer_until_detail')",
            name="ck_collection_content_actions_comment_action_allowed",
        ),
        sa.CheckConstraint("comment_target is null or comment_target >= 1", name="ck_collection_content_actions_comment_target_positive"),
        sa.CheckConstraint("reply_target_per_root is null or reply_target_per_root >= 1", name="ck_collection_content_actions_reply_target_positive"),
        sa.CheckConstraint("resolved_comment_count is null or resolved_comment_count >= 0", name="ck_collection_content_actions_resolved_comment_count_nonnegative"),
        sa.CheckConstraint(
            "comments_completed = false or detail_completed = true or detail_action = 'skip'",
            name="ck_collection_content_actions_completion_order",
        ),
        sa.ForeignKeyConstraint(["scope_id"], ["collection_scopes.id"]),
        sa.ForeignKeyConstraint(["search_provider_attempt_id"], ["provider_request_attempts.id"]),
        sa.ForeignKeyConstraint(["search_raw_artifact_id"], ["artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_id", "external_content_id"),
    )

    op.create_table(
        "content_external_ids",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("id_type", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        *_source_columns(),
        sa.CheckConstraint("char_length(id_type) > 0", name="ck_content_external_ids_id_type_nonempty"),
        sa.CheckConstraint("char_length(external_id) > 0", name="ck_content_external_ids_external_id_nonempty"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "id_type"),
    )
    op.create_table(
        "content_media",
        sa.Column("content_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name="ck_content_media_position_nonnegative"),
        sa.CheckConstraint("media_type in ('image','video','live_photo','audio','cover','other')", name="ck_content_media_media_type_allowed"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "position"),
    )
    op.create_table(
        "content_topics",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("external_topic_id", sa.Text()),
        sa.Column("url", sa.Text()),
        *_source_columns(),
        sa.CheckConstraint("position >= 0", name="ck_content_topics_position_nonnegative"),
        sa.CheckConstraint("char_length(name) > 0", name="ck_content_topics_name_nonempty"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "position"),
    )
    op.create_table(
        "content_mentions",
        sa.Column("content_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name="ck_content_mentions_position_nonnegative"),
        sa.CheckConstraint("jsonb_typeof(alternate_ids) = 'object'", name="ck_content_mentions_alternate_ids_object"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "position"),
    )
    op.create_table(
        "content_locations",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("location_type", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("country", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        *_source_columns(),
        sa.CheckConstraint("position >= 0", name="ck_content_locations_position_nonnegative"),
        sa.CheckConstraint("location_type in ('place','ip_region')", name="ck_content_locations_location_type_allowed"),
        sa.CheckConstraint("latitude is null or latitude between -90 and 90", name="ck_content_locations_latitude_range"),
        sa.CheckConstraint("longitude is null or longitude between -180 and 180", name="ck_content_locations_longitude_range"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("content_id", "position"),
    )

    op.create_table(
        "comment_media",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name="ck_comment_media_position_nonnegative"),
        sa.CheckConstraint("media_type in ('image','video','live_photo','audio','cover','other')", name="ck_comment_media_media_type_allowed"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.PrimaryKeyConstraint("comment_id", "position"),
    )
    op.create_table(
        "comment_mentions",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name="ck_comment_mentions_position_nonnegative"),
        sa.CheckConstraint("jsonb_typeof(alternate_ids) = 'object'", name="ck_comment_mentions_alternate_ids_object"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.PrimaryKeyConstraint("comment_id", "position"),
    )
    op.create_table(
        "comment_locations",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("location_type", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("country", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        *_source_columns(),
        sa.CheckConstraint("position >= 0", name="ck_comment_locations_position_nonnegative"),
        sa.CheckConstraint("location_type in ('place','ip_region')", name="ck_comment_locations_location_type_allowed"),
        sa.CheckConstraint("latitude is null or latitude between -90 and 90", name="ck_comment_locations_latitude_range"),
        sa.CheckConstraint("longitude is null or longitude between -180 and 180", name="ck_comment_locations_longitude_range"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.PrimaryKeyConstraint("comment_id", "position"),
    )
    op.create_table(
        "comment_thread_coverage_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("root_comment_id", sa.Text(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("coverage", sa.Text(), nullable=False),
        sa.Column("reported_total", sa.BigInteger()),
        sa.Column("captured_count", sa.BigInteger(), nullable=False),
        sa.Column("target_count", sa.BigInteger()),
        sa.Column("stop_reason", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(root_comment_id) > 0", name="ck_comment_thread_coverage_observations_root_comment_id_nonempty"),
        sa.CheckConstraint("coverage in ('complete','partial','not_requested','unavailable')", name="ck_comment_thread_coverage_observations_coverage_allowed"),
        sa.CheckConstraint("captured_count >= 0", name="ck_comment_thread_coverage_observations_captured_count_nonnegative"),
        sa.CheckConstraint("reported_total is null or reported_total >= 0", name="ck_comment_thread_coverage_observations_reported_total_nonnegative"),
        sa.CheckConstraint("target_count is null or target_count >= 0", name="ck_comment_thread_coverage_observations_target_count_nonnegative"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", "root_comment_id", "provider_attempt_id", "raw_artifact_id", name="uq_comment_thread_coverage_source"),
    )

    op.create_unique_constraint(
        "uq_provider_request_attempts_id_raw_artifact",
        "provider_request_attempts",
        ["id", "raw_artifact_id"],
    )

    source_tables = (
        "content_versions",
        "content_metric_observations",
        "comment_versions",
        "comment_metric_observations",
        "comment_coverage_observations",
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
    existing_source_tables = {
        "content_versions",
        "content_metric_observations",
        "comment_versions",
        "comment_metric_observations",
        "comment_coverage_observations",
    }
    for table_name in source_tables:
        if table_name not in existing_source_tables:
            _source_foreign_keys(table_name)
        else:
            op.create_foreign_key(
                f"fk_{table_name}_attempt_raw_source",
                table_name,
                "provider_request_attempts",
                ["provider_attempt_id", "raw_artifact_id"],
                ["id", "raw_artifact_id"],
            )


def downgrade() -> None:
    source_tables = (
        "content_versions",
        "content_metric_observations",
        "comment_versions",
        "comment_metric_observations",
        "comment_coverage_observations",
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
    for table_name in source_tables:
        op.drop_constraint(f"fk_{table_name}_attempt_raw_source", table_name, type_="foreignkey")

    op.drop_constraint(
        "uq_provider_request_attempts_id_raw_artifact",
        "provider_request_attempts",
        type_="unique",
    )

    for table_name in (
        "comment_thread_coverage_observations",
        "comment_locations",
        "comment_mentions",
        "comment_media",
        "content_locations",
        "content_mentions",
        "content_topics",
        "content_media",
        "content_external_ids",
        "collection_content_actions",
        "collection_plan_decision_policies",
    ):
        op.drop_table(table_name)
