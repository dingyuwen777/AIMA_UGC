"""支持 Analysis Scheme 从管理视图删除并保留历史版本快照。

Revision ID: 20260929_0075
Revises: 20260928_0074
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0075"
down_revision: str | Sequence[str] | None = "20260928_0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加删除 tombstone，并只对仍可管理的 Scheme 强制名称唯一。"""

    op.add_column(
        "analysis_schemes",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_analysis_schemes_deleted_analysis_scheme_archived_inactive"),
        "analysis_schemes",
        "deleted_at is null or (archived_at is not null and not is_active)",
    )
    op.drop_constraint(
        op.f("uq_analysis_schemes_name"),
        "analysis_schemes",
        type_="unique",
    )
    op.create_index(
        "uq_analysis_schemes_live_name",
        "analysis_schemes",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at is null"),
    )


def downgrade() -> None:
    """恢复旧全局唯一约束；存在同名 tombstone/live 资源时拒绝有损回滚。"""

    bind = op.get_bind()
    duplicate_name = bind.execute(
        sa.text(
            """
            SELECT name
            FROM analysis_schemes
            GROUP BY name
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if duplicate_name is not None:
        raise RuntimeError(
            "analysis_schemes 存在删除后重新创建的同名资源，"
            "无法安全恢复旧版全局名称唯一约束"
        )

    op.drop_index("uq_analysis_schemes_live_name", table_name="analysis_schemes")
    op.create_unique_constraint(
        op.f("uq_analysis_schemes_name"),
        "analysis_schemes",
        ["name"],
    )
    op.drop_constraint(
        op.f("ck_analysis_schemes_deleted_analysis_scheme_archived_inactive"),
        "analysis_schemes",
        type_="check",
    )
    op.drop_column("analysis_schemes", "deleted_at")
