"""Analysis Owner 的人工相关性复核追加事件 Schema。"""

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
    Column("review_no", Integer(), nullable=False),
    Column("decision", Text(), nullable=False),
    Column("request_id", Text(), nullable=False),
    Column("reviewed_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "content_id",
        "content_version",
        "review_no",
        name="uq_analysis_content_relevance_reviews_content_version_review_no",
    ),
    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("review_no >= 1", name="review_no_positive"),
    CheckConstraint(
        "decision in ('relevant','irrelevant','inherit_ai')",
        name="decision_allowed",
    ),
    CheckConstraint("char_length(request_id) > 0", name="request_id_nonempty"),
    info={"owner": "analysis"},
)


__all__ = ["analysis_content_relevance_reviews_table"]
