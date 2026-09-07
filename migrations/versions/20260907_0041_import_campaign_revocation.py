"""增加 Content 来源贡献与 Data Import Campaign 可审计撤销事实。

Revision ID: 20260907_0041
Revises: 20260903_0040
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0041"
down_revision: str | Sequence[str] | None = "20260903_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增不可变来源 Delta、撤销事实与撤销生成 Version 追溯，不删除历史数据。"""

    op.create_table(
        "content_source_contributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_item_key", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("version_before", sa.Integer(), nullable=True),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.Column("delta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(source_item_key) = 64",
            name=op.f("ck_content_source_contributions_source_item_key_sha256"),
        ),
        sa.CheckConstraint(
            "version_before is null or version_before >= 1",
            name=op.f("ck_content_source_contributions_version_before_positive"),
        ),
        sa.CheckConstraint(
            "version_after >= 1",
            name=op.f("ck_content_source_contributions_version_after_positive"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(delta) = 'object'",
            name=op.f("ck_content_source_contributions_delta_object"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_source_contributions_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f(
                "fk_content_source_contributions_provider_attempt_id_provider_request_attempts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_content_source_contributions_raw_artifact_id_artifacts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_source_contributions")),
        sa.UniqueConstraint(
            "source_item_key",
            name=op.f("uq_content_source_contributions_source_item_key"),
        ),
    )

    op.create_table(
        "historical_import_campaign_revocations",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("affected_content_count", sa.Integer(), nullable=False),
        sa.Column("hidden_content_count", sa.Integer(), nullable=False),
        sa.Column("retained_shared_content_count", sa.Integer(), nullable=False),
        sa.Column("unreversible_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(actor_ref) > 0",
            name=op.f("ck_historical_import_campaign_revocations_actor_ref_nonempty"),
        ),
        sa.CheckConstraint(
            "reason is null or char_length(reason) > 0",
            name=op.f("ck_historical_import_campaign_revocations_reason_nonempty"),
        ),
        sa.CheckConstraint(
            "affected_content_count >= 0 and hidden_content_count >= 0 "
            "and retained_shared_content_count >= 0 and unreversible_content_count >= 0",
            name=op.f("ck_historical_import_campaign_revocations_counts_nonnegative"),
        ),
        sa.CheckConstraint(
            "hidden_content_count + retained_shared_content_count = affected_content_count",
            name=op.f("ck_historical_import_campaign_revocations_impact_balanced"),
        ),
        sa.CheckConstraint(
            "unreversible_content_count <= affected_content_count",
            name=op.f("ck_historical_import_campaign_revocations_unrev_le_affected"),
        ),
        sa.CheckConstraint(
            "unreversible_content_count = 0",
            name=op.f("ck_historical_import_campaign_revocations_fully_reversible"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["historical_import_campaigns.id"],
            name=op.f(
                "fk_historical_import_campaign_revocations_campaign_id_historical_import_campaigns"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "campaign_id",
            name=op.f("pk_historical_import_campaign_revocations"),
        ),
    )

    op.create_table(
        "historical_import_revocation_content_versions",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version_no >= 1",
            name=op.f("ck_historical_import_revocation_content_versions_version_ge_1"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["historical_import_campaign_revocations.campaign_id"],
            name=op.f(
                "fk_historical_import_revocation_content_versions_campaign_id_historical_import_campaign_revocations"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_historical_import_revocation_content_versions_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id", "version_no"],
            ["content_versions.content_id", "content_versions.version_no"],
            name=op.f("fk_import_revocation_content_version"),
        ),
        sa.PrimaryKeyConstraint(
            "campaign_id",
            "content_id",
            name=op.f("pk_historical_import_revocation_content_versions"),
        ),
    )
    op.execute(
        """
        CREATE FUNCTION reject_import_revocation_ledger_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% 是追加账本，禁止 %', TG_TABLE_NAME, TG_OP;
        END; $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_content_source_contributions_append_only
        BEFORE UPDATE OR DELETE ON content_source_contributions
        FOR EACH ROW EXECUTE FUNCTION reject_import_revocation_ledger_mutation();

        CREATE TRIGGER trg_historical_import_campaign_revocations_append_only
        BEFORE UPDATE OR DELETE ON historical_import_campaign_revocations
        FOR EACH ROW EXECUTE FUNCTION reject_import_revocation_ledger_mutation();

        CREATE TRIGGER trg_historical_import_revocation_content_versions_append_only
        BEFORE UPDATE OR DELETE ON historical_import_revocation_content_versions
        FOR EACH ROW EXECUTE FUNCTION reject_import_revocation_ledger_mutation();
        """
    )


def downgrade() -> None:
    """移除生命周期新表；既有 Content/Raw/历史版本保持不变。"""

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_historical_import_revocation_content_versions_append_only
        ON historical_import_revocation_content_versions;
        DROP TRIGGER IF EXISTS trg_historical_import_campaign_revocations_append_only
        ON historical_import_campaign_revocations;
        DROP TRIGGER IF EXISTS trg_content_source_contributions_append_only
        ON content_source_contributions;
        DROP FUNCTION IF EXISTS reject_import_revocation_ledger_mutation();
        """
    )
    op.drop_table("historical_import_revocation_content_versions")
    op.drop_table("historical_import_campaign_revocations")
    op.drop_table("content_source_contributions")
