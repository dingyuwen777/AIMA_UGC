"""Content Owner 的来源贡献账本；为可逆生命周期操作保留 before/after Delta。"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

content_source_contributions_table = Table(
    "content_source_contributions",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("source_item_key", Text(), nullable=False, unique=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column(
        "provider_attempt_id",
        Uuid(),
        ForeignKey("provider_request_attempts.id"),
        nullable=False,
    ),
    Column("raw_artifact_id", Uuid(), ForeignKey("artifacts.id"), nullable=False),
    Column("version_before", Integer()),
    Column("version_after", Integer(), nullable=False),
    Column("delta", JSONB(), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(source_item_key) = 64", name="source_item_key_sha256"),
    CheckConstraint(
        "version_before is null or version_before >= 1",
        name="version_before_positive",
    ),
    CheckConstraint("version_after >= 1", name="version_after_positive"),
    CheckConstraint("jsonb_typeof(delta) = 'object'", name="delta_object"),
    info={"owner": "content"},
)


__all__ = ["content_source_contributions_table"]
