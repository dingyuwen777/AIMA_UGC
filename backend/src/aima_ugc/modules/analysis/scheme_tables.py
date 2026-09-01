"""Analysis Scheme 与原子版本表。"""

from sqlalchemy import (
    Boolean,
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

analysis_schemes_table = Table(
    "analysis_schemes",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("name", Text(), nullable=False),
    Column("active_version_id", Uuid(), ForeignKey("analysis_scheme_versions.id", use_alter=True)),
    Column("is_active", Boolean(), nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("name"),
    CheckConstraint("char_length(name) > 0", name="name_nonempty"),
    info={"owner": "analysis"},
)

Index(
    "uq_analysis_schemes_single_active",
    analysis_schemes_table.c.is_active,
    unique=True,
    postgresql_where=analysis_schemes_table.c.is_active.is_(True),
)

analysis_scheme_versions_table = Table(
    "analysis_scheme_versions",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("scheme_id", Uuid(), ForeignKey("analysis_schemes.id"), nullable=False),
    Column("version", Integer(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("description", Text(), nullable=False),
    Column("definition", JSONB(), nullable=False),
    Column("compiled_prompt", Text(), nullable=False),
    Column("prompt_sha256", Text(), nullable=False),
    Column("taxonomy_sha256", Text(), nullable=False),
    Column("created_by", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("published_at", DateTime(timezone=True)),
    UniqueConstraint("scheme_id", "version"),
    CheckConstraint("version > 0", name="version_positive"),
    CheckConstraint("status in ('draft','published','retired')", name="status_allowed"),
    CheckConstraint("jsonb_typeof(definition) = 'object'", name="definition_object"),
    CheckConstraint("char_length(compiled_prompt) > 0", name="compiled_prompt_nonempty"),
    CheckConstraint("char_length(created_by) > 0", name="created_by_nonempty"),
    info={"owner": "analysis"},
)

__all__ = ["analysis_scheme_versions_table", "analysis_schemes_table"]
