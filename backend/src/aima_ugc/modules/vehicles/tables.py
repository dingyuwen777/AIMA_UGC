"""品牌车型目录、词包引用与内容证据表。"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)

from aima_ugc.platform.database.metadata import metadata

vehicle_catalog_versions_table = Table(
    "vehicle_catalog_versions",
    metadata,
    Column("version", Integer(), primary_key=True),
    Column("reason", Text(), nullable=False),
    Column("actor_ref", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("version > 0", name="version_positive"),
    CheckConstraint("char_length(reason) > 0", name="reason_nonempty"),
    info={"owner": "vehicles"},
)

vehicle_brands_table = Table(
    "vehicle_brands",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("code", Text(), nullable=False),
    Column("display_name", Text(), nullable=False),
    Column("role", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("version", Integer(), nullable=False),
    Column(
        "catalog_version", Integer(), ForeignKey("vehicle_catalog_versions.version"), nullable=False
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("code"),
    CheckConstraint("char_length(code) > 0", name="code_nonempty"),
    CheckConstraint("char_length(display_name) > 0", name="display_name_nonempty"),
    CheckConstraint("role in ('owned','competitor','other')", name="role_allowed"),
    CheckConstraint("status in ('active','deprecated')", name="status_allowed"),
    CheckConstraint("version > 0", name="version_positive"),
    info={"owner": "vehicles"},
)

vehicle_brand_aliases_table = Table(
    "vehicle_brand_aliases",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("brand_id", Uuid(), ForeignKey("vehicle_brands.id"), nullable=False),
    Column("text", Text(), nullable=False),
    Column("normalized_text", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("brand_id", "normalized_text"),
    CheckConstraint("char_length(text) > 0", name="text_nonempty"),
    CheckConstraint("char_length(normalized_text) > 0", name="normalized_text_nonempty"),
    info={"owner": "vehicles"},
)

vehicle_models_table = Table(
    "vehicle_models",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("code", Text(), nullable=False),
    Column("display_name", Text(), nullable=False),
    Column("series_name", Text()),
    Column("category_name", Text()),
    Column("brand_id", Uuid(), ForeignKey("vehicle_brands.id")),
    Column("status", Text(), nullable=False),
    Column("version", Integer(), nullable=False),
    Column(
        "catalog_version", Integer(), ForeignKey("vehicle_catalog_versions.version"), nullable=False
    ),
    Column("merged_into_id", Uuid(), ForeignKey("vehicle_models.id")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("code"),
    CheckConstraint("char_length(code) > 0", name="code_nonempty"),
    CheckConstraint("char_length(display_name) > 0", name="display_name_nonempty"),
    CheckConstraint(
        "series_name is null or char_length(trim(series_name)) between 1 and 200",
        name="series_name_valid",
    ),
    CheckConstraint(
        "category_name is null or char_length(trim(category_name)) between 1 and 200",
        name="category_name_valid",
    ),
    CheckConstraint("status in ('active','deprecated','merged')", name="status_allowed"),
    CheckConstraint("version > 0", name="version_positive"),
    CheckConstraint(
        "(status = 'merged' and merged_into_id is not null) or "
        "(status <> 'merged' and merged_into_id is null)",
        name="merged_target_consistent",
    ),
    Index("ix_vehicle_models_brand_id_status", "brand_id", "status"),
    info={"owner": "vehicles"},
)

vehicle_model_aliases_table = Table(
    "vehicle_model_aliases",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("vehicle_model_id", Uuid(), ForeignKey("vehicle_models.id"), nullable=False),
    Column("text", Text(), nullable=False),
    Column("normalized_text", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("vehicle_model_id", "normalized_text"),
    CheckConstraint("char_length(text) > 0", name="text_nonempty"),
    CheckConstraint("char_length(normalized_text) > 0", name="normalized_text_nonempty"),
    info={"owner": "vehicles"},
)

keyword_pack_vehicle_models_table = Table(
    "keyword_pack_vehicle_models",
    metadata,
    Column("pack_id", Uuid(), ForeignKey("keyword_packs.id"), primary_key=True),
    Column("vehicle_model_id", Uuid(), ForeignKey("vehicle_models.id"), primary_key=True),
    Column("enabled", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    info={"owner": "vehicles"},
)

content_vehicle_evidence_table = Table(
    "content_vehicle_evidence",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("vehicle_model_id", Uuid(), ForeignKey("vehicle_models.id"), nullable=False),
    Column("source", Text(), nullable=False),
    Column("matched_text", Text()),
    Column("source_field", Text()),
    Column(
        "catalog_version", Integer(), ForeignKey("vehicle_catalog_versions.version"), nullable=False
    ),
    Column("confidence", Float()),
    Column("is_manual_locked", Boolean(), nullable=False, server_default=text("false")),
    Column("is_active", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "content_id",
        "content_version",
        "vehicle_model_id",
        "source",
        "catalog_version",
        name="uq_content_vehicle_evidence_identity",
    ),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    CheckConstraint(
        "source in ('alias_match','ai_candidate','manual_review','import')",
        name="source_allowed",
    ),
    CheckConstraint(
        "confidence is null or (confidence >= 0 and confidence <= 1)",
        name="confidence_range",
    ),
    Index(
        "ix_content_vehicle_evidence_active_vehicle",
        "vehicle_model_id",
        "content_id",
        postgresql_where=text("is_active"),
    ),
    info={"owner": "vehicles"},
)

content_vehicle_review_locks_table = Table(
    "content_vehicle_review_locks",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("content_version", Integer(), primary_key=True),
    Column("is_locked", Boolean(), nullable=False),
    Column("actor_ref", Text(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    CheckConstraint("char_length(actor_ref) > 0", name="actor_ref_nonempty"),
    info={"owner": "vehicles"},
)

content_brand_evidence_table = Table(
    "content_brand_evidence",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("brand_id", Uuid(), ForeignKey("vehicle_brands.id"), nullable=False),
    Column("source", Text(), nullable=False),
    Column("matched_text", Text()),
    Column("source_field", Text()),
    Column("derived_vehicle_model_id", Uuid(), ForeignKey("vehicle_models.id")),
    Column(
        "catalog_version", Integer(), ForeignKey("vehicle_catalog_versions.version"), nullable=False
    ),
    Column("confidence", Float()),
    Column("is_manual_locked", Boolean(), nullable=False, server_default=text("false")),
    Column("is_active", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    CheckConstraint(
        "source in ('alias_match','vehicle_match','manual_review','import')",
        name="source_allowed",
    ),
    CheckConstraint(
        "(source = 'vehicle_match' and derived_vehicle_model_id is not null) or "
        "(source <> 'vehicle_match' and derived_vehicle_model_id is null)",
        name="derived_vehicle_model_consistent",
    ),
    CheckConstraint(
        "confidence is null or (confidence >= 0 and confidence <= 1)",
        name="confidence_range",
    ),
    Index(
        "uq_content_brand_evidence_direct_identity",
        "content_id",
        "content_version",
        "brand_id",
        "source",
        "catalog_version",
        unique=True,
        postgresql_where=text("derived_vehicle_model_id is null"),
    ),
    Index(
        "uq_content_brand_evidence_vehicle_identity",
        "content_id",
        "content_version",
        "brand_id",
        "source",
        "derived_vehicle_model_id",
        "catalog_version",
        unique=True,
        postgresql_where=text("derived_vehicle_model_id is not null"),
    ),
    Index(
        "ix_content_brand_evidence_active_content",
        "content_id",
        "content_version",
        "brand_id",
        postgresql_where=text("is_active"),
    ),
    Index(
        "ix_content_brand_evidence_active_brand",
        "brand_id",
        "content_id",
        postgresql_where=text("is_active"),
    ),
    info={"owner": "vehicles"},
)

content_brand_review_locks_table = Table(
    "content_brand_review_locks",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("content_version", Integer(), primary_key=True),
    Column("is_locked", Boolean(), nullable=False),
    Column("actor_ref", Text(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    CheckConstraint("char_length(actor_ref) > 0", name="actor_ref_nonempty"),
    info={"owner": "vehicles"},
)

__all__ = [
    "content_brand_evidence_table",
    "content_brand_review_locks_table",
    "content_vehicle_evidence_table",
    "content_vehicle_review_locks_table",
    "keyword_pack_vehicle_models_table",
    "vehicle_brand_aliases_table",
    "vehicle_brands_table",
    "vehicle_catalog_versions_table",
    "vehicle_model_aliases_table",
    "vehicle_models_table",
]
