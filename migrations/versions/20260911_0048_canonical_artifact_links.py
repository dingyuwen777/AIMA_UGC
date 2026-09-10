"""新增 Canonical Artifact 的真实来源父级关系。

Revision ID: 20260911_0048
Revises: 20260910_0047
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0048"
down_revision: str | Sequence[str] | None = "20260910_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建一件 Canonical Artifact 恰好一个真实父级的强关系表。"""

    op.create_table(
        "canonical_artifact_links",
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("processing_import_batch_id", sa.Uuid()),
        sa.Column("historical_import_campaign_item_id", sa.Uuid()),
        sa.Column("collection_scope_id", sa.Uuid()),
        sa.Column("provider_attempt_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(processing_import_batch_id, "
            "historical_import_campaign_item_id, collection_scope_id, "
            "provider_attempt_id) = 1",
            name=op.f("ck_canonical_artifact_links_source_parent_exactly_one"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_canonical_artifact_links_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["processing_import_batch_id"],
            ["processing_import_batches.id"],
            name=op.f(
                "fk_canonical_artifact_links_processing_import_batch_id_processing_import_batches"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["historical_import_campaign_item_id"],
            ["historical_import_campaign_items.id"],
            name=op.f(
                "fk_canonical_artifact_links_historical_import_campaign_item_id_"
                "historical_import_campaign_items"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["collection_scope_id"],
            ["collection_scopes.id"],
            name=op.f("fk_canonical_artifact_links_collection_scope_id_collection_scopes"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f("fk_canonical_artifact_links_provider_attempt_id_provider_request_attempts"),
        ),
        sa.PrimaryKeyConstraint(
            "artifact_id",
            name=op.f("pk_canonical_artifact_links"),
        ),
    )
    op.create_index(
        "ix_canonical_artifact_links_processing_import_batch_id",
        "canonical_artifact_links",
        ["processing_import_batch_id"],
    )
    op.create_index(
        "ix_canonical_artifact_links_historical_import_campaign_item_id",
        "canonical_artifact_links",
        ["historical_import_campaign_item_id"],
    )
    op.create_index(
        "ix_canonical_artifact_links_collection_scope_id",
        "canonical_artifact_links",
        ["collection_scope_id"],
    )
    op.create_index(
        "ix_canonical_artifact_links_provider_attempt_id",
        "canonical_artifact_links",
        ["provider_attempt_id"],
    )


def downgrade() -> None:
    """删除尚未被后续 Runtime 使用的 Canonical Artifact 关系表。"""

    op.drop_table("canonical_artifact_links")
