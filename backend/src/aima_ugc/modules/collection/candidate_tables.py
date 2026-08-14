"""Stage 6 Collection Candidate/Ingestion 追加账本表。"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Table, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

collection_candidates_table = Table(
    "collection_candidates",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "provider_request_attempt_id",
        Uuid(),
        ForeignKey("provider_request_attempts.id"),
        nullable=False,
    ),
    Column("item_kind", Text(), nullable=False),
    Column("external_item_id", Text()),
    Column("item_locator", Text(), nullable=False),
    Column("discovered_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("provider_request_attempt_id", "item_locator"),
    CheckConstraint("item_kind in ('content','comment')", name="item_kind_allowed"),
    CheckConstraint("char_length(item_locator) > 0", name="item_locator_nonempty"),
    info={"owner": "collection"},
)

collection_candidate_ingestions_table = Table(
    "collection_candidate_ingestions",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("candidate_id", Uuid(), ForeignKey("collection_candidates.id"), nullable=False),
    Column("ingestion_no", Integer(), nullable=False),
    Column("canonical_version", Text()),
    Column("canonical_identity", Text()),
    Column("observed_fields", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    Column("target_type", Text()),
    Column("content_id", Uuid(), ForeignKey("contents.id")),
    Column("comment_id", Uuid(), ForeignKey("comments.id")),
    Column("result", Text(), nullable=False),
    Column("error_code", Text()),
    Column("error_detail", Text()),
    Column("processed_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("candidate_id", "ingestion_no"),
    CheckConstraint("ingestion_no >= 1", name="ingestion_no_positive"),
    CheckConstraint(
        "result in ('ingested','duplicate','invalid','unsupported','failed')",
        name="result_allowed",
    ),
    CheckConstraint(
        "(target_type = 'content' and content_id is not null and comment_id is null) or "
        "(target_type = 'comment' and comment_id is not null and content_id is null) or "
        "(target_type is null and content_id is null and comment_id is null)",
        name="target_consistent",
    ),
    CheckConstraint("jsonb_typeof(observed_fields) = 'array'", name="observed_fields_array"),
    info={"owner": "collection"},
)
