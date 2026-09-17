"""Artifact 元数据表；写 Owner 固定为 Platform。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

from aima_ugc.platform.database.metadata import metadata

artifacts_table = Table(
    "artifacts",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("kind", Text(), nullable=False),
    Column("storage_backend", Text(), nullable=False),
    Column("storage_key", Text(), nullable=False),
    Column("content_type", Text(), nullable=False),
    Column("encoding", Text()),
    Column("sha256", Text()),
    Column("byte_size", BigInteger()),
    Column("retention_class", Text(), nullable=False),
    Column("storage_status", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("stored_at", DateTime(timezone=True)),
    Column("linked_at", DateTime(timezone=True)),
    Column("expires_at", DateTime(timezone=True)),
    Column("deleted_at", DateTime(timezone=True)),
    UniqueConstraint("storage_backend", "storage_key"),
    CheckConstraint(
        "storage_status in ('pending','stored','linked','delete_pending','deleted','error')",
        name="storage_status_allowed",
    ),
    CheckConstraint(
        "(storage_status = 'pending' and sha256 is null and byte_size is null "
        "and stored_at is null and linked_at is null and deleted_at is null) or "
        "(storage_status = 'stored' and sha256 is not null and byte_size >= 0 "
        "and stored_at is not null and linked_at is null and deleted_at is null) or "
        "(storage_status = 'linked' and sha256 is not null and byte_size >= 0 "
        "and stored_at is not null and linked_at is not null and deleted_at is null) or "
        "(storage_status = 'delete_pending' and sha256 is not null and byte_size >= 0 "
        "and stored_at is not null and deleted_at is null) or "
        "(storage_status = 'deleted' and sha256 is not null and byte_size >= 0 "
        "and stored_at is not null and deleted_at is not null) or storage_status = 'error'",
        name="storage_state_consistent",
    ),
    info={"owner": "platform"},
)

canonical_artifact_links_table = Table(
    "canonical_artifact_links",
    metadata,
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id"), primary_key=True),
    Column(
        "processing_import_batch_id",
        Uuid(),
        ForeignKey("processing_import_batches.id"),
    ),
    Column(
        "historical_import_campaign_item_id",
        Uuid(),
        ForeignKey("historical_import_campaign_items.id"),
    ),
    Column("collection_scope_id", Uuid(), ForeignKey("collection_scopes.id")),
    Column(
        "provider_attempt_id",
        Uuid(),
        ForeignKey("provider_request_attempts.id"),
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "num_nonnulls(processing_import_batch_id, historical_import_campaign_item_id, "
        "collection_scope_id, provider_attempt_id) = 1",
        name="source_parent_exactly_one",
    ),
    CheckConstraint("collection_scope_id is null", name="scope_only_forbidden"),
    info={"owner": "platform"},
)

Index(
    "ix_canonical_artifact_links_processing_import_batch_id",
    canonical_artifact_links_table.c.processing_import_batch_id,
)
Index(
    "ix_canonical_artifact_links_historical_import_campaign_item_id",
    canonical_artifact_links_table.c.historical_import_campaign_item_id,
)
Index(
    "ix_canonical_artifact_links_collection_scope_id",
    canonical_artifact_links_table.c.collection_scope_id,
)
Index(
    "ix_canonical_artifact_links_provider_attempt_id",
    canonical_artifact_links_table.c.provider_attempt_id,
)
Index(
    "uq_canonical_artifact_links_processing_import_batch_id",
    canonical_artifact_links_table.c.processing_import_batch_id,
    unique=True,
    postgresql_where=canonical_artifact_links_table.c.processing_import_batch_id.is_not(None),
)
Index(
    "uq_canonical_artifact_links_historical_import_campaign_item_id",
    canonical_artifact_links_table.c.historical_import_campaign_item_id,
    unique=True,
    postgresql_where=(
        canonical_artifact_links_table.c.historical_import_campaign_item_id.is_not(None)
    ),
)
Index(
    "uq_canonical_artifact_links_provider_attempt_id",
    canonical_artifact_links_table.c.provider_attempt_id,
    unique=True,
    postgresql_where=canonical_artifact_links_table.c.provider_attempt_id.is_not(None),
)

__all__ = ["artifacts_table", "canonical_artifact_links_table"]
