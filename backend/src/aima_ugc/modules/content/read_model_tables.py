"""声音广场的派生读模型、筛选目录与可恢复回填状态。"""

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
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from aima_ugc.platform.database.metadata import metadata

voice_plaza_content_projection_table = Table(
    "voice_plaza_content_projection",
    metadata,
    Column(
        "content_id",
        Uuid(),
        ForeignKey("contents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("content_version", Integer(), nullable=False),
    Column("platform", Text(), nullable=False),
    Column("content_type", Text(), nullable=False),
    Column("published_at", DateTime(timezone=True)),
    Column("sort_at", DateTime(timezone=True), nullable=False),
    Column("is_visible", Boolean(), nullable=False),
    Column("analysis_result_id", Uuid(), ForeignKey("analysis_content_results.id")),
    Column("analysis_status", Text(), nullable=False),
    Column("effective_relevance", Text()),
    Column("relevance_source", Text()),
    Column("effective_voice_type", Text()),
    Column("effective_sentiment", Text()),
    Column("labels", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    Column(
        "brand_ids",
        ARRAY(Uuid()),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    ),
    Column(
        "vehicle_model_ids",
        ARRAY(Uuid()),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    ),
    Column("competition_scope", Text(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    CheckConstraint(
        "analysis_status in ('completed','pending','stale')",
        name="analysis_status_allowed",
    ),
    CheckConstraint(
        "effective_relevance is null or effective_relevance in ('relevant','irrelevant')",
        name="effective_relevance_allowed",
    ),
    CheckConstraint(
        "relevance_source is null or relevance_source in ('ai','manual_review')",
        name="relevance_source_allowed",
    ),
    CheckConstraint(
        "(effective_relevance is null) = (relevance_source is null)",
        name="relevance_projection_consistent",
    ),
    CheckConstraint("jsonb_typeof(labels) = 'array'", name="labels_array"),
    CheckConstraint(
        "competition_scope in "
        "('none_detected','owned_only','competitor_only','other_only','mixed')",
        name="competition_scope_allowed",
    ),
    info={"owner": "content", "derived": True},
)

_VISIBLE_RELEVANT = text("is_visible IS TRUE AND effective_relevance IS DISTINCT FROM 'irrelevant'")

Index(
    "ix_voice_plaza_projection_latest",
    voice_plaza_content_projection_table.c.sort_at.desc(),
    voice_plaza_content_projection_table.c.content_id.desc(),
    postgresql_where=_VISIBLE_RELEVANT,
)
Index(
    "ix_voice_plaza_projection_published_latest",
    voice_plaza_content_projection_table.c.published_at.desc().nulls_last(),
    voice_plaza_content_projection_table.c.content_id.desc(),
    postgresql_where=_VISIBLE_RELEVANT,
)
Index(
    "ix_voice_plaza_projection_platform_latest",
    voice_plaza_content_projection_table.c.platform,
    voice_plaza_content_projection_table.c.published_at.desc().nulls_last(),
    voice_plaza_content_projection_table.c.content_id.desc(),
    postgresql_where=_VISIBLE_RELEVANT,
)
Index(
    "ix_voice_plaza_projection_content_type_latest",
    voice_plaza_content_projection_table.c.content_type,
    voice_plaza_content_projection_table.c.published_at.desc().nulls_last(),
    voice_plaza_content_projection_table.c.content_id.desc(),
    postgresql_where=_VISIBLE_RELEVANT,
)
Index(
    "ix_voice_plaza_projection_analysis_status_latest",
    voice_plaza_content_projection_table.c.analysis_status,
    voice_plaza_content_projection_table.c.published_at.desc().nulls_last(),
    voice_plaza_content_projection_table.c.content_id.desc(),
    postgresql_where=text("is_visible IS TRUE"),
)
Index(
    "ix_voice_plaza_projection_relevance_latest",
    voice_plaza_content_projection_table.c.effective_relevance,
    voice_plaza_content_projection_table.c.published_at.desc().nulls_last(),
    voice_plaza_content_projection_table.c.content_id.desc(),
    postgresql_where=text("is_visible IS TRUE"),
)
Index(
    "ix_voice_plaza_projection_labels_gin",
    voice_plaza_content_projection_table.c.labels,
    postgresql_using="gin",
)
Index(
    "ix_voice_plaza_projection_brand_ids_gin",
    voice_plaza_content_projection_table.c.brand_ids,
    postgresql_using="gin",
)
Index(
    "ix_voice_plaza_projection_vehicle_ids_gin",
    voice_plaza_content_projection_table.c.vehicle_model_ids,
    postgresql_using="gin",
)


voice_plaza_filter_catalog_table = Table(
    "voice_plaza_filter_catalog",
    metadata,
    Column("dimension", Text(), primary_key=True),
    Column("value", Text(), primary_key=True),
    Column("secondary_value", Text(), primary_key=True, server_default=text("''")),
    Column("content_count", BigInteger(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "dimension in ('content_type','sentiment','voice_type','label')",
        name="dimension_allowed",
    ),
    CheckConstraint("char_length(value) > 0", name="value_nonempty"),
    CheckConstraint("content_count > 0", name="content_count_positive"),
    info={"owner": "content", "derived": True},
)


voice_plaza_filter_catalog_entries_table = Table(
    "voice_plaza_filter_catalog_entries",
    metadata,
    Column(
        "content_id",
        Uuid(),
        ForeignKey("voice_plaza_content_projection.content_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("dimension", Text(), primary_key=True),
    Column("value", Text(), primary_key=True),
    Column("secondary_value", Text(), primary_key=True, server_default=text("''")),
    CheckConstraint(
        "dimension in ('content_type','sentiment','voice_type','label')",
        name="dimension_allowed",
    ),
    CheckConstraint("char_length(value) > 0", name="value_nonempty"),
    Index(
        "ix_voice_plaza_filter_entries_catalog",
        "dimension",
        "value",
        "secondary_value",
    ),
    info={"owner": "content", "derived": True},
)


voice_plaza_projection_state_table = Table(
    "voice_plaza_projection_state",
    metadata,
    Column("singleton", Boolean(), primary_key=True, server_default=text("true")),
    Column("status", Text(), nullable=False),
    Column("generation", Integer(), nullable=False, server_default=text("1")),
    Column("last_content_id", Uuid()),
    Column("projected_count", BigInteger(), nullable=False, server_default=text("0")),
    Column("total_content_count", BigInteger()),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("last_error_code", Text()),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("singleton", name="singleton_true"),
    CheckConstraint(
        "status in ('pending','running','ready','failed')",
        name="status_allowed",
    ),
    CheckConstraint("generation > 0", name="generation_positive"),
    CheckConstraint("projected_count >= 0", name="projected_count_nonnegative"),
    CheckConstraint(
        "total_content_count is null or total_content_count >= 0",
        name="total_content_count_nonnegative",
    ),
    info={"owner": "content", "derived": True},
)


__all__ = [
    "voice_plaza_content_projection_table",
    "voice_plaza_filter_catalog_entries_table",
    "voice_plaza_filter_catalog_table",
    "voice_plaza_projection_state_table",
]
