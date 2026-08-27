"""增加 Stage 12 历史迁移 Campaign、Manifest 与逐行账本。

Revision ID: 20260826_0026
Revises: 20260824_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_0026"
down_revision: str | Sequence[str] | None = "20260824_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_import_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_idempotency_key", sa.Text(), nullable=False),
        sa.Column("root_relative_path", sa.Text(), nullable=False),
        sa.Column("recursive", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "keyword_pack_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("discovered_file_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ready_item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_rows", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status in ('discovering','snapshotting','ready','queued','running','cancelling',"
            "'cancelled','succeeded','partial_failed','failed')",
            name=op.f("ck_historical_import_campaigns_status_allowed"),
        ),
        sa.CheckConstraint(
            "discovered_file_count >= 0",
            name=op.f("ck_historical_import_campaigns_discovered_files_nonnegative"),
        ),
        sa.CheckConstraint(
            "ready_item_count >= 0",
            name=op.f("ck_historical_import_campaigns_ready_item_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "total_rows >= 0",
            name=op.f("ck_historical_import_campaigns_total_rows_nonnegative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(profile_snapshot) = 'object'",
            name=op.f("ck_historical_import_campaigns_profile_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(keyword_pack_snapshot) = 'object'",
            name=op.f("ck_historical_import_campaigns_keyword_pack_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(stats) = 'object'",
            name=op.f("ck_historical_import_campaigns_stats_object"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_idempotency_key"),
    )
    op.create_index(
        "ix_historical_import_campaigns_status_created_at",
        "historical_import_campaigns",
        ["status", "created_at"],
    )
    op.create_table(
        "historical_import_campaign_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("parent_item_id", sa.Uuid()),
        sa.Column("item_kind", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("manifest_identity", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer()),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("file_mtime_ns", sa.BigInteger()),
        sa.Column("artifact_id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("sha256", sa.Text()),
        sa.Column("row_start", sa.BigInteger()),
        sa.Column("row_end", sa.BigInteger()),
        sa.Column("row_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "item_kind in ('source_file','chunk')",
            name=op.f("ck_historical_import_campaign_items_item_kind_allowed"),
        ),
        sa.CheckConstraint(
            "status in ('discovered','snapshotting','ready','queued','running','succeeded',"
            "'failed','cancelled')",
            name=op.f("ck_historical_import_campaign_items_status_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(manifest_identity) = 64",
            name=op.f("ck_historical_import_campaign_items_manifest_identity_sha256"),
        ),
        sa.CheckConstraint(
            "sha256 is null or char_length(sha256) = 64",
            name=op.f("ck_historical_import_campaign_items_sha256_length"),
        ),
        sa.CheckConstraint(
            "ordinal is null or ordinal >= 0",
            name=op.f("ck_historical_import_campaign_items_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "file_size is null or file_size >= 0",
            name=op.f("ck_historical_import_campaign_items_file_size_nonnegative"),
        ),
        sa.CheckConstraint(
            "row_count >= 0",
            name=op.f("ck_historical_import_campaign_items_row_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_historical_import_campaign_items_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(stats) = 'object'",
            name=op.f("ck_historical_import_campaign_items_stats_object"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["historical_import_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(
            ["parent_item_id"],
            ["historical_import_campaign_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
        sa.UniqueConstraint(
            "campaign_id",
            "relative_path",
            "manifest_identity",
            "item_kind",
            "ordinal",
            name="uq_historical_import_campaign_items_manifest",
        ),
    )
    op.create_index(
        "ix_historical_import_campaign_items_campaign_status",
        "historical_import_campaign_items",
        ["campaign_id", "status"],
    )
    op.create_index(
        "uq_historical_import_campaign_items_source_manifest",
        "historical_import_campaign_items",
        ["campaign_id", "relative_path", "manifest_identity"],
        unique=True,
        postgresql_where=sa.text("item_kind = 'source_file'"),
    )

    op.add_column(
        "processing_import_batches",
        sa.Column("historical_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "processing_import_batches",
        sa.Column("historical_campaign_item_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "processing_import_batches",
        sa.Column("historical_policy_version", sa.Text(), nullable=True),
    )
    op.add_column(
        "processing_import_batches",
        sa.Column("retry_of_batch_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pib_history_item",
        "processing_import_batches",
        "historical_import_campaign_items",
        ["historical_campaign_item_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_pib_retry",
        "processing_import_batches",
        "processing_import_batches",
        ["retry_of_batch_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_processing_import_batches_historical_fields_consistent"),
        "processing_import_batches",
        "(historical_mode and historical_campaign_item_id is not null "
        "and historical_policy_version is not null) or "
        "(not historical_mode and historical_campaign_item_id is null "
        "and historical_policy_version is null and retry_of_batch_id is null)",
    )

    op.create_table(
        "processing_import_batch_identities",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("identity_hash", sa.Text(), nullable=False),
        sa.Column("first_row_ordinal", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "char_length(identity_hash) = 64",
            name=op.f("ck_processing_import_batch_identities_identity_hash_sha256"),
        ),
        sa.CheckConstraint(
            "first_row_ordinal >= 1",
            name=op.f("ck_processing_import_batch_identities_first_row_positive"),
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["processing_import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("batch_id", "identity_hash"),
    )
    op.create_table(
        "processing_import_batch_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_item_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_ordinal", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.Text()),
        sa.Column("external_content_id_hash", sa.Text()),
        sa.Column("content_id", sa.Uuid()),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("filled_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conflict_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("committed_chunk_ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_row_ordinal >= 1",
            name=op.f("ck_processing_import_batch_items_source_row_ordinal_positive"),
        ),
        sa.CheckConstraint(
            "outcome in ('created','filled','unchanged','conflict','filtered','duplicate',"
            "'invalid','failed')",
            name=op.f("ck_processing_import_batch_items_outcome_allowed"),
        ),
        sa.CheckConstraint(
            "filled_count >= 0",
            name=op.f("ck_processing_import_batch_items_filled_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "conflict_count >= 0",
            name=op.f("ck_processing_import_batch_items_conflict_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "committed_chunk_ordinal >= 0",
            name=op.f("ck_processing_import_batch_items_chunk_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "external_content_id_hash is null or char_length(external_content_id_hash) = 64",
            name=op.f("ck_processing_import_batch_items_external_id_hash_sha256"),
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["processing_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_item_id"], ["historical_import_campaign_items.id"]),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "source_row_ordinal",
            name="uq_processing_import_batch_items_batch_row",
        ),
    )
    op.create_index(
        "ix_processing_import_batch_items_campaign_item_outcome",
        "processing_import_batch_items",
        ["campaign_item_id", "outcome"],
    )
    op.create_table(
        "processing_import_batch_item_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_item_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("current_value_hash", sa.Text(), nullable=False),
        sa.Column("historical_value_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version >= 1",
            name=op.f("ck_processing_import_batch_item_conflicts_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(current_value_hash) = 64",
            name=op.f("ck_processing_import_batch_item_conflicts_current_hash_sha256"),
        ),
        sa.CheckConstraint(
            "char_length(historical_value_hash) = 64",
            name=op.f("ck_processing_import_batch_item_conflicts_history_hash_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["batch_item_id"], ["processing_import_batch_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_item_id",
            "field_name",
            name="uq_processing_import_batch_item_conflicts_field",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION reject_historical_import_ledger_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% 是追加账本，禁止 %', TG_TABLE_NAME, TG_OP;
        END; $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_processing_import_batch_items_append_only
        BEFORE UPDATE OR DELETE ON processing_import_batch_items
        FOR EACH ROW EXECUTE FUNCTION reject_historical_import_ledger_mutation();

        CREATE TRIGGER trg_processing_import_batch_item_conflicts_append_only
        BEFORE UPDATE OR DELETE ON processing_import_batch_item_conflicts
        FOR EACH ROW EXECUTE FUNCTION reject_historical_import_ledger_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_processing_import_batch_item_conflicts_append_only
        ON processing_import_batch_item_conflicts;
        DROP TRIGGER IF EXISTS trg_processing_import_batch_items_append_only
        ON processing_import_batch_items;
        DROP FUNCTION IF EXISTS reject_historical_import_ledger_mutation();
        """
    )
    op.drop_table("processing_import_batch_item_conflicts")
    op.drop_index(
        "ix_processing_import_batch_items_campaign_item_outcome",
        table_name="processing_import_batch_items",
    )
    op.drop_table("processing_import_batch_items")
    op.drop_table("processing_import_batch_identities")
    op.drop_constraint(
        op.f("ck_processing_import_batches_historical_fields_consistent"),
        "processing_import_batches",
        type_="check",
    )
    op.drop_constraint(
        "fk_pib_retry",
        "processing_import_batches",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_pib_history_item",
        "processing_import_batches",
        type_="foreignkey",
    )
    op.drop_column("processing_import_batches", "retry_of_batch_id")
    op.drop_column("processing_import_batches", "historical_policy_version")
    op.drop_column("processing_import_batches", "historical_campaign_item_id")
    op.drop_column("processing_import_batches", "historical_mode")
    op.drop_index(
        "uq_historical_import_campaign_items_source_manifest",
        table_name="historical_import_campaign_items",
        if_exists=True,
    )
    op.drop_index(
        "ix_historical_import_campaign_items_campaign_status",
        table_name="historical_import_campaign_items",
    )
    op.drop_table("historical_import_campaign_items")
    op.drop_index(
        "ix_historical_import_campaigns_status_created_at",
        table_name="historical_import_campaigns",
    )
    op.drop_table("historical_import_campaigns")
