"""Persistent Canonical Replay 的最小 PostgreSQL Schema。"""

from sqlalchemy import (
    BigInteger,
    Boolean,
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

canonical_replay_all_requests_table = Table(
    "canonical_replay_all_requests",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("client_idempotency_key", Text(), nullable=False, unique=True),
    Column("selection_digest", Text(), nullable=False),
    Column("artifact_count", Integer(), nullable=False),
    Column("run_count", Integer(), nullable=False),
    Column("artifacts_per_run", Integer(), nullable=False),
    Column("batch_size", Integer(), nullable=False),
    Column("created_by", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("reversible", Boolean(), nullable=False, server_default=text("false")),
    Column("lifecycle_status", Text(), nullable=False, server_default=text("'active'")),
    Column("reversal_job_id", Uuid(), ForeignKey("jobs.id"), unique=True),
    Column("cancellation_requested_at", DateTime(timezone=True)),
    Column("reversal_requested_at", DateTime(timezone=True)),
    Column("reversed_at", DateTime(timezone=True)),
    Column("reversal_requested_by", Text()),
    Column("reversal_request_id", Text()),
    Column("reverted_content_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("hidden_content_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("retained_content_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("skipped_content_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("restored_evidence_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("skipped_evidence_count", BigInteger(), nullable=False, server_default=text("0")),
    CheckConstraint(
        "char_length(client_idempotency_key) between 1 and 120",
        name="idempotency_key_length",
    ),
    CheckConstraint("char_length(selection_digest) = 64", name="selection_digest_length"),
    CheckConstraint("artifact_count >= 0", name="artifact_count_nonnegative"),
    CheckConstraint("run_count >= 0", name="run_count_nonnegative"),
    CheckConstraint("artifacts_per_run = 100", name="artifacts_per_run_fixed"),
    CheckConstraint("batch_size = 1000", name="batch_size_fixed"),
    CheckConstraint("char_length(created_by) between 1 and 200", name="created_by_length"),
    CheckConstraint(
        "lifecycle_status in ('active','cancelling','reverting','reverted','revert_failed')",
        name="lifecycle_status_allowed",
    ),
    CheckConstraint(
        "reverted_content_count >= 0 and hidden_content_count >= 0 "
        "and retained_content_count >= 0 and skipped_content_count >= 0 "
        "and restored_evidence_count >= 0 and skipped_evidence_count >= 0",
        name="reversal_counts_nonnegative",
    ),
    CheckConstraint(
        "reversal_requested_by is null or char_length(reversal_requested_by) between 1 and 200",
        name="reversal_requested_by_length",
    ),
    info={"owner": "ingestion"},
)

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
    Column(
        "all_request_id",
        Uuid(),
        ForeignKey("canonical_replay_all_requests.id"),
    ),
    Column("all_request_ordinal", Integer()),
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
    CheckConstraint(
        "(all_request_id is null and all_request_ordinal is null) or "
        "(all_request_id is not null and all_request_ordinal >= 0)",
        name="all_request_fields_consistent",
    ),
    UniqueConstraint(
        "all_request_id",
        "all_request_ordinal",
        name="uq_canonical_replay_runs_all_request_ordinal",
    ),
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

canonical_replay_validation_proofs_table = Table(
    "canonical_replay_validation_proofs",
    metadata,
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id", ondelete="CASCADE"), primary_key=True),
    Column("sha256", Text(), nullable=False),
    Column("byte_size", BigInteger(), nullable=False),
    Column("validation_version", Text(), nullable=False),
    Column("source_kind", Text(), nullable=False),
    Column("source_expectations", JSONB(), nullable=False),
    Column("validated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(sha256) = 64", name="sha256_length"),
    CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
    CheckConstraint(
        "jsonb_typeof(source_expectations) = 'array'", name="source_expectations_array"
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

canonical_replay_content_changes_table = Table(
    "canonical_replay_content_changes",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "all_request_id",
        Uuid(),
        ForeignKey("canonical_replay_all_requests.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "run_id",
        Uuid(),
        ForeignKey("canonical_replay_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column(
        "provider_attempt_id",
        Uuid(),
        ForeignKey("provider_request_attempts.id"),
        nullable=False,
    ),
    Column("raw_artifact_id", Uuid(), ForeignKey("artifacts.id"), nullable=False),
    Column("version_before", Integer()),
    Column("version_after", Integer(), nullable=False),
    Column("delta", JSONB(), nullable=False),
    Column("visibility_owner_before", Uuid(), ForeignKey("canonical_replay_all_requests.id")),
    Column("vehicle_evidence_before", JSONB(), nullable=False),
    Column("vehicle_evidence_after", JSONB(), nullable=False),
    Column("brand_evidence_before", JSONB(), nullable=False),
    Column("brand_evidence_after", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("reverted_at", DateTime(timezone=True)),
    Column("reversal_version_no", Integer()),
    UniqueConstraint(
        "run_id",
        "content_id",
        name="uq_canonical_replay_content_changes_run_content",
    ),
    CheckConstraint(
        "version_before is null or version_before >= 1",
        name="version_before_positive",
    ),
    CheckConstraint("version_after >= 1", name="version_after_positive"),
    CheckConstraint("jsonb_typeof(delta) = 'object'", name="delta_object"),
    CheckConstraint("jsonb_typeof(vehicle_evidence_before) = 'array'", name="vehicle_before_array"),
    CheckConstraint("jsonb_typeof(vehicle_evidence_after) = 'array'", name="vehicle_after_array"),
    CheckConstraint("jsonb_typeof(brand_evidence_before) = 'array'", name="brand_before_array"),
    CheckConstraint("jsonb_typeof(brand_evidence_after) = 'array'", name="brand_after_array"),
    CheckConstraint(
        "(reverted_at is null and reversal_version_no is null) or "
        "(reverted_at is not null and reversal_version_no >= 1)",
        name="reversal_fields_consistent",
    ),
    info={"owner": "ingestion"},
)

Index(
    "ix_canonical_replay_runs_created_at",
    canonical_replay_runs_table.c.created_at,
    canonical_replay_runs_table.c.id,
)
Index(
    "ix_canonical_replay_all_requests_created_at",
    canonical_replay_all_requests_table.c.created_at,
    canonical_replay_all_requests_table.c.id,
)
Index(
    "ix_canonical_replay_run_artifacts_artifact_id",
    canonical_replay_run_artifacts_table.c.artifact_id,
)
Index(
    "ix_canonical_replay_content_changes_request_created",
    canonical_replay_content_changes_table.c.all_request_id,
    canonical_replay_content_changes_table.c.created_at,
    canonical_replay_content_changes_table.c.id,
)
Index(
    "ix_canonical_replay_content_changes_reverted_visibility",
    canonical_replay_content_changes_table.c.all_request_id,
    canonical_replay_content_changes_table.c.content_id,
    postgresql_where=canonical_replay_content_changes_table.c.reverted_at.is_not(None),
)

__all__ = [
    "canonical_replay_all_requests_table",
    "canonical_replay_content_changes_table",
    "canonical_replay_run_artifacts_table",
    "canonical_replay_runs_table",
    "canonical_replay_seen_content_table",
    "canonical_replay_validation_proofs_table",
]
