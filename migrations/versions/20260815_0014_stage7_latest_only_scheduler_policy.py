"""固化 Stage 7 Scheduler latest-only 停机恢复策略。

Revision ID: 20260815_0014
Revises: 20260815_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0014"
down_revision: str | Sequence[str] | None = "20260815_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """拒绝与首版已批准 latest-only 语义冲突的 Plan。"""
    op.create_check_constraint(
        op.f("ck_collection_plans_misfire_policy_latest_only"),
        "collection_plans",
        "misfire_policy = 'latest_only'",
    )
    op.create_check_constraint(
        op.f("ck_collection_plans_max_catch_up_runs_first_release"),
        "collection_plans",
        "max_catch_up_runs = 0",
    )


def downgrade() -> None:
    """只撤销策略约束，不改写既有 Plan 数据。"""
    op.drop_constraint(
        op.f("ck_collection_plans_max_catch_up_runs_first_release"),
        "collection_plans",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_collection_plans_misfire_policy_latest_only"),
        "collection_plans",
        type_="check",
    )
