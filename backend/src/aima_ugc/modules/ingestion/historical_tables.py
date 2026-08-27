"""Stage 12 历史迁移 Campaign、Manifest 与逐行对账 Schema。"""

from sqlalchemy import (
    BigInteger,
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

historical_import_campaigns_table = Table(
    "historical_import_campaigns",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("client_idempotency_key", Text(), nullable=False, unique=True),
    Column("source_kind", Text(), nullable=False, server_default=text("'server_path'")),
    Column(
        "ingestion_policy",
        Text(),
        nullable=False,
        server_default=text("'historical_fill_only'"),
    ),
    Column("declared_file_count", Integer(), nullable=False, server_default=text("0")),
    Column("root_relative_path", Text(), nullable=False),
    Column("recursive", Boolean(), nullable=False, server_default=text("false")),
    Column("profile_snapshot", JSONB(), nullable=False),
    Column("keyword_pack_snapshot", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("status", Text(), nullable=False),
    Column("discovered_file_count", Integer(), nullable=False, server_default=text("0")),
    Column("ready_item_count", Integer(), nullable=False, server_default=text("0")),
    Column("total_rows", BigInteger(), nullable=False, server_default=text("0")),
    Column("stats", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("error_summary", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    CheckConstraint(
        "status in ('uploading','discovering','snapshotting','ready','queued','running',"
        "'cancelling',"
        "'cancelled','succeeded','partial_failed','failed')",
        name="status_allowed",
    ),
    CheckConstraint(
        "source_kind in ('local_upload','server_path')",
        name="source_kind_allowed",
    ),
    CheckConstraint(
        "ingestion_policy in ('standard_observation','historical_fill_only')",
        name="ingestion_policy_allowed",
    ),
    CheckConstraint("declared_file_count >= 0", name="declared_file_count_nonnegative"),
    CheckConstraint("discovered_file_count >= 0", name="discovered_files_nonnegative"),
    CheckConstraint("ready_item_count >= 0", name="ready_item_count_nonnegative"),
    CheckConstraint("total_rows >= 0", name="total_rows_nonnegative"),
    CheckConstraint("jsonb_typeof(profile_snapshot) = 'object'", name="profile_snapshot_object"),
    CheckConstraint(
        "jsonb_typeof(keyword_pack_snapshot) = 'object'", name="keyword_pack_snapshot_object"
    ),
    CheckConstraint("jsonb_typeof(stats) = 'object'", name="stats_object"),
    info={"owner": "ingestion"},
)


historical_import_campaign_items_table = Table(
    "historical_import_campaign_items",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "campaign_id",
        Uuid(),
        ForeignKey("historical_import_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "parent_item_id",
        Uuid(),
        ForeignKey("historical_import_campaign_items.id", ondelete="CASCADE"),
    ),
    Column("item_kind", Text(), nullable=False),
    Column("relative_path", Text(), nullable=False),
    Column("manifest_identity", Text(), nullable=False),
    Column("ordinal", Integer()),
    Column("file_size", BigInteger()),
    Column("file_mtime_ns", BigInteger()),
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id")),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), unique=True),
    Column("sha256", Text()),
    Column("row_start", BigInteger()),
    Column("row_end", BigInteger()),
    Column("row_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("status", Text(), nullable=False),
    Column("attempt_count", Integer(), nullable=False, server_default=text("0")),
    Column("stats", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("error_code", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    UniqueConstraint(
        "campaign_id",
        "relative_path",
        "manifest_identity",
        "item_kind",
        "ordinal",
        name="uq_historical_import_campaign_items_manifest",
    ),
    CheckConstraint("item_kind in ('source_file','chunk')", name="item_kind_allowed"),
    CheckConstraint(
        "status in ('discovered','snapshotting','ready','queued','running','succeeded',"
        "'failed','cancelled')",
        name="status_allowed",
    ),
    CheckConstraint("char_length(manifest_identity) = 64", name="manifest_identity_sha256"),
    CheckConstraint("sha256 is null or char_length(sha256) = 64", name="sha256_length"),
    CheckConstraint("ordinal is null or ordinal >= 0", name="ordinal_nonnegative"),
    CheckConstraint("file_size is null or file_size >= 0", name="file_size_nonnegative"),
    CheckConstraint("row_count >= 0", name="row_count_nonnegative"),
    CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
    CheckConstraint("jsonb_typeof(stats) = 'object'", name="stats_object"),
    info={"owner": "ingestion"},
)


processing_import_batch_identities_table = Table(
    "processing_import_batch_identities",
    metadata,
    Column(
        "batch_id",
        Uuid(),
        ForeignKey("processing_import_batches.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("identity_hash", Text(), primary_key=True),
    Column("first_row_ordinal", BigInteger(), nullable=False),
    CheckConstraint("char_length(identity_hash) = 64", name="identity_hash_sha256"),
    CheckConstraint("first_row_ordinal >= 1", name="first_row_positive"),
    info={"owner": "ingestion"},
)


processing_import_batch_items_table = Table(
    "processing_import_batch_items",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "batch_id",
        Uuid(),
        ForeignKey("processing_import_batches.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "campaign_item_id",
        Uuid(),
        ForeignKey("historical_import_campaign_items.id"),
        nullable=False,
    ),
    Column("source_row_ordinal", BigInteger(), nullable=False),
    Column("platform", Text()),
    Column("external_content_id_hash", Text()),
    Column("content_id", Uuid(), ForeignKey("contents.id")),
    Column("outcome", Text(), nullable=False),
    Column("error_code", Text()),
    Column("filled_count", Integer(), nullable=False, server_default=text("0")),
    Column("conflict_count", Integer(), nullable=False, server_default=text("0")),
    Column("committed_chunk_ordinal", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "batch_id",
        "source_row_ordinal",
        name="uq_processing_import_batch_items_batch_row",
    ),
    CheckConstraint("source_row_ordinal >= 1", name="source_row_ordinal_positive"),
    CheckConstraint(
        "outcome in ('created','filled','updated','unchanged','conflict','filtered','duplicate',"
        "'invalid','failed')",
        name="outcome_allowed",
    ),
    CheckConstraint("filled_count >= 0", name="filled_count_nonnegative"),
    CheckConstraint("conflict_count >= 0", name="conflict_count_nonnegative"),
    CheckConstraint("committed_chunk_ordinal >= 0", name="chunk_ordinal_nonnegative"),
    CheckConstraint(
        "external_content_id_hash is null or char_length(external_content_id_hash) = 64",
        name="external_id_hash_sha256",
    ),
    info={"owner": "ingestion"},
)


processing_import_batch_item_conflicts_table = Table(
    "processing_import_batch_item_conflicts",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "batch_item_id",
        Uuid(),
        ForeignKey("processing_import_batch_items.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("field_name", Text(), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("current_value_hash", Text(), nullable=False),
    Column("historical_value_hash", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "batch_item_id",
        "field_name",
        name="uq_processing_import_batch_item_conflicts_field",
    ),
    CheckConstraint("content_version >= 1", name="version_positive"),
    CheckConstraint("char_length(current_value_hash) = 64", name="current_hash_sha256"),
    CheckConstraint("char_length(historical_value_hash) = 64", name="history_hash_sha256"),
    info={"owner": "ingestion"},
)


Index(
    "ix_historical_import_campaigns_status_created_at",
    historical_import_campaigns_table.c.status,
    historical_import_campaigns_table.c.created_at,
)
Index(
    "ix_historical_import_campaign_items_campaign_status",
    historical_import_campaign_items_table.c.campaign_id,
    historical_import_campaign_items_table.c.status,
)
Index(
    "uq_historical_import_campaign_items_source_manifest",
    historical_import_campaign_items_table.c.campaign_id,
    historical_import_campaign_items_table.c.relative_path,
    historical_import_campaign_items_table.c.manifest_identity,
    unique=True,
    postgresql_where=historical_import_campaign_items_table.c.item_kind == "source_file",
)
Index(
    "ix_processing_import_batch_items_campaign_item_outcome",
    processing_import_batch_items_table.c.campaign_item_id,
    processing_import_batch_items_table.c.outcome,
)


__all__ = [
    "historical_import_campaign_items_table",
    "historical_import_campaigns_table",
    "processing_import_batch_identities_table",
    "processing_import_batch_item_conflicts_table",
    "processing_import_batch_items_table",
]
