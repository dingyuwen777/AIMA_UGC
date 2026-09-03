"""Stage 8D Analysis Result 历史与有序标签表。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
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

analysis_content_runs_table = Table(
    "analysis_content_runs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("sequence_no", BigInteger(), Identity(), nullable=False),
    Column("client_idempotency_key", Text(), nullable=False),
    Column("planner_job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("run_intent", Text(), nullable=False),
    Column("scope", Text(), nullable=False),
    Column("filter_snapshot", JSONB(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("target_count", Integer(), nullable=False),
    Column("shard_count", Integer(), nullable=False),
    Column("shard_size", Integer(), nullable=False),
    Column("prompt_version", Text(), nullable=False),
    Column("analysis_scheme_version_id", Uuid(), ForeignKey("analysis_scheme_versions.id")),
    Column("prompt_text_snapshot", Text()),
    Column("prompt_sha256", Text(), nullable=False),
    Column("taxonomy_sha256", Text(), nullable=False),
    Column("model_provider", Text(), nullable=False),
    Column("model", Text(), nullable=False),
    Column("generation_config", JSONB(), nullable=False),
    Column("generation_config_hash", Text(), nullable=False),
    Column("runtime_config_snapshot", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("error_code", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("cancel_requested_at", DateTime(timezone=True)),
    CheckConstraint(
        "run_intent in ('initial_analysis','manual_reanalysis')",
        name="run_intent_allowed",
    ),
    CheckConstraint("scope in ('query','selected')", name="scope_allowed"),
    CheckConstraint(
        "status in ('queued','running','succeeded','partial_failed','failed',"
        "'cancelling','cancelled')",
        name="status_allowed",
    ),
    CheckConstraint("target_count > 0", name="target_count_positive"),
    CheckConstraint("shard_count > 0", name="shard_count_positive"),
    CheckConstraint("shard_size > 0", name="shard_size_positive"),
    CheckConstraint("jsonb_typeof(filter_snapshot) = 'object'", name="filter_snapshot_object"),
    CheckConstraint("jsonb_typeof(generation_config) = 'object'", name="generation_config_object"),
    CheckConstraint(
        "jsonb_typeof(runtime_config_snapshot) = 'object'",
        name="runtime_config_snapshot_object",
    ),
    CheckConstraint("char_length(prompt_sha256) = 64", name="prompt_sha256_length"),
    CheckConstraint("char_length(taxonomy_sha256) = 64", name="taxonomy_sha256_length"),
    CheckConstraint(
        "char_length(generation_config_hash) = 64",
        name="generation_config_hash_length",
    ),
    UniqueConstraint("sequence_no", name="uq_analysis_content_runs_sequence_no"),
    UniqueConstraint(
        "client_idempotency_key",
        name="uq_analysis_content_runs_client_idempotency_key",
    ),
    UniqueConstraint("planner_job_id", name="uq_analysis_content_runs_planner_job_id"),
    info={"owner": "analysis"},
)

analysis_content_run_targets_table = Table(
    "analysis_content_run_targets",
    metadata,
    Column(
        "run_id",
        Uuid(),
        ForeignKey("analysis_content_runs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("target_ordinal", BigInteger(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    UniqueConstraint("run_id", "content_id", name="uq_analysis_content_run_targets_content"),
    CheckConstraint("target_ordinal >= 0", name="target_ordinal_nonnegative"),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    info={"owner": "analysis"},
)

Index(
    "ix_analysis_content_run_targets_run_ordinal",
    analysis_content_run_targets_table.c.run_id,
    analysis_content_run_targets_table.c.target_ordinal,
)

analysis_content_results_table = Table(
    "analysis_content_results",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("analysis_run_id", Uuid(), ForeignKey("analysis_content_runs.id"), nullable=False),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("schema_version", Text(), nullable=False),
    Column("relevance", Text(), nullable=False),
    Column("voice_type", Text(), nullable=False),
    Column("sentiment", Text()),
    Column("prompt_version", Text(), nullable=False),
    Column("prompt_sha256", Text(), nullable=False),
    Column("taxonomy_sha256", Text(), nullable=False),
    Column("model_provider", Text(), nullable=False),
    Column("model", Text(), nullable=False),
    Column("input_hash", Text(), nullable=False),
    Column("generation_config_hash", Text(), nullable=False),
    Column("analyzed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "analysis_run_id", "content_id", "content_version", name="uq_analysis_content_results_identity"
    ),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("relevance in ('relevant','irrelevant')", name="relevance_allowed"),
    CheckConstraint("char_length(voice_type) > 0", name="voice_type_nonempty"),
    CheckConstraint(
        "(relevance = 'relevant' and sentiment is not null) or "
        "(relevance = 'irrelevant' and sentiment is null)",
        name="relevance_sentiment_consistent",
    ),
    CheckConstraint("char_length(input_hash) = 64", name="input_hash_sha256_length"),
    CheckConstraint("char_length(prompt_sha256) = 64", name="prompt_sha256_length"),
    CheckConstraint("char_length(taxonomy_sha256) = 64", name="taxonomy_sha256_length"),
    CheckConstraint("char_length(generation_config_hash) = 64", name="generation_config_hash_length"),
    info={"owner": "analysis"},
)

analysis_content_requests_table = Table(
    "analysis_content_requests",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("run_id", Uuid(), ForeignKey("analysis_content_runs.id", ondelete="CASCADE"), nullable=False),
    Column("shard_no", Integer(), nullable=False),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("scope", Text(), nullable=False),
    Column("filter_snapshot", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("target_count", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", name="uq_analysis_content_requests_job_id"),
    UniqueConstraint("run_id", "shard_no", name="uq_analysis_content_requests_run_shard"),
    CheckConstraint("scope in ('query','selected')", name="scope_allowed"),
    CheckConstraint("target_count > 0", name="target_count_positive"),
    CheckConstraint("shard_no >= 0", name="shard_no_nonnegative"),
    CheckConstraint("jsonb_typeof(filter_snapshot) = 'object'", name="filter_snapshot_object"),
    info={"owner": "analysis"},
)

analysis_content_request_items_table = Table(
    "analysis_content_request_items",
    metadata,
    Column("request_id", Uuid(), ForeignKey("analysis_content_requests.id", ondelete="CASCADE"), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("content_version", Integer(), nullable=False),
    Column("ordinal", Integer(), nullable=False),
    Column("analysis_result_id", Uuid(), ForeignKey("analysis_content_results.id")),
    Column("status", Text(), nullable=False, server_default=text("'pending'")),
    Column("error_code", Text()),
    UniqueConstraint("request_id", "ordinal", name="uq_analysis_content_request_items_ordinal"),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    CheckConstraint(
        "status in ('pending','succeeded','failed','stale','cancelled')",
        name="status_allowed",
    ),
    CheckConstraint(
        "(status = 'pending' and analysis_result_id is null and error_code is null) or "
        "(status = 'succeeded' and analysis_result_id is not null and error_code is null) or "
        "(status in ('failed','stale','cancelled') and analysis_result_id is null and error_code is not null)",
        name="status_fields_consistent",
    ),
    info={"owner": "analysis"},
)

analysis_content_label_pairs_table = Table(
    "analysis_content_label_pairs",
    metadata,
    Column("analysis_result_id", Uuid(), ForeignKey("analysis_content_results.id", ondelete="CASCADE"), primary_key=True),
    Column("ordinal", Integer(), primary_key=True),
    Column("primary_label", Text(), nullable=False),
    Column("secondary_label", Text(), nullable=False),
    CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    CheckConstraint("char_length(primary_label) > 0", name="primary_label_nonempty"),
    CheckConstraint("char_length(secondary_label) > 0", name="secondary_label_nonempty"),
    UniqueConstraint(
        "analysis_result_id", "primary_label", "secondary_label", name="uq_analysis_content_label_pairs_value"
    ),
    info={"owner": "analysis"},
)

__all__ = [
    "analysis_content_label_pairs_table",
    "analysis_content_request_items_table",
    "analysis_content_requests_table",
    "analysis_content_results_table",
    "analysis_content_run_targets_table",
    "analysis_content_runs_table",
]
