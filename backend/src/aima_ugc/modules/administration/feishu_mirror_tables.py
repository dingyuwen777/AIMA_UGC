"""管理员报告产生的飞书多维表双向镜像持久化。"""

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

feishu_bitable_mirrors_table = Table(
    "feishu_bitable_mirrors",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("publication_job_id", Uuid(), ForeignKey("jobs.id", ondelete="SET NULL")),
    Column("document_token", Text(), nullable=False),
    Column("document_url", Text(), nullable=False),
    Column("external_app_token", Text(), nullable=False),
    Column("external_table_id", Text(), nullable=False),
    Column("embedded_app_token", Text(), nullable=False),
    Column("embedded_table_id", Text(), nullable=False),
    Column("status", Text(), nullable=False, server_default=text("'active'")),
    Column("known_key_hashes", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    Column("last_synced_at", DateTime(timezone=True)),
    Column("next_sync_at", DateTime(timezone=True), nullable=False),
    Column("consecutive_failures", Integer(), nullable=False, server_default=text("0")),
    Column("last_error_code", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("publication_job_id"),
    UniqueConstraint("document_token"),
    UniqueConstraint("external_app_token", "external_table_id"),
    UniqueConstraint("embedded_app_token", "embedded_table_id"),
    CheckConstraint("status in ('active','paused')", name="status_allowed"),
    CheckConstraint("consecutive_failures >= 0", name="consecutive_failures_nonnegative"),
    info={"owner": "administration"},
)


__all__ = ["feishu_bitable_mirrors_table"]
