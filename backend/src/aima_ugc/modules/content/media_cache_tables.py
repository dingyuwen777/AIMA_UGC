"""内容媒体可丢弃缓存的当前绑定表。"""

from aima_ugc.platform.database.metadata import metadata
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    Uuid,
)


content_media_cache_entries_table = Table(
    "content_media_cache_entries",
    metadata,
    Column("content_id", Uuid(), ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("source_url_hash", Text(), nullable=False),
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id"), nullable=False, unique=True),
    Column("cached_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("position >= 0", name="position_nonnegative"),
    CheckConstraint("char_length(source_url_hash) = 64", name="source_url_hash_sha256"),
    info={"owner": "content"},
)


__all__ = ["content_media_cache_entries_table"]
