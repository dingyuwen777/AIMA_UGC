"""为 Collection Plan 增加品牌过滤范围关联。

Revision ID: 20260910_0045
Revises: 20260909_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0045"
down_revision: str | Sequence[str] | None = "20260909_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """以 Expand-only 方式保存 Plan 的 selected Brand Scope。"""

    op.create_table(
        "collection_plan_brands",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["vehicle_brands.id"],
            name=op.f("fk_collection_plan_brands_brand_id_vehicle_brands"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["collection_plans.id"],
            name=op.f("fk_collection_plan_brands_plan_id_collection_plans"),
        ),
        sa.PrimaryKeyConstraint(
            "plan_id",
            "brand_id",
            name=op.f("pk_collection_plan_brands"),
        ),
    )


def downgrade() -> None:
    """移除 Plan Brand Expand 表，不触碰 Stage 7 才清理的旧表。"""

    op.drop_table("collection_plan_brands")
