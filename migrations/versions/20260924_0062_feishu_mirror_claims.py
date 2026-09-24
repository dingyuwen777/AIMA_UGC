"""为飞书镜像同步增加可抢占的 Lease/Fencing 字段。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0062"
down_revision: str | Sequence[str] | None = "20260924_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feishu_bitable_mirrors",
        sa.Column("claim_owner", sa.Text(), nullable=True),
    )
    op.add_column(
        "feishu_bitable_mirrors",
        sa.Column("claim_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "feishu_bitable_mirrors",
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_feishu_bitable_mirrors_claim_expires_at"),
        "feishu_bitable_mirrors",
        ["status", "next_sync_at", "claim_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_feishu_bitable_mirrors_claim_expires_at"),
        table_name="feishu_bitable_mirrors",
    )
    op.drop_column("feishu_bitable_mirrors", "claim_expires_at")
    op.drop_column("feishu_bitable_mirrors", "claim_token")
    op.drop_column("feishu_bitable_mirrors", "claim_owner")
