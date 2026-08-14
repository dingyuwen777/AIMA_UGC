"""Collection 模块拥有的 Run/Scope 父事实表。"""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

collection_runs_table = Table(
    "collection_runs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("trigger_type", Text(), nullable=False),
    Column("config_snapshot", JSONB(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("requested_count", Integer(), nullable=False, server_default=text("0")),
    Column("succeeded_count", Integer(), nullable=False, server_default=text("0")),
    Column("failed_count", Integer(), nullable=False, server_default=text("0")),
    Column("content_count", Integer(), nullable=False, server_default=text("0")),
    Column("comment_count", Integer(), nullable=False, server_default=text("0")),
    Column("error_summary", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id"),
    CheckConstraint(
        "trigger_type in ('manual','api','backfill')",
        name="trigger_type_allowed",
    ),
    CheckConstraint(
        "status in ('queued','running','partial_success','succeeded','failed','cancelled')",
        name="status_allowed",
    ),
    CheckConstraint(
        "requested_count >= 0 and succeeded_count >= 0 and failed_count >= 0 "
        "and content_count >= 0 and comment_count >= 0",
        name="counts_nonnegative",
    ),
    info={"owner": "collection"},
)

collection_scopes_table = Table(
    "collection_scopes",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("run_id", Uuid(), ForeignKey("collection_runs.id"), nullable=False),
    Column("platform", Text(), nullable=False),
    Column("source_type", Text(), nullable=False),
    Column("source_value", Text(), nullable=False),
    Column("operation_group", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column(
        "pagination_state",
        JSONB(),
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    Column("progress", Integer(), nullable=False, server_default=text("0")),
    Column("stop_reason", Text()),
    Column("stats", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    UniqueConstraint("run_id", "platform", "source_type", "source_value", "operation_group"),
    info={"owner": "collection"},
)

Index(
    "ix_collection_runs_status_created_at",
    collection_runs_table.c.status,
    collection_runs_table.c.created_at.desc(),
)
Index(
    "ix_collection_scopes_run_id_status",
    collection_scopes_table.c.run_id,
    collection_scopes_table.c.status,
)
