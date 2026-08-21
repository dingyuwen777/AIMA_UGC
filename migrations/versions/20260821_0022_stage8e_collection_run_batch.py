"""关联 Stage 8E Collection Run 与 Import Batch。

Revision ID: 20260821_0022
Revises: 20260821_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0022"
down_revision: str | Sequence[str] | None = "20260821_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_runs",
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_collection_runs_import_batch_id_processing_import_batches"),
        "collection_runs",
        "processing_import_batches",
        ["import_batch_id"],
        ["id"],
    )
    op.create_index(
        "ix_collection_runs_import_batch_id_created_at",
        "collection_runs",
        ["import_batch_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_collection_runs_import_batch_id_created_at",
        table_name="collection_runs",
    )
    op.drop_constraint(
        op.f("fk_collection_runs_import_batch_id_processing_import_batches"),
        "collection_runs",
        type_="foreignkey",
    )
    op.drop_column("collection_runs", "import_batch_id")
