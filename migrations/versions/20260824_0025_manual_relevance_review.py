"""增加双向人工相关性复核与撤销事件账本。

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
        sa.Column("analysis_result_id", sa.Uuid(), nullable=False),
        sa.Column("review_no", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version >= 1",
            name=op.f("ck_analysis_content_relevance_reviews_content_version_positive"),
        ),
        sa.CheckConstraint(
            "review_no >= 1",
            name=op.f("ck_analysis_content_relevance_reviews_review_no_positive"),
        ),
        sa.CheckConstraint(
            "decision in ('relevant','irrelevant','inherit_ai')",
            name=op.f("ck_analysis_content_relevance_reviews_decision_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(request_id) > 0",
            name=op.f("ck_analysis_content_relevance_reviews_request_id_nonempty"),
        ),
        sa.ForeignKeyConstraint(["analysis_result_id"], ["analysis_content_results.id"]),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_id",
            "content_version",
            "review_no",
            name="uq_analysis_content_relevance_reviews_content_version_review_no",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION reject_analysis_relevance_review_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% 是追加账本，禁止 %', TG_TABLE_NAME, TG_OP;
        END; $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_analysis_content_relevance_reviews_append_only
        BEFORE UPDATE OR DELETE ON analysis_content_relevance_reviews
        FOR EACH ROW EXECUTE FUNCTION reject_analysis_relevance_review_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_analysis_content_relevance_reviews_append_only
        ON analysis_content_relevance_reviews;
        DROP FUNCTION IF EXISTS reject_analysis_relevance_review_mutation();
        """
    )
    op.drop_table("analysis_content_relevance_reviews")
