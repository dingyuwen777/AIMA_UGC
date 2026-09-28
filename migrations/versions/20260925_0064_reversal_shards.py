"""给普通导入撤销和重筛撤回增加可恢复的 Content 工作单元。

Revision ID: 20260925_0064
Revises: 20260924_0063
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0064"
down_revision: str | Sequence[str] | None = "20260924_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_reversal_shards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "import_campaign_id",
            sa.Uuid(),
            sa.ForeignKey("historical_import_revocation_requests.campaign_id"),
        ),
        sa.Column(
            "replay_request_id", sa.Uuid(), sa.ForeignKey("canonical_replay_all_requests.id")
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("lower_content_id", sa.Uuid(), nullable=False),
        sa.Column("upper_content_id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("checkpoint_content_id", sa.Uuid()),
        sa.Column("processed_content_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "(kind = 'import' and import_campaign_id is not null and replay_request_id is null) "
            "or (kind = 'replay' and import_campaign_id is null and replay_request_id is not null)",
            name="kind_parent_consistent",
        ),
        sa.CheckConstraint(
            "status in ('pending','queued','running','succeeded','failed')",
            name="status_allowed",
        ),
        sa.CheckConstraint(
            "ordinal >= 0 and processed_content_count >= 0",
            name="counts_nonnegative",
        ),
        sa.CheckConstraint(
            "upper_content_id is null or lower_content_id < upper_content_id",
            name="range_ordered",
        ),
        sa.CheckConstraint(
            "checkpoint_content_id is null or checkpoint_content_id >= lower_content_id",
            name="checkpoint_in_range",
        ),
        sa.UniqueConstraint(
            "import_campaign_id", "ordinal", name="uq_reversal_shard_import_ordinal"
        ),
        sa.UniqueConstraint(
            "replay_request_id", "ordinal", name="uq_reversal_shard_replay_ordinal"
        ),
    )
    op.create_index(
        "ix_reversal_shards_import_status",
        "ingestion_reversal_shards",
        ["import_campaign_id", "status"],
    )
    op.create_index(
        "ix_reversal_shards_replay_status",
        "ingestion_reversal_shards",
        ["replay_request_id", "status"],
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM ingestion_reversal_shards LIMIT 1")).first():
        raise RuntimeError("撤回分片事实仍存在，不能安全 downgrade 0064")
    op.drop_index("ix_reversal_shards_replay_status", table_name="ingestion_reversal_shards")
    op.drop_index("ix_reversal_shards_import_status", table_name="ingestion_reversal_shards")
    op.drop_table("ingestion_reversal_shards")
