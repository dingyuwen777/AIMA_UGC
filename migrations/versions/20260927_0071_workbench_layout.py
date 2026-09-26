"""新增用户工作台布局，并为 active Scheme 聚合增加 Run 索引。

Revision ID: 20260927_0071
Revises: 20260926_0070
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260927_0071"
down_revision: str | Sequence[str] | None = "20260926_0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workbench_layouts",
        sa.Column(
            "principal_id",
            sa.Text(),
            sa.ForeignKey("identity_principals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "schema_version = 1",
            name=op.f("ck_workbench_layouts_schema_version_v1"),
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name=op.f("ck_workbench_layouts_revision_positive"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(layout) = 'array'",
            name=op.f("ck_workbench_layouts_layout_array"),
        ),
    )
    op.create_index(
        "ix_analysis_runs_scheme_sequence",
        "analysis_content_runs",
        ["analysis_scheme_version_id", "sequence_no", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_scheme_sequence", table_name="analysis_content_runs")
    op.drop_table("workbench_layouts")
