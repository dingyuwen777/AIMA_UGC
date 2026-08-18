"""Stage 1-7 全面整改补齐的 Content Owner Canonical 子实体表。"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata


def _source_columns() -> tuple[Column, Column, Column]:
    """来源由 Attempt+Raw 复合 FK 统一约束，避免两个冗余单列来源 FK。"""
    return (
        Column("provider_attempt_id", Uuid(), nullable=False),
        Column("raw_artifact_id", Uuid(), nullable=False),
        Column("observed_at", DateTime(timezone=True), nullable=False),
    )


content_external_ids_table = Table(
    "content_external_ids",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("id_type", Text(), primary_key=True),
    Column("external_id", Text(), nullable=False),
    *_source_columns(),
    CheckConstraint("char_length(id_type) > 0", name="id_type_nonempty"),
    CheckConstraint("char_length(external_id) > 0", name="external_id_nonempty"),
    info={"owner": "content"},
)

content_media_table = Table(
    "content_media",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("media_type", Text(), nullable=False),
    Column("external_media_id", Text()),
    Column("url", Text()),
    Column("preview_url", Text()),
    Column("width", BigInteger()),
    Column("height", BigInteger()),
    Column("duration_ms", BigInteger()),
    Column("mime_type", Text()),
    Column("alt_text", Text()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint(
        "media_type in ('image','video','live_photo','audio','cover','other')",
        name="media_type_allowed",
    ),
    info={"owner": "content"},
)

content_topics_table = Table(
    "content_topics",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("name", Text(), nullable=False),
    Column("external_topic_id", Text()),
    Column("url", Text()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint("char_length(name) > 0", name="name_nonempty"),
    info={"owner": "content"},
)

content_mentions_table = Table(
    "content_mentions",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("external_account_id", Text()),
    Column("handle", Text()),
    Column("display_name", Text()),
    Column("profile_url", Text()),
    Column("avatar_url", Text()),
    Column("bio", Text()),
    Column("verified", Boolean()),
    Column("verification_label", Text()),
    Column("region", Text()),
    Column("follower_count", BigInteger()),
    Column("following_count", BigInteger()),
    Column("content_count", BigInteger()),
    Column("total_like_count", BigInteger()),
    Column("alternate_ids", JSONB(), nullable=False),
    Column("display_text", Text()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint(
        "jsonb_typeof(alternate_ids) = 'object'",
        name="alternate_ids_object",
    ),
    info={"owner": "content"},
)

content_locations_table = Table(
    "content_locations",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("location_type", Text(), nullable=False),
    Column("label", Text(), nullable=False),
    Column("country", Text()),
    Column("region", Text()),
    Column("city", Text()),
    Column("latitude", Float()),
    Column("longitude", Float()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint(
        "location_type in ('place','ip_region')",
        name="location_type_allowed",
    ),
    CheckConstraint(
        "latitude is null or latitude between -90 and 90",
        name="latitude_range",
    ),
    CheckConstraint(
        "longitude is null or longitude between -180 and 180",
        name="longitude_range",
    ),
    info={"owner": "content"},
)

comment_media_table = Table(
    "comment_media",
    metadata,
    Column("comment_id", Uuid(), ForeignKey("comments.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("media_type", Text(), nullable=False),
    Column("external_media_id", Text()),
    Column("url", Text()),
    Column("preview_url", Text()),
    Column("width", BigInteger()),
    Column("height", BigInteger()),
    Column("duration_ms", BigInteger()),
    Column("mime_type", Text()),
    Column("alt_text", Text()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint(
        "media_type in ('image','video','live_photo','audio','cover','other')",
        name="media_type_allowed",
    ),
    info={"owner": "content"},
)

comment_mentions_table = Table(
    "comment_mentions",
    metadata,
    Column("comment_id", Uuid(), ForeignKey("comments.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("external_account_id", Text()),
    Column("handle", Text()),
    Column("display_name", Text()),
    Column("profile_url", Text()),
    Column("avatar_url", Text()),
    Column("bio", Text()),
    Column("verified", Boolean()),
    Column("verification_label", Text()),
    Column("region", Text()),
    Column("follower_count", BigInteger()),
    Column("following_count", BigInteger()),
    Column("content_count", BigInteger()),
    Column("total_like_count", BigInteger()),
    Column("alternate_ids", JSONB(), nullable=False),
    Column("display_text", Text()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint(
        "jsonb_typeof(alternate_ids) = 'object'",
        name="alternate_ids_object",
    ),
    info={"owner": "content"},
)

comment_locations_table = Table(
    "comment_locations",
    metadata,
    Column("comment_id", Uuid(), ForeignKey("comments.id"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("location_type", Text(), nullable=False),
    Column("label", Text(), nullable=False),
    Column("country", Text()),
    Column("region", Text()),
    Column("city", Text()),
    Column("latitude", Float()),
    Column("longitude", Float()),
    *_source_columns(),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint(
        "location_type in ('place','ip_region')",
        name="location_type_allowed",
    ),
    CheckConstraint(
        "latitude is null or latitude between -90 and 90",
        name="latitude_range",
    ),
    CheckConstraint(
        "longitude is null or longitude between -180 and 180",
        name="longitude_range",
    ),
    info={"owner": "content"},
)

comment_thread_coverage_observations_table = Table(
    "comment_thread_coverage_observations",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("root_comment_id", Text(), nullable=False),
    *_source_columns(),
    Column("coverage", Text(), nullable=False),
    Column("reported_total", BigInteger()),
    Column("captured_count", BigInteger(), nullable=False),
    Column("target_count", BigInteger()),
    Column("stop_reason", Text(), nullable=False),
    UniqueConstraint(
        "content_id",
        "root_comment_id",
        "provider_attempt_id",
        "raw_artifact_id",
        name="uq_comment_thread_coverage_source",
    ),
    CheckConstraint("char_length(root_comment_id) > 0", name="root_id_nonempty"),
    CheckConstraint(
        "coverage in ('complete','partial','not_requested','unavailable')",
        name="coverage_allowed",
    ),
    CheckConstraint("captured_count >= 0", name="captured_nonneg"),
    CheckConstraint(
        "reported_total is null or reported_total >= 0",
        name="reported_nonneg",
    ),
    CheckConstraint(
        "target_count is null or target_count >= 0",
        name="target_nonneg",
    ),
    info={"owner": "content"},
)

__all__ = [
    "comment_locations_table",
    "comment_media_table",
    "comment_mentions_table",
    "comment_thread_coverage_observations_table",
    "content_external_ids_table",
    "content_locations_table",
    "content_media_table",
    "content_mentions_table",
    "content_topics_table",
]
