"""补齐车型删除资格与合并引用检查索引。

Revision ID: 20260922_0057
Revises: 20260921_0056
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0057"
down_revision: str | Sequence[str] | None = "20260921_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为任意历史车型证据和非空合并目标建立反查索引。"""

    op.create_index(
        "ix_content_vehicle_evidence_vehicle_model_id",
        "content_vehicle_evidence",
        ["vehicle_model_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_models_merged_into_id",
        "vehicle_models",
        ["merged_into_id"],
        unique=False,
        postgresql_where=sa.text("merged_into_id IS NOT NULL"),
    )


def downgrade() -> None:
    """删除本次新增索引，不改写车型或历史证据。"""

    op.drop_index("ix_vehicle_models_merged_into_id", table_name="vehicle_models")
    op.drop_index(
        "ix_content_vehicle_evidence_vehicle_model_id",
        table_name="content_vehicle_evidence",
    )
