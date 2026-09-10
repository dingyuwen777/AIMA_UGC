"""Persistent Canonical Replay 的最小 PostgreSQL Schema。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from aima_ugc.platform.database.metadata import metadata

canonical_replay_runs_table = Table(
    "canonical_replay_runs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False, unique=True),
    Column("client_idempotency_key", Text(), nullable=False, unique=True),
    Column("filter_snapshot", JSONB(), nullable=False),
    Column("requested_brand_ids", ARRAY(Uuid()), nullable=False),
    Column("artifact_count", Integer(), nullable=False),
    Column("checkpoint_artifact_ordinal", Integer(), nullable=False, server_default=text("0")),
    Column("checkpoint_row_number", BigInteger(), nullable=False, server_default=text("0")),
    Column("batch_size", Integer(), nullable=False),
    Column("rows_seen", BigInteger(), nullable=False, server_default=text("0")),
    Column("rows_matched", BigInteger(), nullable=False, server_default=text("0")),
    Column("rows_filtered_out", BigInteger(), nullable=False, server_default=text("0")),
    Column("duplicates_removed", BigInteger(), nullable=False, server_default=text("0")),
    Column("rows_ingested", BigInteger(), nullable=False, server_default=text("0")),
    Column("existing_convergence", BigInteger(), nullable=False, server_default=text("0")),
    Column("created_by", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "char_length(client_idempotency_key) between 1 and 200", name="idempotency_key_length"
    ),
    CheckConstraint("char_length(created_by) between 1 and 200", name="created_by_length"),
    CheckConstraint("artifact_count between 1 and 100", name="artifact_count_range"),
    CheckConstraint("batch_size between 1 and 1000", name="batch_size_range"),
    CheckConstraint(
        "checkpoint_artifact_ordinal between 0 and artifact_count "
        "and checkpoint_row_number >= 0 "
        "and (checkpoint_artifact_ordinal < artifact_count or checkpoint_row_number = 0)",
        name="checkpoint_nonnegative",
    ),
    CheckConstraint(
        "rows_seen >= 0 and rows_matched >= 0 and rows_filtered_out >= 0 "
        "and duplicates_removed >= 0 and rows_ingested >= 0 "
        "and existing_convergence >= 0",
        name="counters_nonnegative",
    ),
    CheckConstraint("rows_seen = rows_matched + rows_filtered_out", name="seen_reconciled"),
    CheckConstraint(
        "rows_matched = duplicates_removed + rows_ingested + existing_convergence",
        name="matched_reconciled",
    ),
    CheckConstraint("jsonb_typeof(filter_snapshot) = 'object'", name="filter_snapshot_object"),
    info={"owner": "ingestion"},
)

canonical_replay_run_artifacts_table = Table(
    "canonical_replay_run_artifacts",
    metadata,
    Column(
        "run_id",
        Uuid(),
        ForeignKey("canonical_replay_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("ordinal", Integer(), nullable=False),
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id"), nullable=False),
    Column("source_kind", Text(), nullable=False),
    PrimaryKeyConstraint("run_id", "ordinal"),
    UniqueConstraint("run_id", "artifact_id", name="uq_canonical_replay_run_artifacts_input"),
    CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    CheckConstraint(
        "source_kind in ('excel_import_v2','data_import_canonical_chunk_v2',"
        "'tikhub_search_attempt_v1')",
        name="source_kind_allowed",
    ),
    info={"owner": "ingestion"},
)

canonical_replay_seen_content_table = Table(
    "canonical_replay_seen_content",
    metadata,
    Column(
        "run_id",
        Uuid(),
        ForeignKey("canonical_replay_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("platform", Text(), nullable=False),
    Column("external_content_id", Text(), nullable=False),
    PrimaryKeyConstraint("run_id", "platform", "external_content_id"),
    CheckConstraint("char_length(platform) > 0", name="platform_nonempty"),
    CheckConstraint("char_length(external_content_id) > 0", name="external_content_id_nonempty"),
    info={"owner": "ingestion"},
)

Index(
    "ix_canonical_replay_runs_created_at",
    canonical_replay_runs_table.c.created_at,
    canonical_replay_runs_table.c.id,
)
Index(
    "ix_canonical_replay_run_artifacts_artifact_id",
    canonical_replay_run_artifacts_table.c.artifact_id,
)

__all__ = [
    "canonical_replay_run_artifacts_table",
    "canonical_replay_runs_table",
    "canonical_replay_seen_content_table",
]
