"""删除已退出生产链的旧搜索与车型过滤配置。

Revision ID: 20260910_0047
Revises: 20260910_0046
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0047"
down_revision: str | Sequence[str] | None = "20260910_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_TABLES = (
    "keyword_pack_vehicle_models",
    "collection_plan_vehicle_models",
    "global_relevance_config",
)


def upgrade() -> None:
    """只在旧数据与旧执行版本均为空时删除 Legacy Schema。"""

    connection = op.get_bind()
    for table_name in _LEGACY_TABLES:
        count = connection.scalar(sa.text(f'SELECT count(*) FROM "{table_name}"'))
        if int(count or 0) > 0:
            raise RuntimeError(
                f"Stage 7 Cleanup 拒绝删除非空 Legacy 表 {table_name}；"
                "当前批准前提是尚未导入任何旧业务数据"
            )

    legacy_import_jobs = connection.scalar(
        sa.text("SELECT count(*) FROM jobs WHERE job_type = 'ingestion.import-excel.v1'")
    )
    if int(legacy_import_jobs or 0) > 0:
        raise RuntimeError("Stage 7 Cleanup 发现旧 ingestion.import-excel.v1 Job，拒绝继续")

    legacy_import_batches = connection.scalar(
        sa.text("SELECT count(*) FROM processing_import_batches WHERE stats ? 'keyword_selection'")
    )
    if int(legacy_import_batches or 0) > 0:
        raise RuntimeError("Stage 7 Cleanup 发现旧 Import Batch Snapshot，拒绝继续")

    legacy_collection_runs = connection.scalar(
        sa.text(
            "SELECT count(*) FROM collection_runs "
            "WHERE coalesce(config_snapshot ->> 'schema_version', '') "
            "<> 'collection-run-config.v2'"
        )
    )
    if int(legacy_collection_runs or 0) > 0:
        raise RuntimeError("Stage 7 Cleanup 发现旧 Collection Run Snapshot，拒绝继续")

    legacy_import_campaigns = connection.scalar(
        sa.text(
            "SELECT count(*) FROM historical_import_campaigns "
            "WHERE coalesce(keyword_pack_snapshot ->> 'schema_version', '') "
            "<> 'brand-vehicle-filter.v1'"
        )
    )
    if int(legacy_import_campaigns or 0) > 0:
        raise RuntimeError("Stage 7 Cleanup 发现旧 Data Import Campaign Snapshot，拒绝继续")

    unresolved_active_vehicles = connection.scalar(
        sa.text(
            "SELECT count(*) FROM vehicle_models AS vehicle "
            "LEFT JOIN vehicle_brands AS brand ON brand.id = vehicle.brand_id "
            "WHERE vehicle.status = 'active' "
            "AND (vehicle.brand_id IS NULL OR brand.id IS NULL OR brand.status <> 'active')"
        )
    )
    if int(unresolved_active_vehicles or 0) > 0:
        raise RuntimeError("Stage 7 Cleanup 发现缺少有效 Brand Ownership 的 active 车型，拒绝继续")

    op.drop_table("keyword_pack_vehicle_models")
    op.drop_table("collection_plan_vehicle_models")
    op.drop_table("global_relevance_config")


def downgrade() -> None:
    """恢复旧应用回滚所需的三张空表结构。"""

    op.create_table(
        "global_relevance_config",
        sa.Column("singleton_key", sa.Text(), nullable=False),
        sa.Column("keyword_pack_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "singleton_key = 'global'",
            name=op.f("ck_global_relevance_config_singleton_key_global"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_global_relevance_config_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["keyword_pack_id"],
            ["keyword_packs.id"],
            name=op.f("fk_global_relevance_config_keyword_pack_id_keyword_packs"),
        ),
        sa.PrimaryKeyConstraint("singleton_key", name=op.f("pk_global_relevance_config")),
    )
    op.create_table(
        "collection_plan_vehicle_models",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_model_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["collection_plans.id"],
            name=op.f("fk_collection_plan_vehicle_models_plan_id_collection_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_model_id"],
            ["vehicle_models.id"],
            name=op.f("fk_collection_plan_vehicle_models_vehicle_model_id_vehicle_models"),
        ),
        sa.PrimaryKeyConstraint(
            "plan_id", "vehicle_model_id", name=op.f("pk_collection_plan_vehicle_models")
        ),
    )
    op.create_table(
        "keyword_pack_vehicle_models",
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_model_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["keyword_packs.id"],
            name=op.f("fk_keyword_pack_vehicle_models_pack_id_keyword_packs"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_model_id"],
            ["vehicle_models.id"],
            name=op.f("fk_keyword_pack_vehicle_models_vehicle_model_id_vehicle_models"),
        ),
        sa.PrimaryKeyConstraint(
            "pack_id", "vehicle_model_id", name=op.f("pk_keyword_pack_vehicle_models")
        ),
    )
