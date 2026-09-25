"""在原有 Replay Run 去重边界内增加并行工作单元。

Revision ID: 20260925_0065
Revises: 20260925_0064
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0065"
down_revision: str | Sequence[str] | None = "20260925_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_replay_run_shards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("canonical_replay_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("shard_count", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("checkpoint_artifact_ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checkpoint_row_number", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_seen", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_matched", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_filtered_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duplicates_removed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_ingested", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("existing_convergence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "ordinal >= 0 and shard_count >= 1 and ordinal < shard_count",
            name="ordinal_range",
        ),
        sa.CheckConstraint(
            "status in ('pending','queued','running','succeeded','failed')",
            name="status_allowed",
        ),
        sa.CheckConstraint(
            "checkpoint_artifact_ordinal >= 0 and checkpoint_row_number >= 0",
            name="checkpoint_nonnegative",
        ),
        sa.CheckConstraint(
            "rows_seen >= 0 and rows_matched >= 0 and rows_filtered_out >= 0 "
            "and duplicates_removed >= 0 and rows_ingested >= 0 and existing_convergence >= 0 "
            "and rows_seen = rows_matched + rows_filtered_out "
            "and rows_matched = duplicates_removed + rows_ingested + existing_convergence",
            name="counters_reconciled",
        ),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_canonical_replay_run_shards_ordinal"),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM canonical_replay_run_shards LIMIT 1")).first():
        raise RuntimeError("Replay 分片事实仍存在，不能安全 downgrade 0065")
    op.drop_table("canonical_replay_run_shards")
