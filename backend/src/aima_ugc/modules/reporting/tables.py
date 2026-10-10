"""Stage 8D durable Excel Export 业务关联表。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

reporting_data_exports_table = Table(
    "reporting_data_exports",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id")),
    Column("format", Text(), nullable=False),
    Column("request_snapshot", JSONB(), nullable=False),
    Column("columns", JSONB(), nullable=False),
    Column("column_catalog_version", Integer(), nullable=False),
    Column("created_by", Text(), nullable=True),
    Column("stats", JSONB()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    UniqueConstraint("job_id", name="uq_reporting_data_exports_job_id"),
    UniqueConstraint("artifact_id", name="uq_reporting_data_exports_artifact_id"),
    CheckConstraint("format = 'xlsx'", name="format_xlsx"),
    CheckConstraint(
        "jsonb_typeof(request_snapshot) = 'object'",
        name="request_snapshot_object",
    ),
    CheckConstraint("jsonb_typeof(columns) = 'array'", name="columns_array"),
    CheckConstraint("column_catalog_version > 0", name="column_catalog_version_positive"),
    CheckConstraint("stats is null or jsonb_typeof(stats) = 'object'", name="stats_object"),
    CheckConstraint(
        "(artifact_id is null and stats is null and completed_at is null) or "
        "(artifact_id is not null and stats is not null and completed_at is not null)",
        name="completion_fields_consistent",
    ),
    info={"owner": "reporting"},
)


Index(
    "ix_reporting_data_exports_owner_recent",
    reporting_data_exports_table.c.created_by,
    reporting_data_exports_table.c.created_at.desc(),
    reporting_data_exports_table.c.id.desc(),
)

reporting_user_export_column_defaults_table = Table(
    "reporting_user_export_column_defaults",
    metadata,
    Column("principal_id", Text(), primary_key=True),
    Column("schema_version", Integer(), nullable=False),
    Column("revision", Integer(), nullable=False),
    Column("selected_columns", JSONB(none_as_null=True), nullable=True),
    Column("saved_catalog_version", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("length(btrim(principal_id)) > 0", name="principal_nonempty"),
    CheckConstraint("schema_version = 1", name="schema_supported"),
    CheckConstraint("revision > 0", name="revision_positive"),
    CheckConstraint("saved_catalog_version > 0", name="catalog_positive"),
    CheckConstraint(
        "selected_columns IS NULL OR (jsonb_typeof(selected_columns) = 'array' "
        "AND jsonb_array_length(selected_columns) > 0)",
        name="columns_nonempty",
    ),
    info={"owner": "reporting"},
)

reporting_data_export_items_table = Table(
    "reporting_data_export_items",
    metadata,
    Column(
        "export_id",
        Uuid(),
        ForeignKey("reporting_data_exports.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("content_version", Integer(), nullable=False),
    Column("ordinal", Integer(), nullable=False),
    UniqueConstraint("export_id", "ordinal", name="uq_reporting_data_export_items_ordinal"),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    info={"owner": "reporting"},
)


__all__ = [
    "reporting_data_export_items_table",
    "reporting_data_exports_table",
    "reporting_user_export_column_defaults_table",
]
