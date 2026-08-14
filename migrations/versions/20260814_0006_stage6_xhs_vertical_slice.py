"""建立 Stage 6 小红书纵切 Content/Candidate 业务事实。

Revision ID: 20260814_0006
Revises: 20260814_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0006"
down_revision: str | Sequence[str] | None = "20260814_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_account_id", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text()),
        sa.Column("display_name", sa.Text()),
        sa.Column("profile_url", sa.Text()),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("bio", sa.Text()),
        sa.Column("verified", sa.Boolean()),
        sa.Column("verification_label", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("current_follower_count", sa.BigInteger()),
        sa.Column("current_following_count", sa.BigInteger()),
        sa.Column("current_content_count", sa.BigInteger()),
        sa.Column("current_total_like_count", sa.BigInteger()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint(
            "platform", "external_account_id", name=op.f("uq_accounts_platform_external_account_id")
        ),
    )
    op.create_table(
        "contents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_content_id", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("share_url", sa.Text()),
        sa.Column("author_account_id", sa.Uuid()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("current_like_count", sa.BigInteger()),
        sa.Column("current_comment_count", sa.BigInteger()),
        sa.Column("current_share_count", sa.BigInteger()),
        sa.Column("current_repost_count", sa.BigInteger()),
        sa.Column("current_favorite_count", sa.BigInteger()),
        sa.Column("current_view_count", sa.BigInteger()),
        sa.Column("current_play_count", sa.BigInteger()),
        sa.Column("current_danmaku_count", sa.BigInteger()),
        sa.Column("current_coin_count", sa.BigInteger()),
        sa.Column("current_download_count", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_account_id"], ["accounts.id"], name=op.f("fk_contents_author_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contents")),
        sa.UniqueConstraint(
            "platform", "external_content_id", name=op.f("uq_contents_platform_external_content_id")
        ),
        sa.CheckConstraint(
            "current_version >= 1", name=op.f("ck_contents_current_version_positive")
        ),
    )
    op.create_index(
        "ix_contents_platform_last_seen",
        "contents",
        ["platform", "last_seen_at"],
        unique=False,
    )
    op.create_table(
        "content_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("share_url", sa.Text()),
        sa.Column("author_snapshot", postgresql.JSONB()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text()),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"], ["contents.id"], name=op.f("fk_content_versions_content_id_contents")
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_content_versions_provider_attempt_id_provider_request_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"], ["artifacts.id"], name=op.f("fk_content_versions_raw_artifact_id_artifacts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_versions")),
        sa.UniqueConstraint(
            "content_id", "version_no", name=op.f("uq_content_versions_content_id_version_no")
        ),
        sa.CheckConstraint(
            "version_no >= 1", name=op.f("ck_content_versions_version_no_positive")
        ),
    )
    op.create_table(
        "content_metric_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("observation_key", sa.Text(), nullable=False),
        sa.Column("like_count", sa.BigInteger()),
        sa.Column("comment_count", sa.BigInteger()),
        sa.Column("share_count", sa.BigInteger()),
        sa.Column("repost_count", sa.BigInteger()),
        sa.Column("favorite_count", sa.BigInteger()),
        sa.Column("view_count", sa.BigInteger()),
        sa.Column("play_count", sa.BigInteger()),
        sa.Column("danmaku_count", sa.BigInteger()),
        sa.Column("coin_count", sa.BigInteger()),
        sa.Column("download_count", sa.BigInteger()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"], ["contents.id"], name=op.f("fk_content_metric_observations_content_id_contents")
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_content_metric_observations_provider_attempt_id_provider_request_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"], ["artifacts.id"], name=op.f("fk_content_metric_observations_raw_artifact_id_artifacts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_metric_observations")),
        sa.UniqueConstraint(
            "content_id", "observation_key", name=op.f("uq_content_metric_observations_content_id_observation_key")
        ),
        sa.CheckConstraint(
            "reason in ('initial','changed','daily_checkpoint')",
            name=op.f("ck_content_metric_observations_reason_allowed"),
        ),
    )
    op.create_index(
        "uq_content_metric_daily_checkpoint",
        "content_metric_observations",
        ["content_id", "business_date"],
        unique=True,
        postgresql_where=sa.text("reason = 'daily_checkpoint'"),
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("external_comment_id", sa.Text(), nullable=False),
        sa.Column("root_comment_id", sa.Text()),
        sa.Column("parent_comment_id", sa.Text()),
        sa.Column("author_account_id", sa.Uuid()),
        sa.Column("text", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text()),
        sa.Column("is_by_content_author", sa.Boolean()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_like_count", sa.BigInteger()),
        sa.Column("current_reply_count", sa.BigInteger()),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"], ["contents.id"], name=op.f("fk_comments_content_id_contents")
        ),
        sa.ForeignKeyConstraint(
            ["author_account_id"], ["accounts.id"], name=op.f("fk_comments_author_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
        sa.UniqueConstraint(
            "content_id", "external_comment_id", name=op.f("uq_comments_content_id_external_comment_id")
        ),
        sa.CheckConstraint(
            "current_version >= 1", name=op.f("ck_comments_current_version_positive")
        ),
    )
    op.create_index(
        "ix_comments_content_id_last_seen", "comments", ["content_id", "last_seen_at"], unique=False
    )
    op.create_table(
        "comment_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("root_comment_id", sa.Text()),
        sa.Column("parent_comment_id", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("author_snapshot", postgresql.JSONB()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text()),
        sa.Column("is_by_content_author", sa.Boolean()),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["comment_id"], ["comments.id"], name=op.f("fk_comment_versions_comment_id_comments")
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_comment_versions_provider_attempt_id_provider_request_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"], ["artifacts.id"], name=op.f("fk_comment_versions_raw_artifact_id_artifacts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comment_versions")),
        sa.UniqueConstraint(
            "comment_id", "version_no", name=op.f("uq_comment_versions_comment_id_version_no")
        ),
        sa.CheckConstraint(
            "version_no >= 1", name=op.f("ck_comment_versions_version_no_positive")
        ),
    )
    op.create_table(
        "comment_metric_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("observation_key", sa.Text(), nullable=False),
        sa.Column("like_count", sa.BigInteger()),
        sa.Column("reply_count", sa.BigInteger()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["comment_id"], ["comments.id"], name=op.f("fk_comment_metric_observations_comment_id_comments")
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_comment_metric_observations_provider_attempt_id_provider_request_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"], ["artifacts.id"], name=op.f("fk_comment_metric_observations_raw_artifact_id_artifacts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comment_metric_observations")),
        sa.UniqueConstraint(
            "comment_id", "observation_key", name=op.f("uq_comment_metric_observations_comment_id_observation_key")
        ),
        sa.CheckConstraint(
            "reason in ('initial','changed','daily_checkpoint')",
            name=op.f("ck_comment_metric_observations_reason_allowed"),
        ),
    )
    op.create_index(
        "uq_comment_metric_daily_checkpoint",
        "comment_metric_observations",
        ["comment_id", "business_date"],
        unique=True,
        postgresql_where=sa.text("reason = 'daily_checkpoint'"),
    )
    op.create_table(
        "comment_coverage_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("coverage", sa.Text(), nullable=False),
        sa.Column("reported_total", sa.BigInteger()),
        sa.Column("collected_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"], ["contents.id"], name=op.f("fk_comment_coverage_observations_content_id_contents")
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_comment_coverage_observations_provider_attempt_id_provider_request_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"], ["artifacts.id"], name=op.f("fk_comment_coverage_observations_raw_artifact_id_artifacts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comment_coverage_observations")),
        sa.CheckConstraint(
            "coverage in ('complete','partial','not_requested','unavailable')",
            name=op.f("ck_comment_coverage_observations_coverage_allowed"),
        ),
        sa.CheckConstraint(
            "collected_count >= 0",
            name=op.f("ck_comment_coverage_observations_collected_count_nonnegative"),
        ),
    )
    op.create_table(
        "collection_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_request_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.Text(), nullable=False),
        sa.Column("external_item_id", sa.Text()),
        sa.Column("item_locator", sa.Text(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_request_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_collection_candidates_provider_request_attempt_id_provider_request_attempts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_candidates")),
        sa.UniqueConstraint(
            "provider_request_attempt_id",
            "item_locator",
            name=op.f("uq_collection_candidates_provider_request_attempt_id_item_locator"),
        ),
        sa.CheckConstraint(
            "item_kind in ('content','comment')",
            name=op.f("ck_collection_candidates_item_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(item_locator) > 0",
            name=op.f("ck_collection_candidates_item_locator_nonempty"),
        ),
    )
    op.create_table(
        "collection_candidate_ingestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_no", sa.Integer(), nullable=False),
        sa.Column("canonical_version", sa.Text()),
        sa.Column("canonical_identity", sa.Text()),
        sa.Column("observed_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_type", sa.Text()),
        sa.Column("content_id", sa.Uuid()),
        sa.Column("comment_id", sa.Uuid()),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_detail", sa.Text()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["collection_candidates.id"], name=op.f("fk_collection_candidate_ingestions_candidate_id_collection_candidates")
        ),
        sa.ForeignKeyConstraint(
            ["content_id"], ["contents.id"], name=op.f("fk_collection_candidate_ingestions_content_id_contents")
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"], ["comments.id"], name=op.f("fk_collection_candidate_ingestions_comment_id_comments")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_candidate_ingestions")),
        sa.UniqueConstraint(
            "candidate_id", "ingestion_no", name=op.f("uq_collection_candidate_ingestions_candidate_id_ingestion_no")
        ),
        sa.CheckConstraint(
            "ingestion_no >= 1",
            name=op.f("ck_collection_candidate_ingestions_ingestion_no_positive"),
        ),
        sa.CheckConstraint(
            "result in ('ingested','duplicate','invalid','unsupported','failed')",
            name=op.f("ck_collection_candidate_ingestions_result_allowed"),
        ),
        sa.CheckConstraint(
            "(target_type = 'content' and content_id is not null and comment_id is null) or "
            "(target_type = 'comment' and comment_id is not null and content_id is null) or "
            "(target_type is null and content_id is null and comment_id is null)",
            name=op.f("ck_collection_candidate_ingestions_target_consistent"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(observed_fields) = 'array'",
            name=op.f("ck_collection_candidate_ingestions_observed_fields_array"),
        ),
    )
    op.execute(
        """
        CREATE FUNCTION validate_collection_candidate_source() RETURNS trigger AS $$
        DECLARE attempt_status text; artifact_id uuid; artifact_status text;
        BEGIN
          SELECT dispatch_status, raw_artifact_id INTO attempt_status, artifact_id
          FROM provider_request_attempts WHERE id = NEW.provider_request_attempt_id;
          IF attempt_status <> 'completed' OR artifact_id IS NULL THEN
            RAISE EXCEPTION 'Candidate 必须来自 completed 且已绑定 Raw 的 Provider Attempt';
          END IF;
          SELECT status INTO artifact_status FROM artifacts WHERE id = artifact_id;
          IF artifact_status <> 'linked' THEN
            RAISE EXCEPTION 'Candidate Raw Artifact 必须已 linked';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE CONSTRAINT TRIGGER trg_collection_candidate_source_valid
        AFTER INSERT ON collection_candidates DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_collection_candidate_source();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_candidate_ingestion_target() RETURNS trigger AS $$
        DECLARE expected_kind text; expected_platform text; target_platform text;
        BEGIN
          SELECT c.item_kind, s.platform INTO expected_kind, expected_platform
          FROM collection_candidates c
          JOIN provider_request_attempts a ON a.id = c.provider_request_attempt_id
          JOIN provider_requests r ON r.id = a.provider_request_id
          JOIN collection_scopes s ON s.id = r.scope_id
          WHERE c.id = NEW.candidate_id;
          IF NEW.target_type IS NOT NULL AND NEW.target_type <> expected_kind THEN
            RAISE EXCEPTION 'Candidate item_kind 与 Ingestion target_type 不一致';
          END IF;
          IF NEW.target_type = 'content' THEN
            SELECT platform INTO target_platform FROM contents WHERE id = NEW.content_id;
          ELSIF NEW.target_type = 'comment' THEN
            SELECT c2.platform INTO target_platform FROM comments cm JOIN contents c2 ON c2.id = cm.content_id WHERE cm.id = NEW.comment_id;
          END IF;
          IF NEW.target_type IS NOT NULL AND target_platform IS DISTINCT FROM expected_platform THEN
            RAISE EXCEPTION 'Candidate 与 Ingestion 目标平台不一致';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE CONSTRAINT TRIGGER trg_candidate_ingestion_target_valid
        AFTER INSERT ON collection_candidate_ingestions DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_candidate_ingestion_target();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_candidate_ingestion_target_valid ON collection_candidate_ingestions")
    op.execute("DROP FUNCTION IF EXISTS validate_candidate_ingestion_target()")
    op.execute("DROP TRIGGER IF EXISTS trg_collection_candidate_source_valid ON collection_candidates")
    op.execute("DROP FUNCTION IF EXISTS validate_collection_candidate_source()")
    op.drop_table("collection_candidate_ingestions")
    op.drop_table("collection_candidates")
    op.drop_table("comment_coverage_observations")
    op.drop_index("uq_comment_metric_daily_checkpoint", table_name="comment_metric_observations")
    op.drop_table("comment_metric_observations")
    op.drop_table("comment_versions")
    op.drop_index("ix_comments_content_id_last_seen", table_name="comments")
    op.drop_table("comments")
    op.drop_index("uq_content_metric_daily_checkpoint", table_name="content_metric_observations")
    op.drop_table("content_metric_observations")
    op.drop_table("content_versions")
    op.drop_index("ix_contents_platform_last_seen", table_name="contents")
    op.drop_table("contents")
    op.drop_table("accounts")
