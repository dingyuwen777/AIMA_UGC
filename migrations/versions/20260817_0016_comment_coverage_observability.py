"""补齐评论 Coverage 可观测字段与来源幂等约束。

Revision ID: 20260817_0016
Revises: 20260817_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0016"
down_revision: str | Sequence[str] | None = "20260817_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为 Stage 7 已批准的 Coverage 语义补齐可审计字段。"""
    op.add_column(
        "comment_coverage_observations",
        sa.Column("sample_mode", sa.Text(), nullable=True),
    )
    op.add_column(
        "comment_coverage_observations",
        sa.Column("sort_mode", sa.Text(), nullable=True),
    )
    op.add_column(
        "comment_coverage_observations",
        sa.Column("target_count", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "comment_coverage_observations",
        sa.Column("stop_reason", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_comment_coverage_observations_target_count_nonnegative"),
        "comment_coverage_observations",
        "target_count is null or target_count >= 0",
    )
    op.create_unique_constraint(
        op.f("uq_comment_coverage_observations_source"),
        "comment_coverage_observations",
        ["content_id", "provider_attempt_id", "raw_artifact_id"],
    )


def downgrade() -> None:
    """只回退 0016 新增 Coverage 字段，不删除既有 Coverage 事实。"""
    op.drop_constraint(
        op.f("uq_comment_coverage_observations_source"),
        "comment_coverage_observations",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_comment_coverage_observations_target_count_nonnegative"),
        "comment_coverage_observations",
        type_="check",
    )
    op.drop_column("comment_coverage_observations", "stop_reason")
    op.drop_column("comment_coverage_observations", "target_count")
    op.drop_column("comment_coverage_observations", "sort_mode")
    op.drop_column("comment_coverage_observations", "sample_mode")
