"""增加 Data Import Campaign 可审计撤销事实。

Revision ID: 20260907_0041
Revises: 20260903_0040
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0041"
down_revision: str | Sequence[str] | None = "20260903_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增独立撤销事实，不改写 Campaign 终态或 Content 历史。"""

    op.create_table(
        "historical_import_campaign_revocations",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("affected_content_count", sa.Integer(), nullable=False),
        sa.Column("hidden_content_count", sa.Integer(), nullable=False),
        sa.Column("retained_shared_content_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(actor_ref) > 0", name=op.f("ck_historical_import_campaign_revocations_actor_ref_nonempty")),
        sa.CheckConstraint(
            "reason is null or char_length(reason) > 0",
            name=op.f("ck_historical_import_campaign_revocations_reason_nonempty"),
        ),
        sa.CheckConstraint(
            "affected_content_count >= 0 and hidden_content_count >= 0 "
            "and retained_shared_content_count >= 0",
            name=op.f("ck_historical_import_campaign_revocations_counts_nonnegative"),
        ),
        sa.CheckConstraint(
            "hidden_content_count + retained_shared_content_count = affected_content_count",
            name=op.f("ck_historical_import_campaign_revocations_impact_counts_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["historical_import_campaigns.id"],
            name=op.f("fk_historical_import_campaign_revocations_campaign_id_historical_import_campaigns"),
        ),
        sa.PrimaryKeyConstraint(
            "campaign_id",
            name=op.f("pk_historical_import_campaign_revocations"),
        ),
    )


def downgrade() -> None:
    """只移除撤销投影事实，不删除任何历史导入或 Content 数据。"""

    op.drop_table("historical_import_campaign_revocations")
