"""持久化导出创建者与个人默认字段，不扫描 Content 或修改历史文件。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261010_0087"
down_revision: str | Sequence[str] | None = "20261009_0086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """只回填可靠字符串；未知所有者保持 NULL，普通用户不可继承。"""
    op.add_column("reporting_data_exports", sa.Column("created_by", sa.Text(), nullable=True))
    op.execute("""
        UPDATE reporting_data_exports
        SET created_by = request_snapshot->>'requested_by'
        WHERE jsonb_typeof(request_snapshot->'requested_by') = 'string'
          AND length(btrim(request_snapshot->>'requested_by')) > 0
          AND request_snapshot->>'requested_by' = btrim(request_snapshot->>'requested_by')
    """)
    op.create_index(
        "ix_reporting_data_exports_owner_recent",
        "reporting_data_exports",
        ["created_by", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_table(
        "reporting_user_export_column_defaults",
        sa.Column("principal_id", sa.Text(), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("selected_columns", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("saved_catalog_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(btrim(principal_id)) > 0", name="principal_nonempty"),
        sa.CheckConstraint("schema_version = 1", name="schema_version_supported"),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("saved_catalog_version > 0", name="catalog_version_positive"),
        sa.CheckConstraint(
            "selected_columns IS NULL OR (jsonb_typeof(selected_columns) = 'array' "
            "AND jsonb_array_length(selected_columns) > 0)",
            name="selected_columns_nonempty_array",
        ),
    )


def downgrade() -> None:
    """只允许隔离空库往返；已有用户配置或导出时拒绝丢失业务归属。"""
    populated = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM reporting_user_export_column_defaults) "
                "OR EXISTS (SELECT 1 FROM reporting_data_exports)"
            )
        )
        .scalar_one()
    )
    if populated:
        raise RuntimeError("不能安全 downgrade：应用回滚须保留导出归属和个人配置 Schema")
    op.drop_table("reporting_user_export_column_defaults")
    op.drop_index("ix_reporting_data_exports_owner_recent", table_name="reporting_data_exports")
    op.drop_column("reporting_data_exports", "created_by")
