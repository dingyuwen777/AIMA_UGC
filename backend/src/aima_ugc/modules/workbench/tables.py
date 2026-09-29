"""工作台用户布局与可重建聚合派生表。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Sequence,
    Table,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

workbench_layouts_table = Table(
    "workbench_layouts",
    metadata,
    Column("principal_id", Text(), primary_key=True),
    Column("schema_version", Integer(), nullable=False, server_default="1"),
    Column("revision", Integer(), nullable=False),
    Column("layout", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("schema_version = 1", name="schema_version_v1"),
    CheckConstraint("revision >= 1", name="revision_positive"),
    CheckConstraint("char_length(principal_id) > 0", name="principal_id_nonempty"),
    CheckConstraint("jsonb_typeof(layout) = 'array'", name="layout_array"),
    info={"owner": "dashboard"},
)


workbench_data_revision_sequence = Sequence("workbench_data_revision_seq", metadata=metadata)


workbench_snapshots_table = Table(
    "workbench_snapshots",
    metadata,
    Column("module", Text(), primary_key=True),
    Column("query_hash", Text(), primary_key=True),
    Column("query", JSONB(), nullable=False),
    Column(
        "analysis_scheme_version_id",
        Uuid(),
        ForeignKey("analysis_scheme_versions.id", ondelete="CASCADE"),
    ),
    Column(
        "target_analysis_scheme_version_id",
        Uuid(),
        ForeignKey("analysis_scheme_versions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("taxonomy_sha256", Text()),
    Column("source_revision", BigInteger()),
    Column("target_revision", BigInteger(), nullable=False),
    Column("refresh_generation", BigInteger(), nullable=False, server_default=text("1")),
    Column("status", Text(), nullable=False),
    Column("response", JSONB()),
    Column("computed_at", DateTime(timezone=True)),
    Column("last_error_code", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("module in ('mind','trend')", name="module_allowed"),
    CheckConstraint("char_length(query_hash) = 64", name="query_hash_length"),
    CheckConstraint("jsonb_typeof(query) = 'object'", name="query_object"),
    CheckConstraint(
        "taxonomy_sha256 is null or char_length(taxonomy_sha256) = 64", name="taxonomy_hash_length"
    ),
    CheckConstraint(
        "source_revision is null or source_revision > 0", name="source_revision_positive"
    ),
    CheckConstraint("target_revision > 0", name="target_revision_positive"),
    CheckConstraint("refresh_generation > 0", name="refresh_generation_positive"),
    CheckConstraint("status in ('refreshing','ready','failed')", name="status_allowed"),
    CheckConstraint(
        "response is null or jsonb_typeof(response) = 'object'", name="response_object"
    ),
    CheckConstraint(
        "(response is null) = (computed_at is null)", name="response_computed_consistent"
    ),
    info={"owner": "dashboard", "derived": True},
)


__all__ = [
    "workbench_data_revision_sequence",
    "workbench_layouts_table",
    "workbench_snapshots_table",
]
