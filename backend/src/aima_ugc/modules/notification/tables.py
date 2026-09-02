"""通知事件与 Principal Inbox 已读状态表。"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

notification_events_table = Table(
    "notification_events",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("deduplication_key", Text(), nullable=False),
    Column("event_type", Text(), nullable=False),
    Column("title", Text(), nullable=False),
    Column("message", Text(), nullable=False),
    Column("resource_type", Text()),
    Column("resource_id", Text()),
    Column("safe_detail", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("deduplication_key"),
    CheckConstraint("char_length(deduplication_key) > 0", name="deduplication_key_nonempty"),
    CheckConstraint("char_length(event_type) > 0", name="event_type_nonempty"),
    CheckConstraint("char_length(title) > 0", name="title_nonempty"),
    CheckConstraint("jsonb_typeof(safe_detail) = 'object'", name="safe_detail_object"),
    info={"owner": "notification"},
)

notification_inbox_items_table = Table(
    "notification_inbox_items",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("event_id", Uuid(), ForeignKey("notification_events.id"), nullable=False),
    Column("principal_id", Text(), nullable=False),
    Column("is_read", Boolean(), nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("read_at", DateTime(timezone=True)),
    UniqueConstraint("event_id", "principal_id"),
    CheckConstraint("char_length(principal_id) > 0", name="principal_id_nonempty"),
    CheckConstraint(
        "(is_read and read_at is not null) or (not is_read and read_at is null)",
        name="read_state_consistent",
    ),
    Index(
        "ix_notification_inbox_principal_created",
        "principal_id",
        "created_at",
    ),
    info={"owner": "notification"},
)

__all__ = ["notification_events_table", "notification_inbox_items_table"]
