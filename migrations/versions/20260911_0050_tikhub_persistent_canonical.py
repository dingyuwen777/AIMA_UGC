"""约束每个 TikHub Search Attempt 唯一 Canonical Artifact。

Revision ID: 20260911_0050
Revises: 20260911_0049
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0050"
down_revision: str | Sequence[str] | None = "20260911_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """拒绝含糊旧关系，再建立 Stage 3 Provider Attempt 唯一父级。"""

    connection = op.get_bind()
    duplicate_attempt = connection.execute(
        sa.text(
            "SELECT provider_attempt_id "
            "FROM canonical_artifact_links "
            "WHERE provider_attempt_id IS NOT NULL "
            "GROUP BY provider_attempt_id HAVING count(*) > 1 LIMIT 1"
        )
    ).scalar_one_or_none()
    if duplicate_attempt is not None:
        raise RuntimeError(
            "存在同一 Provider Attempt 绑定多个 Canonical Artifact；"
            "必须先核对来源并清除含糊关系后才能升级"
        )

    op.create_index(
        "uq_canonical_artifact_links_provider_attempt_id",
        "canonical_artifact_links",
        ["provider_attempt_id"],
        unique=True,
        postgresql_where=sa.text("provider_attempt_id IS NOT NULL"),
    )


def downgrade() -> None:
    """撤销 Stage 3 Provider Attempt 唯一索引，不改 Artifact 事实。"""

    op.drop_index(
        "uq_canonical_artifact_links_provider_attempt_id",
        table_name="canonical_artifact_links",
    )
