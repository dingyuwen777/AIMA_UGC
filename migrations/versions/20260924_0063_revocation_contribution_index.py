"""按来源 Attempt 快速定位需要撤销的 Content 贡献。

Revision ID: 20260924_0063
Revises: 20260924_0062
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260924_0063"
down_revision: str | Sequence[str] | None = "20260924_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """并发建索引，避免在大表上长时间阻塞数据导入写入。"""

    with op.get_context().autocommit_block():
        # 并发创建中断时 PostgreSQL 可能留下 invalid 索引；重跑前清理同名残留。
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_content_source_contributions_attempt_content"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY ix_content_source_contributions_attempt_content "
            "ON content_source_contributions (provider_attempt_id, content_id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_content_source_contributions_attempt_content"
        )
