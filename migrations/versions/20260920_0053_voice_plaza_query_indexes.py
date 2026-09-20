"""增加声音广场首屏、评论与分析投影查询索引。

Revision ID: 20260920_0053
Revises: 20260913_0052
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0053"
down_revision: str | Sequence[str] | None = "20260913_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为声音广场高频排序与分页读取建立匹配索引。"""

    op.create_index(
        "ix_contents_published_at_id_desc",
        "contents",
        [
            sa.text("published_at DESC NULLS LAST"),
            sa.text("id DESC"),
        ],
    )
    op.create_index(
        "ix_comments_content_roots_published_desc",
        "comments",
        [
            "content_id",
            sa.text("published_at DESC NULLS LAST"),
            sa.text("id DESC"),
        ],
        postgresql_where=sa.text(
            "root_comment_id IS NULL OR root_comment_id = external_comment_id"
        ),
    )
    op.create_index(
        "ix_comments_content_thread_published",
        "comments",
        [
            "content_id",
            "root_comment_id",
            sa.text("published_at ASC NULLS LAST"),
            sa.text("id ASC"),
        ],
    )
    op.create_index(
        "ix_analysis_results_content_version_run",
        "analysis_content_results",
        ["content_id", "content_version", "analysis_run_id"],
    )
    op.create_index(
        "ix_analysis_targets_content_version_run",
        "analysis_content_run_targets",
        ["content_id", "content_version", "run_id"],
    )


def downgrade() -> None:
    """删除声音广场查询索引。"""

    op.drop_index(
        "ix_analysis_targets_content_version_run",
        table_name="analysis_content_run_targets",
    )
    op.drop_index(
        "ix_analysis_results_content_version_run",
        table_name="analysis_content_results",
    )
    op.drop_index("ix_comments_content_thread_published", table_name="comments")
    op.drop_index("ix_comments_content_roots_published_desc", table_name="comments")
    op.drop_index("ix_contents_published_at_id_desc", table_name="contents")
