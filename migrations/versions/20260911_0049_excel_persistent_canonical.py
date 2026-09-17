"""切换 Excel Stage 2 Pure Canonical，并约束每个父级唯一 Artifact。

Revision ID: 20260911_0049
Revises: 20260911_0048
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0049"
down_revision: str | Sequence[str] | None = "20260911_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """先拒绝旧活跃 Chunk/Job，再建立 Stage 2 父级唯一关系。"""

    connection = op.get_bind()
    active_legacy_jobs = connection.execute(
        sa.text(
            "SELECT count(*) FROM jobs "
            "WHERE job_type = 'ingestion.historical-import-chunk.v1' "
            "AND status IN ('queued', 'running')"
        )
    ).scalar_one()
    if active_legacy_jobs:
        raise RuntimeError(
            "存在活跃 ingestion.historical-import-chunk.v1 Job；"
            "停止旧 Worker 并完成或取消任务后才能升级"
        )

    retryable_legacy_chunks = connection.execute(
        sa.text(
            "SELECT count(*) "
            "FROM historical_import_campaign_items item "
            "JOIN artifacts artifact ON artifact.id = item.artifact_id "
            "WHERE item.item_kind = 'chunk' "
            "AND artifact.kind = 'historical-import.chunk' "
            "AND item.status NOT IN ('succeeded', 'cancelled')"
        )
    ).scalar_one()
    if retryable_legacy_chunks:
        raise RuntimeError(
            "存在仍可执行或重试的旧 Historical Chunk；"
            "本版本按已批准的干净切换失败关闭，不会把旧 outcome 格式误作 Canonical"
        )

    op.create_index(
        "uq_canonical_artifact_links_processing_import_batch_id",
        "canonical_artifact_links",
        ["processing_import_batch_id"],
        unique=True,
        postgresql_where=sa.text("processing_import_batch_id IS NOT NULL"),
    )
    op.create_index(
        "uq_canonical_artifact_links_historical_import_campaign_item_id",
        "canonical_artifact_links",
        ["historical_import_campaign_item_id"],
        unique=True,
        postgresql_where=sa.text("historical_import_campaign_item_id IS NOT NULL"),
    )


def downgrade() -> None:
    """只撤销唯一索引；终端旧审计事实从未被重写。"""

    op.drop_index(
        "uq_canonical_artifact_links_historical_import_campaign_item_id",
        table_name="canonical_artifact_links",
    )
    op.drop_index(
        "uq_canonical_artifact_links_processing_import_batch_id",
        table_name="canonical_artifact_links",
    )
