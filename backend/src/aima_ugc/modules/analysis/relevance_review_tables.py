"""Analysis Owner 的人工相关性复核 Schema。"""

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
)

from aima_ugc.platform.database.metadata import metadata

analysis_content_relevance_reviews_table = Table(
    "analysis_content_relevance_reviews",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column(
        "analysis_result_id",
        Uuid(),
        ForeignKey("analysis_content_results.id"),
        nullable=False,
    ),
    Column("decision", Text(), nullable=False),
    Column("request_id", Text(), nullable=False),
    Column("reviewed_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "content_id",
        "content_version",
        name="uq_analysis_content_relevance_reviews_content_version",
    ),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("decision = 'relevant'", name="decision_relevant_only"),
    CheckConstraint("char_length(request_id) > 0", name="request_id_nonempty"),
    info={"owner": "analysis"},
)


__all__ = ["analysis_content_relevance_reviews_table"]
