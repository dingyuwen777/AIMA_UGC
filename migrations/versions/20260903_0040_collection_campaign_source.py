"""允许 Collection Run 追溯 Data Import Campaign 来源。

Revision ID: 20260903_0040
Revises: 20260903_0039
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0040"
down_revision: str | Sequence[str] | None = "20260903_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增可空 Campaign 外键，并禁止一个 Run 同时绑定两种导入来源。"""

    op.add_column(
        "collection_runs",
        sa.Column("data_import_campaign_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_collection_runs_data_import_campaign_id_historical_import_campaigns"),
        "collection_runs",
        "historical_import_campaigns",
        ["data_import_campaign_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_collection_runs_import_source_at_most_one"),
        "collection_runs",
        "import_batch_id is null or data_import_campaign_id is null",
    )
    op.create_index(
        "ix_collection_runs_campaign_id_created_at",
        "collection_runs",
        ["data_import_campaign_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    """只移除 Collection Run 的 Campaign 关联，不改写导入或内容事实。"""

    op.drop_index(
        "ix_collection_runs_campaign_id_created_at",
        table_name="collection_runs",
    )
    op.drop_constraint(
        op.f("ck_collection_runs_import_source_at_most_one"),
        "collection_runs",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_collection_runs_data_import_campaign_id_historical_import_campaigns"),
        "collection_runs",
        type_="foreignkey",
    )
    op.drop_column("collection_runs", "data_import_campaign_id")
