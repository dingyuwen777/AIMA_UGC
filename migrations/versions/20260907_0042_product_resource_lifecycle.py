"""增加可归档产品配置资源生命周期。

Revision ID: 20260907_0042
Revises: 20260907_0041
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0042"
down_revision: str | Sequence[str] | None = "20260907_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为词包、采集计划、Provider 与 Analysis Scheme 增加独立归档状态。"""

    op.add_column(
        "keyword_packs",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_keyword_packs_archived_keyword_pack_disabled"),
        "keyword_packs",
        "archived_at is null or not enabled",
    )

    op.add_column(
        "collection_plans",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_collection_plans_archived_collection_plan_disabled"),
        "collection_plans",
        "archived_at is null or not enabled",
    )

    op.add_column(
        "provider_configs",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_provider_configs_archived_provider_inactive"),
        "provider_configs",
        "archived_at is null or (not enabled and not is_default)",
    )

    op.add_column(
        "analysis_schemes",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_analysis_schemes_archived_analysis_scheme_inactive"),
        "analysis_schemes",
        "archived_at is null or not is_active",
    )


def downgrade() -> None:
    """移除归档列；不改写任何资源的原有 enabled/active/configuration 历史。"""

    op.drop_constraint(
        op.f("ck_analysis_schemes_archived_analysis_scheme_inactive"),
        "analysis_schemes",
        type_="check",
    )
    op.drop_column("analysis_schemes", "archived_at")

    op.drop_constraint(
        op.f("ck_provider_configs_archived_provider_inactive"),
        "provider_configs",
        type_="check",
    )
    op.drop_column("provider_configs", "archived_at")

    op.drop_constraint(
        op.f("ck_collection_plans_archived_collection_plan_disabled"),
        "collection_plans",
        type_="check",
    )
    op.drop_column("collection_plans", "archived_at")

    op.drop_constraint(
        op.f("ck_keyword_packs_archived_keyword_pack_disabled"),
        "keyword_packs",
        type_="check",
    )
    op.drop_column("keyword_packs", "archived_at")
