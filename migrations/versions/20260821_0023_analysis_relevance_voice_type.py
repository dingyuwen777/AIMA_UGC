"""增加 Analysis 语义相关性与发声类型。

Revision ID: 20260821_0023
Revises: 20260821_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0023"
down_revision: str | Sequence[str] | None = "20260821_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_content_results", sa.Column("relevance", sa.Text(), nullable=True))
    op.add_column("analysis_content_results", sa.Column("voice_type", sa.Text(), nullable=True))
    op.alter_column("analysis_content_results", "sentiment", existing_type=sa.Text(), nullable=True)
    op.execute(
        "UPDATE analysis_content_results "
        "SET relevance = 'relevant', voice_type = 'unknown' "
        "WHERE relevance IS NULL OR voice_type IS NULL"
    )
    op.alter_column(
        "analysis_content_results", "relevance", existing_type=sa.Text(), nullable=False
    )
    op.alter_column(
        "analysis_content_results", "voice_type", existing_type=sa.Text(), nullable=False
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_relevance_allowed"),
        "analysis_content_results",
        "relevance in ('relevant','irrelevant')",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_voice_type_allowed"),
        "analysis_content_results",
        "voice_type in ('user_voice','creator_marketing','brand_official','dealer_promotion',"
        "'media_information','other_organization','unknown')",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_relevance_sentiment_consistent"),
        "analysis_content_results",
        "(relevance = 'relevant' and sentiment is not null) or "
        "(relevance = 'irrelevant' and sentiment is null)",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_content_request_items SET status = 'failed', "
        "analysis_result_id = NULL, error_code = 'analysis_v3_irrelevant_downgrade' "
        "WHERE analysis_result_id IN (SELECT id FROM analysis_content_results "
        "WHERE relevance = 'irrelevant')"
    )
    op.execute("DELETE FROM analysis_content_results WHERE relevance = 'irrelevant'")
    op.drop_constraint(
        op.f("ck_analysis_content_results_relevance_sentiment_consistent"),
        "analysis_content_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_results_voice_type_allowed"),
        "analysis_content_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_results_relevance_allowed"),
        "analysis_content_results",
        type_="check",
    )
    op.alter_column(
        "analysis_content_results", "sentiment", existing_type=sa.Text(), nullable=False
    )
    op.drop_column("analysis_content_results", "voice_type")
    op.drop_column("analysis_content_results", "relevance")
