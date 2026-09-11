"""增加当前 Persistent Canonical Replay Run 与 clean-break 门禁。

Revision ID: 20260911_0051
Revises: 20260911_0050
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0051"
down_revision: str | Sequence[str] | None = "20260911_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """拒绝仍活跃或含糊的旧结构，再建立最小 Replay 父事实。"""

    connection = op.get_bind()
    active_legacy_jobs = connection.execute(
        sa.text(
            "SELECT count(*) FROM jobs "
            "WHERE job_type IN ('ingestion.import-excel.v1', "
            "'ingestion.historical-import-chunk.v1') "
            "AND status IN ('queued', 'running')"
        )
    ).scalar_one()
    if active_legacy_jobs:
        raise RuntimeError(
            "存在活跃 legacy Import Job；本版本只支持当前 v2 Persistent Canonical，"
            "必须先完成或取消旧任务"
        )

    unsupported_scope_links = connection.execute(
        sa.text(
            "SELECT count(*) FROM canonical_artifact_links WHERE collection_scope_id IS NOT NULL"
        )
    ).scalar_one()
    if unsupported_scope_links:
        raise RuntimeError(
            "存在已淘汰的 Scope-only Canonical lineage；必须先核对来源，不能猜测提升为 Replay 输入"
        )

    op.create_check_constraint(
        op.f("ck_canonical_artifact_links_scope_only_forbidden"),
        "canonical_artifact_links",
        "collection_scope_id is null",
    )

    unsupported_batch_links = connection.execute(
        sa.text(
            "SELECT count(*) FROM canonical_artifact_links link "
            "LEFT JOIN processing_import_batches batch "
            "ON batch.id = link.processing_import_batch_id "
            "LEFT JOIN jobs job ON job.id = batch.job_id "
            "WHERE link.processing_import_batch_id IS NOT NULL "
            "AND (batch.id IS NULL OR batch.historical_campaign_item_id IS NOT NULL "
            "OR job.job_type IS DISTINCT FROM 'ingestion.import-excel.v2')"
        )
    ).scalar_one()
    if unsupported_batch_links:
        raise RuntimeError(
            "存在不属于当前 Excel Import v2 的 Canonical lineage；本 clean break 不会静默转换"
        )

    unsupported_historical_links = connection.execute(
        sa.text(
            "SELECT count(*) FROM canonical_artifact_links link "
            "LEFT JOIN historical_import_campaign_items item "
            "ON item.id = link.historical_import_campaign_item_id "
            "LEFT JOIN jobs job ON job.id = item.job_id "
            "WHERE link.historical_import_campaign_item_id IS NOT NULL "
            "AND (item.id IS NULL OR item.item_kind IS DISTINCT FROM 'chunk' "
            "OR item.artifact_id IS DISTINCT FROM link.artifact_id "
            "OR job.job_type IS DISTINCT FROM 'ingestion.historical-import-chunk.v2')"
        )
    ).scalar_one()
    if unsupported_historical_links:
        raise RuntimeError(
            "存在不属于当前 Pure Canonical Chunk v2 的历史 lineage；"
            "旧 outcome Chunk 不会被误作 Canonical"
        )

    unsupported_tikhub_links = connection.execute(
        sa.text(
            "SELECT count(*) FROM canonical_artifact_links link "
            "LEFT JOIN provider_request_attempts attempt "
            "ON attempt.id = link.provider_attempt_id "
            "LEFT JOIN provider_requests request ON request.id = attempt.provider_request_id "
            "LEFT JOIN collection_scopes scope ON scope.id = request.scope_id "
            "LEFT JOIN collection_runs run ON run.id = scope.run_id "
            "LEFT JOIN jobs job ON job.id = run.job_id "
            "WHERE link.provider_attempt_id IS NOT NULL "
            "AND (attempt.id IS NULL OR attempt.dispatch_status IS DISTINCT FROM 'completed' "
            "OR attempt.raw_artifact_id IS NULL OR request.provider IS DISTINCT FROM 'tikhub' "
            "OR scope.operation_group IS DISTINCT FROM 'content_discovery' "
            "OR job.job_type IS DISTINCT FROM 'collection.run.v1')"
        )
    ).scalar_one()
    if unsupported_tikhub_links:
        raise RuntimeError(
            "存在无法证明为当前 TikHub Discovery Search Attempt 的 Canonical lineage；"
            "本 clean break 拒绝含糊来源"
        )

    op.create_table(
        "canonical_replay_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("client_idempotency_key", sa.Text(), nullable=False),
        sa.Column("filter_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_brand_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column(
            "checkpoint_artifact_ordinal", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "checkpoint_row_number", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("rows_seen", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_matched", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "rows_filtered_out", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "duplicates_removed", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("rows_ingested", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "existing_convergence", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_count between 1 and 100",
            name=op.f("ck_canonical_replay_runs_artifact_count_range"),
        ),
        sa.CheckConstraint(
            "batch_size between 1 and 1000",
            name=op.f("ck_canonical_replay_runs_batch_size_range"),
        ),
        sa.CheckConstraint(
            "checkpoint_artifact_ordinal between 0 and artifact_count "
            "and checkpoint_row_number >= 0 "
            "and (checkpoint_artifact_ordinal < artifact_count "
            "or checkpoint_row_number = 0)",
            name=op.f("ck_canonical_replay_runs_checkpoint_nonnegative"),
        ),
        sa.CheckConstraint(
            "char_length(client_idempotency_key) between 1 and 200",
            name=op.f("ck_canonical_replay_runs_idempotency_key_length"),
        ),
        sa.CheckConstraint(
            "char_length(created_by) between 1 and 200",
            name=op.f("ck_canonical_replay_runs_created_by_length"),
        ),
        sa.CheckConstraint(
            "rows_seen >= 0 and rows_matched >= 0 and rows_filtered_out >= 0 "
            "and duplicates_removed >= 0 and rows_ingested >= 0 "
            "and existing_convergence >= 0",
            name=op.f("ck_canonical_replay_runs_counters_nonnegative"),
        ),
        sa.CheckConstraint(
            "rows_seen = rows_matched + rows_filtered_out",
            name=op.f("ck_canonical_replay_runs_seen_reconciled"),
        ),
        sa.CheckConstraint(
            "rows_matched = duplicates_removed + rows_ingested + existing_convergence",
            name=op.f("ck_canonical_replay_runs_matched_reconciled"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(filter_snapshot) = 'object'",
            name=op.f("ck_canonical_replay_runs_filter_snapshot_object"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_canonical_replay_runs_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_canonical_replay_runs")),
        sa.UniqueConstraint(
            "client_idempotency_key",
            name=op.f("uq_canonical_replay_runs_client_idempotency_key"),
        ),
        sa.UniqueConstraint("job_id", name=op.f("uq_canonical_replay_runs_job_id")),
    )
    op.create_index(
        op.f("ix_canonical_replay_runs_created_at"),
        "canonical_replay_runs",
        ["created_at", "id"],
        unique=False,
    )
    op.create_table(
        "canonical_replay_run_artifacts",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0",
            name=op.f("ck_canonical_replay_run_artifacts_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "source_kind in ('excel_import_v2','data_import_canonical_chunk_v2',"
            "'tikhub_search_attempt_v1')",
            name=op.f("ck_canonical_replay_run_artifacts_source_kind_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_canonical_replay_run_artifacts_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["canonical_replay_runs.id"],
            name=op.f("fk_canonical_replay_run_artifacts_run_id_canonical_replay_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "run_id", "ordinal", name=op.f("pk_canonical_replay_run_artifacts")
        ),
        sa.UniqueConstraint(
            "run_id",
            "artifact_id",
            name=op.f("uq_canonical_replay_run_artifacts_input"),
        ),
    )
    op.create_index(
        op.f("ix_canonical_replay_run_artifacts_artifact_id"),
        "canonical_replay_run_artifacts",
        ["artifact_id"],
        unique=False,
    )
    op.create_table(
        "canonical_replay_seen_content",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_content_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "char_length(platform) > 0",
            name=op.f("ck_canonical_replay_seen_content_platform_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(external_content_id) > 0",
            name=op.f("ck_canonical_replay_seen_content_external_content_id_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["canonical_replay_runs.id"],
            name=op.f("fk_canonical_replay_seen_content_run_id_canonical_replay_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "run_id",
            "platform",
            "external_content_id",
            name=op.f("pk_canonical_replay_seen_content"),
        ),
    )


def downgrade() -> None:
    """删除 Replay 父事实；生产降级前必须确认没有仍需执行或审计的 Run。"""

    op.drop_table("canonical_replay_seen_content")
    op.drop_index(
        op.f("ix_canonical_replay_run_artifacts_artifact_id"),
        table_name="canonical_replay_run_artifacts",
    )
    op.drop_table("canonical_replay_run_artifacts")
    op.drop_index(
        op.f("ix_canonical_replay_runs_created_at"),
        table_name="canonical_replay_runs",
    )
    op.drop_table("canonical_replay_runs")
    op.drop_constraint(
        op.f("ck_canonical_artifact_links_scope_only_forbidden"),
        "canonical_artifact_links",
        type_="check",
    )
