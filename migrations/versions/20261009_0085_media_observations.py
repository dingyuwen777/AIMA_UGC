"""增加媒体属性观察来源；旧行保持默认空元数据，不扫描历史内容。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261009_0085"
down_revision: str | Sequence[str] | None = "20261009_0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """常量默认值的加列由 PostgreSQL 元数据完成，无业务回填。"""
    op.add_column(
        "content_media",
        sa.Column(
            "observation_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    """回滚仅移除新观察元数据，既有媒体地址与属性保持原值。"""
    op.drop_column("content_media", "observation_metadata")
