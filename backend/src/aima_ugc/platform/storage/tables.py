"""Artifact 元数据表；写 Owner 固定为 Platform。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
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
    info={"owner": "operations"},
)
