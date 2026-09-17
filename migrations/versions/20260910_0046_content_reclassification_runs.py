"""建立旧 Content 品牌车型重分类的可恢复 Run。

Revision ID: 20260910_0046
Revises: 20260910_0045
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0046"
down_revision: str | Sequence[str] | None = "20260910_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立冻结范围、Keyset 检查点与累计对账统计。"""

    op.create_table(
        "content_reclassification_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("shard_index", sa.Integer(), nullable=False),
        sa.Column("shard_count", sa.Integer(), nullable=False),
        sa.Column("start_after_content_id", sa.Uuid()),
        sa.Column("end_at_content_id", sa.Uuid()),
        sa.Column("checkpoint_content_id", sa.Uuid()),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("max_contents", sa.BigInteger(), nullable=False),
        sa.Column("processed_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("matched_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("unmatched_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("brand_evidence_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("vehicle_evidence_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("conflict_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("brand_locked_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("vehicle_locked_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "shard_count > 0",
            name=op.f("ck_content_reclassification_runs_shard_count_positive"),
        ),
        sa.CheckConstraint(
            "shard_index >= 0 and shard_index < shard_count",
            name=op.f("ck_content_reclassification_runs_shard_index_within_count"),
        ),
        sa.CheckConstraint(
            "batch_size > 0 and batch_size <= 1000",
            name=op.f("ck_content_reclassification_runs_batch_size_range"),
        ),
        sa.CheckConstraint(
            "max_contents > 0",
            name=op.f("ck_content_reclassification_runs_max_contents_positive"),
        ),
        sa.CheckConstraint(
            "processed_count >= 0 and matched_count >= 0 and unmatched_count >= 0 "
            "and brand_evidence_count >= 0 and vehicle_evidence_count >= 0 "
            "and conflict_count >= 0 and brand_locked_count >= 0 and vehicle_locked_count >= 0",
            name=op.f("ck_content_reclassification_runs_counters_nonnegative"),
        ),
        sa.CheckConstraint(
            "processed_count <= max_contents",
            name=op.f("ck_content_reclassification_runs_processed_within_max"),
        ),
        sa.CheckConstraint(
            "end_at_content_id is null or start_after_content_id is null "
            "or start_after_content_id < end_at_content_id",
            name=op.f("ck_content_reclassification_runs_content_range_ordered"),
        ),
        sa.CheckConstraint(
            "char_length(created_by) between 1 and 200",
            name=op.f("ck_content_reclassification_runs_created_by_length"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_content_reclassification_runs_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_reclassification_runs")),
        sa.UniqueConstraint("job_id", name=op.f("uq_content_reclassification_runs_job_id")),
    )
    op.create_index(
        op.f("ix_content_reclassification_runs_created_at"),
        "content_reclassification_runs",
        ["created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """删除重分类 Run；已写入的 Brand/Vehicle Evidence 保持不变。"""

    op.drop_index(
        op.f("ix_content_reclassification_runs_created_at"),
        table_name="content_reclassification_runs",
    )
    op.drop_table("content_reclassification_runs")
