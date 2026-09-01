"""内容分析人工纠正当前态；AI Result 仍保持不可变历史。"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

analysis_content_manual_overrides_table = Table(
    "analysis_content_manual_overrides",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("content_version", Integer(), primary_key=True),
    Column("voice_type", Text()),
    Column("sentiment", Text()),
    Column("labels", JSONB(), nullable=False),
    Column("voice_type_locked", Boolean(), nullable=False),
    Column("sentiment_locked", Boolean(), nullable=False),
    Column("labels_locked", Boolean(), nullable=False),
    Column("actor_ref", Text(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    CheckConstraint("jsonb_typeof(labels) = 'array'", name="labels_array"),
    CheckConstraint(
        "(voice_type_locked and voice_type is not null) or "
        "(not voice_type_locked and voice_type is null)",
        name="voice_type_lock_consistent",
    ),
    CheckConstraint(
        "(sentiment_locked and sentiment is not null) or "
        "(not sentiment_locked and sentiment is null)",
        name="sentiment_lock_consistent",
    ),
    CheckConstraint(
        "labels_locked or labels = '[]'::jsonb",
        name="labels_lock_consistent",
    ),
    CheckConstraint("char_length(actor_ref) > 0", name="actor_ref_nonempty"),
    info={"owner": "analysis"},
)

__all__ = ["analysis_content_manual_overrides_table"]
