"""工作台用户布局事实表。"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata


workbench_layouts_table = Table(
    "workbench_layouts",
    metadata,
    Column(
        "principal_id",
        Text(),
        ForeignKey("identity_principals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("schema_version", Integer(), nullable=False, server_default="1"),
    Column("revision", Integer(), nullable=False),
    Column("layout", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("schema_version = 1", name="schema_version_v1"),
    CheckConstraint("revision >= 1", name="revision_positive"),
    CheckConstraint("jsonb_typeof(layout) = 'array'", name="layout_array"),
    info={"owner": "workbench"},
)


__all__ = ["workbench_layouts_table"]
