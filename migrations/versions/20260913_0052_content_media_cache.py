"""增加可重建的 Content Media Cache 绑定。

Revision ID: 20260913_0052
Revises: 20260911_0051
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0052"
down_revision: str | Sequence[str] | None = "20260911_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立 Content 媒体位置到可丢弃缓存 Artifact 的当前绑定。"""

    op.create_table(
        "content_media_cache_entries",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_url_hash", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("position >= 0", name=op.f("ck_content_media_cache_entries_position_nonnegative")),
        sa.CheckConstraint(
            "char_length(source_url_hash) = 64",
            name=op.f("ck_content_media_cache_entries_source_url_hash_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_content_media_cache_entries_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_media_cache_entries_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "position",
            name=op.f("pk_content_media_cache_entries"),
        ),
        sa.UniqueConstraint(
            "artifact_id",
            name=op.f("uq_content_media_cache_entries_artifact_id"),
        ),
    )


def downgrade() -> None:
    """删除媒体缓存绑定；缓存字节本身仍可由 Artifact housekeeping 清理。"""

    op.drop_table("content_media_cache_entries")
