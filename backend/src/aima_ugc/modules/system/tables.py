"""System 模块拥有的 Stage 3A 数据表。"""

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, Table, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

system_settings_table = Table(
    "system_settings",
    metadata,
    Column("key", Text(), primary_key=True),
    Column("value", JSONB(), nullable=False),
    Column("version", Integer(), nullable=False, server_default=text("1")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(key) > 0", name="key_nonempty"),
    CheckConstraint("version > 0", name="version_positive"),
    info={"owner": "system"},
)

audit_events_table = Table(
    "audit_events",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("actor_kind", Text(), nullable=False),
    Column("actor_ref", Text()),
    Column("event_type", Text(), nullable=False),
    Column("object_type", Text()),
    Column("object_id", Text()),
    Column("request_id", Text()),
    Column("safe_detail", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("actor_kind in ('system','principal')", name="actor_kind_allowed"),
    CheckConstraint("char_length(event_type) > 0", name="event_type_nonempty"),
    info={"owner": "system"},
)
