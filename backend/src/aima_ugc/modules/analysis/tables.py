"""Stage 8D Analysis Result 历史与有序标签表。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

analysis_content_results_table = Table(
    "analysis_content_results",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("schema_version", Text(), nullable=False),
    Column("sentiment", Text(), nullable=False),
    Column("prompt_version", Text(), nullable=False),
    Column("prompt_sha256", Text(), nullable=False),
    Column("taxonomy_sha256", Text(), nullable=False),
    Column("model_provider", Text(), nullable=False),
    Column("model", Text(), nullable=False),
    Column("input_hash", Text(), nullable=False),
    Column("analyzed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "content_id",
        "content_version",
        "input_hash",
        "prompt_sha256",
        "taxonomy_sha256",
        "model_provider",
        "model",
        name="uq_analysis_content_results_identity",
    ),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("char_length(input_hash) = 64", name="input_hash_sha256_length"),
    CheckConstraint("char_length(prompt_sha256) = 64", name="prompt_sha256_length"),
    CheckConstraint("char_length(taxonomy_sha256) = 64", name="taxonomy_sha256_length"),
    info={"owner": "analysis"},
)


analysis_content_requests_table = Table(
    "analysis_content_requests",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("scope", Text(), nullable=False),
    Column("filter_snapshot", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("target_count", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", name="uq_analysis_content_requests_job_id"),
    CheckConstraint("scope in ('query','selected')", name="scope_allowed"),
    CheckConstraint("target_count > 0", name="target_count_positive"),
    CheckConstraint("jsonb_typeof(filter_snapshot) = 'object'", name="filter_snapshot_object"),
    info={"owner": "analysis"},
)


analysis_content_request_items_table = Table(
    "analysis_content_request_items",
    metadata,
    Column(
        "request_id",
        Uuid(),
        ForeignKey("analysis_content_requests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
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
        "status in ('pending','succeeded','failed','stale')",
        name="status_allowed",
    ),
    CheckConstraint(
        "(status = 'pending' and analysis_result_id is null and error_code is null) or "
        "(status = 'succeeded' and analysis_result_id is not null and error_code is null) or "
        "(status in ('failed','stale') and analysis_result_id is null and error_code is not null)",
        name="status_fields_consistent",
    ),
    info={"owner": "analysis"},
)


analysis_content_label_pairs_table = Table(
    "analysis_content_label_pairs",
    metadata,
    Column(
        "analysis_result_id",
        Uuid(),
        ForeignKey("analysis_content_results.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer(), primary_key=True),
    Column("primary_label", Text(), nullable=False),
    Column("secondary_label", Text(), nullable=False),
    CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
    CheckConstraint("char_length(primary_label) > 0", name="primary_label_nonempty"),
    CheckConstraint("char_length(secondary_label) > 0", name="secondary_label_nonempty"),
    UniqueConstraint(
        "analysis_result_id",
        "primary_label",
        "secondary_label",
        name="uq_analysis_content_label_pairs_value",
    ),
    info={"owner": "analysis"},
)


__all__ = [
    "analysis_content_label_pairs_table",
    "analysis_content_request_items_table",
    "analysis_content_requests_table",
    "analysis_content_results_table",
]
