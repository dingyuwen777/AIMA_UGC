"""修复 Stage 12 开发期 0026 草稿遗留的 Schema 对象名和索引。

Revision ID: 20260827_0029
Revises: 20260827_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "20260827_0029"
down_revision: str | Sequence[str] | None = "20260827_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_REPAIRS = (
    (
        "historical_import_campaigns",
        "ck_historical_import_campaigns_discovered_file_count_no_c356",
        "ck_historical_import_campaigns_discovered_files_nonnegative",
        "ALTER TABLE historical_import_campaigns RENAME CONSTRAINT "
        "ck_historical_import_campaigns_discovered_file_count_no_c356 TO "
        "ck_historical_import_campaigns_discovered_files_nonnegative",
    ),
    (
        "processing_import_batch_identities",
        "ck_processing_import_batch_identities_first_row_ordinal_abf7",
        "ck_processing_import_batch_identities_first_row_positive",
        "ALTER TABLE processing_import_batch_identities RENAME CONSTRAINT "
        "ck_processing_import_batch_identities_first_row_ordinal_abf7 TO "
        "ck_processing_import_batch_identities_first_row_positive",
    ),
    (
        "processing_import_batch_item_conflicts",
        "ck_processing_import_batch_item_conflicts_content_versi_bd36",
        "ck_processing_import_batch_item_conflicts_version_positive",
        "ALTER TABLE processing_import_batch_item_conflicts RENAME CONSTRAINT "
        "ck_processing_import_batch_item_conflicts_content_versi_bd36 TO "
        "ck_processing_import_batch_item_conflicts_version_positive",
    ),
    (
        "processing_import_batch_item_conflicts",
        "ck_processing_import_batch_item_conflicts_historical_ha_1c30",
        "ck_processing_import_batch_item_conflicts_history_hash_sha256",
        "ALTER TABLE processing_import_batch_item_conflicts RENAME CONSTRAINT "
        "ck_processing_import_batch_item_conflicts_historical_ha_1c30 TO "
        "ck_processing_import_batch_item_conflicts_history_hash_sha256",
    ),
    (
        "processing_import_batch_items",
        "ck_processing_import_batch_items_external_content_id_ha_5e82",
        "ck_processing_import_batch_items_external_id_hash_sha256",
        "ALTER TABLE processing_import_batch_items RENAME CONSTRAINT "
        "ck_processing_import_batch_items_external_content_id_ha_5e82 TO "
        "ck_processing_import_batch_items_external_id_hash_sha256",
    ),
)


def _constraint_exists(connection: Connection, *, table_name: str, name: str) -> bool:
    return bool(
        connection.scalar(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_constraint "
                "WHERE conrelid = to_regclass(:table_name) AND conname = :name)"
            ),
            {"table_name": table_name, "name": name},
        )
    )


def upgrade() -> None:
    connection = op.get_bind()
    for table_name, legacy_name, canonical_name, rename_sql in _CONSTRAINT_REPAIRS:
        legacy_exists = _constraint_exists(
            connection,
            table_name=table_name,
            name=legacy_name,
        )
        canonical_exists = _constraint_exists(
            connection,
            table_name=table_name,
            name=canonical_name,
        )
        if legacy_exists and canonical_exists:
            raise RuntimeError(
                f"{table_name} 同时存在旧约束 {legacy_name} 和正式约束 {canonical_name}"
            )
        if legacy_exists:
            op.execute(rename_sql)
        elif not canonical_exists:
            raise RuntimeError(f"{table_name} 缺少 Stage 12 约束 {canonical_name}")

    op.create_index(
        "uq_historical_import_campaign_items_source_manifest",
        "historical_import_campaign_items",
        ["campaign_id", "relative_path", "manifest_identity"],
        unique=True,
        postgresql_where=sa.text("item_kind = 'source_file'"),
        if_not_exists=True,
    )


def downgrade() -> None:
    """0029 只把实际 Schema 收敛到 0028 的正式定义，降级无需反向制造漂移。"""
