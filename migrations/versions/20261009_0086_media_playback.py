"""增加媒体播放准备状态，不扫描历史内容或保存视频二进制。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_0086"
down_revision: str | Sequence[str] | None = "20261009_0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """空状态表按用户播放请求惰性建立。"""
    op.create_table(
        "content_media_playback_states",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("identity_token", sa.Text(), nullable=False),
        sa.Column("source_revision", sa.Text(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id")),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("collection_runs.id")),
        sa.Column("obtained_at", sa.DateTime(timezone=True)),
        sa.Column("explicit_expires_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.Text()),
        sa.Column("failure_source_revision", sa.Text()),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("content_id", "position"),
        sa.ForeignKeyConstraint(
            ["content_id", "position"],
            ["content_media.content_id", "content_media.position"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("generation >= 0", name="generation_nonnegative"),
        sa.CheckConstraint("state in ('ready','preparing','unavailable')", name="state_allowed"),
    )


def downgrade() -> None:
    """先停 API/Worker 再移除状态表；不能据此降级解释已经产生的 v2 来源贡献。"""
    op.drop_table("content_media_playback_states")
