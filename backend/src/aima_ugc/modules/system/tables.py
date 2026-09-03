"""System 模块拥有的数据表。"""

from sqlalchemy import (
    Boolean,
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

from aima_ugc.contracts.platform import PLATFORM_SCOPES
from aima_ugc.platform.database.metadata import metadata

_PLATFORM_SCOPE_CHECK = (
    "platform_scope in (" + ",".join(f"'{value}'" for value in PLATFORM_SCOPES) + ")"
)

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

provider_configs_table = Table(
    "provider_configs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("provider", Text(), nullable=False),
    Column("provider_kind", Text(), nullable=False, server_default=text("'collection'")),
    Column("display_name", Text(), nullable=False),
    Column("base_url", Text(), nullable=False),
    Column("model", Text()),
    Column("secret_ref", Text(), nullable=False),
    Column("timeout_seconds", Integer(), nullable=False, server_default=text("45")),
    Column("max_retries", Integer(), nullable=False, server_default=text("3")),
    Column("max_concurrency", Integer(), nullable=False, server_default=text("5")),
    Column("max_rps", Integer()),
    Column("extra_config", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("is_default", Boolean(), nullable=False, server_default=text("false")),
    Column("revision", Integer(), nullable=False, server_default=text("1")),
    Column("enabled", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(provider) > 0", name="provider_nonempty"),
    CheckConstraint("provider_kind in ('collection','llm')", name="provider_kind_allowed"),
    CheckConstraint("char_length(display_name) > 0", name="display_name_nonempty"),
    CheckConstraint("char_length(base_url) > 0", name="base_url_nonempty"),
    CheckConstraint("char_length(secret_ref) > 0", name="secret_ref_nonempty"),
    CheckConstraint("timeout_seconds > 0", name="timeout_seconds_positive"),
    CheckConstraint("max_retries >= 0", name="max_retries_nonnegative"),
    CheckConstraint("max_concurrency > 0", name="max_concurrency_positive"),
    CheckConstraint("max_rps is null or max_rps > 0", name="max_rps_positive_or_null"),
    CheckConstraint("revision > 0", name="revision_positive"),
    CheckConstraint(
        "provider_kind <> 'llm' or (model is not null and char_length(model) > 0)",
        name="llm_model_required",
    ),
    info={"owner": "system"},
)

keyword_packs_table = Table(
    "keyword_packs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("name", Text(), nullable=False),
    Column("description", Text(), nullable=False, server_default=text("''")),
    Column("enabled", Boolean(), nullable=False, server_default=text("true")),
    Column("version", Integer(), nullable=False, server_default=text("1")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("name"),
    CheckConstraint("char_length(name) > 0", name="name_nonempty"),
    CheckConstraint("version > 0", name="version_positive"),
    info={"owner": "system"},
)

keywords_table = Table(
    "keywords",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("text", Text(), nullable=False),
    Column("normalized_text", Text(), nullable=False),
    Column("enabled", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("normalized_text"),
    CheckConstraint("char_length(text) > 0", name="text_nonempty"),
    CheckConstraint("char_length(normalized_text) > 0", name="normalized_text_nonempty"),
    info={"owner": "system"},
)

keyword_pack_items_table = Table(
    "keyword_pack_items",
    metadata,
    Column("pack_id", Uuid(), ForeignKey("keyword_packs.id"), primary_key=True),
    Column("keyword_id", Uuid(), ForeignKey("keywords.id"), primary_key=True),
    Column("platform_scope", Text(), primary_key=True),
    Column("priority", Integer(), nullable=False, server_default=text("100")),
    Column("enabled", Boolean(), nullable=False, server_default=text("true")),
    Column("note", Text(), nullable=False, server_default=text("''")),
    CheckConstraint(_PLATFORM_SCOPE_CHECK, name="platform_scope_allowed"),
    info={"owner": "system"},
)

global_relevance_config_table = Table(
    "global_relevance_config",
    metadata,
    Column("singleton_key", Text(), primary_key=True),
    Column("keyword_pack_id", Uuid(), ForeignKey("keyword_packs.id"), nullable=False),
    Column("version", Integer(), nullable=False, server_default=text("1")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("singleton_key = 'global'", name="singleton_key_global"),
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
