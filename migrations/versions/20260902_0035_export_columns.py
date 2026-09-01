"""让数据导出冻结后端白名单列目录版本。

Revision ID: 20260902_0035
Revises: 20260902_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0035"
down_revision: str | Sequence[str] | None = "20260902_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reporting_data_exports",
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "reporting_data_exports", sa.Column("column_catalog_version", sa.Integer(), nullable=True)
    )
    op.execute(
        "UPDATE reporting_data_exports SET columns = '[]'::jsonb, column_catalog_version = 1"
    )
    op.alter_column("reporting_data_exports", "columns", nullable=False)
    op.alter_column("reporting_data_exports", "column_catalog_version", nullable=False)
    op.create_check_constraint(
        op.f("ck_reporting_data_exports_columns_array"),
        "reporting_data_exports",
        "jsonb_typeof(columns) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_reporting_data_exports_column_catalog_version_positive"),
        "reporting_data_exports",
        "column_catalog_version > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_reporting_data_exports_column_catalog_version_positive"),
        "reporting_data_exports",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_reporting_data_exports_columns_array"),
        "reporting_data_exports",
        type_="check",
    )
    op.drop_column("reporting_data_exports", "column_catalog_version")
    op.drop_column("reporting_data_exports", "columns")
