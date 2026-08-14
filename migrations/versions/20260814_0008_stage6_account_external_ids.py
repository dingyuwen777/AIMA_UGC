"""增加 Stage 6 账号备用稳定外部 ID 关系表。

Revision ID: 20260814_0008
Revises: 20260814_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0008"
down_revision: str | Sequence[str] | None = "20260814_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_external_ids",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("id_type", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_account_external_ids_account_id_accounts"),
        ),
        sa.UniqueConstraint(
            "account_id",
            "id_type",
            name=op.f("uq_account_external_ids_account_id_id_type"),
        ),
        sa.UniqueConstraint(
            "id_type",
            "external_id",
            name=op.f("uq_account_external_ids_id_type_external_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("account_external_ids")
