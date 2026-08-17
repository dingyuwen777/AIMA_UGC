"""为 Content Current 增加字段级 Observation freshness。

Revision ID: 20260817_0017
Revises: 20260817_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0017"
down_revision: str | Sequence[str] | None = "20260817_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加内部字段 freshness map，并为既有非空 Current 做保守初始化。"""
    for table_name in ("accounts", "contents", "comments"):
        op.add_column(
            table_name,
            sa.Column(
                "field_observed_at",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
        op.create_check_constraint(
            op.f(f"ck_{table_name}_field_observed_at_object"),
            table_name,
            "jsonb_typeof(field_observed_at) = 'object'",
        )

    # 历史行没有完整 observed_fields provenance。这里只为当前明确非空值建立
    # last_seen_at freshness，避免迁移后旧 Observation 回滚已有 Current；当前为
    # NULL 的字段不伪造“曾被明确观察为 null”，允许后续 Raw replay 补充缺失事实。
    op.execute(
        """
        UPDATE accounts
        SET field_observed_at = jsonb_strip_nulls(jsonb_build_object(
          'author.handle', CASE WHEN handle IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.display_name', CASE WHEN display_name IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.profile_url', CASE WHEN profile_url IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.avatar_url', CASE WHEN avatar_url IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.bio', CASE WHEN bio IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.verified', CASE WHEN verified IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.verification_label', CASE WHEN verification_label IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.region', CASE WHEN region IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.follower_count', CASE WHEN current_follower_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.following_count', CASE WHEN current_following_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.content_count', CASE WHEN current_content_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.total_like_count', CASE WHEN current_total_like_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END
        ))
        """
    )
    op.execute(
        """
        UPDATE contents
        SET field_observed_at = jsonb_strip_nulls(jsonb_build_object(
          'content_type', to_jsonb(last_seen_at::text),
          'title', CASE WHEN title IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'text', CASE WHEN text IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'canonical_url', CASE WHEN canonical_url IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'share_url', CASE WHEN share_url IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.external_account_id', CASE WHEN author_account_id IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'published_at', CASE WHEN published_at IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'source_updated_at', CASE WHEN source_updated_at IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'status', CASE WHEN status IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.like_count', CASE WHEN current_like_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.comment_count', CASE WHEN current_comment_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.share_count', CASE WHEN current_share_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.repost_count', CASE WHEN current_repost_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.favorite_count', CASE WHEN current_favorite_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.view_count', CASE WHEN current_view_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.play_count', CASE WHEN current_play_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.danmaku_count', CASE WHEN current_danmaku_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.coin_count', CASE WHEN current_coin_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.download_count', CASE WHEN current_download_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END
        ))
        """
    )
    op.execute(
        """
        UPDATE comments
        SET field_observed_at = jsonb_strip_nulls(jsonb_build_object(
          'root_comment_id', CASE WHEN root_comment_id IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'parent_comment_id', CASE WHEN parent_comment_id IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'author.external_account_id', CASE WHEN author_account_id IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'text', CASE WHEN text IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'published_at', CASE WHEN published_at IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'source_updated_at', CASE WHEN source_updated_at IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'status', CASE WHEN status IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'is_by_content_author', CASE WHEN is_by_content_author IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.like_count', CASE WHEN current_like_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END,
          'metrics.reply_count', CASE WHEN current_reply_count IS NOT NULL THEN to_jsonb(last_seen_at::text) END
        ))
        """
    )


def downgrade() -> None:
    """移除内部 freshness provenance，不删除任何业务 Current 值。"""
    for table_name in ("comments", "contents", "accounts"):
        op.drop_constraint(
            op.f(f"ck_{table_name}_field_observed_at_object"),
            table_name,
            type_="check",
        )
        op.drop_column(table_name, "field_observed_at")
