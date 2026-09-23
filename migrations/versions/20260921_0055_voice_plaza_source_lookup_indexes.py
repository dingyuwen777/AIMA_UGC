"""增加声音广场来源可见性反查索引。

Revision ID: 20260921_0055
Revises: 20260920_0054
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0055"
down_revision: str | Sequence[str] | None = "20260920_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为两类来源账本的 Content 可见性判断建立部分索引。"""

    op.create_index(
        "ix_processing_import_batch_items_content_id",
        "processing_import_batch_items",
        ["content_id"],
        postgresql_where=sa.text("content_id IS NOT NULL"),
    )
    op.create_index(
        "ix_collection_candidate_ingestions_content_id",
        "collection_candidate_ingestions",
        ["content_id"],
        postgresql_where=sa.text("content_id IS NOT NULL"),
    )


def downgrade() -> None:
    """删除声音广场来源可见性反查索引。"""

    op.drop_index(
        "ix_collection_candidate_ingestions_content_id",
        table_name="collection_candidate_ingestions",
    )
    op.drop_index(
        "ix_processing_import_batch_items_content_id",
        table_name="processing_import_batch_items",
    )
