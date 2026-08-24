"""增加 AI 不相关内容人工相关性复核表。

Revision ID: 20260824_0025
Revises: 20260822_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0025"
down_revision: str | Sequence[str] | None = "20260822_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_content_relevance_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version >= 1",
            name="ck_analysis_content_relevance_reviews_content_version_positive",
        ),
        sa.CheckConstraint(
            "decision = 'relevant'",
            name="ck_analysis_content_relevance_reviews_decision_relevant_only",
        ),
        sa.CheckConstraint(
            "char_length(request_id) > 0",
            name="ck_analysis_content_relevance_reviews_request_id_nonempty",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_id",
            "content_version",
            name="uq_analysis_content_relevance_reviews_content_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_content_relevance_reviews")
