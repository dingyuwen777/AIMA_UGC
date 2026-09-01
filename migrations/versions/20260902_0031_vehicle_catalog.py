"""建立车型目录、别名、词包引用与计划车型选择。

Revision ID: 20260902_0031
Revises: 20260828_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0031"
down_revision: str | Sequence[str] | None = "20260828_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_catalog_versions",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_vehicle_catalog_versions_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(reason) > 0", name=op.f("ck_vehicle_catalog_versions_reason_nonempty")
        ),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_vehicle_catalog_versions")),
    )
    op.execute(
        sa.text(
            "INSERT INTO vehicle_catalog_versions (version, reason, actor_ref, created_at) "
            "VALUES (1, 'initial_catalog', 'system:migration', CURRENT_TIMESTAMP)"
        )
    )
    op.create_table(
        "vehicle_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("merged_into_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(code) > 0", name=op.f("ck_vehicle_models_code_nonempty")),
        sa.CheckConstraint(
            "char_length(display_name) > 0",
            name=op.f("ck_vehicle_models_display_name_nonempty"),
        ),
        sa.CheckConstraint(
            "status in ('active','deprecated','merged')",
            name=op.f("ck_vehicle_models_status_allowed"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_vehicle_models_version_positive")),
        sa.CheckConstraint(
            "(status = 'merged' and merged_into_id is not null) or "
            "(status <> 'merged' and merged_into_id is null)",
            name=op.f("ck_vehicle_models_merged_target_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version"],
            ["vehicle_catalog_versions.version"],
            name=op.f("fk_vehicle_models_catalog_version_vehicle_catalog_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["vehicle_models.id"],
            name=op.f("fk_vehicle_models_merged_into_id_vehicle_models"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicle_models")),
        sa.UniqueConstraint("code", name=op.f("uq_vehicle_models_code")),
    )
    op.create_table(
        "vehicle_model_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_model_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(text) > 0", name=op.f("ck_vehicle_model_aliases_text_nonempty")
        ),
        sa.CheckConstraint(
            "char_length(normalized_text) > 0",
            name=op.f("ck_vehicle_model_aliases_normalized_text_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_model_id"],
            ["vehicle_models.id"],
            name=op.f("fk_vehicle_model_aliases_vehicle_model_id_vehicle_models"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicle_model_aliases")),
        sa.UniqueConstraint(
            "vehicle_model_id",
            "normalized_text",
            name=op.f("uq_vehicle_model_aliases_vehicle_model_id_normalized_text"),
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


def downgrade() -> None:
    op.drop_table("collection_plan_vehicle_models")
    op.drop_table("keyword_pack_vehicle_models")
    op.drop_table("vehicle_model_aliases")
    op.drop_table("vehicle_models")
    op.drop_table("vehicle_catalog_versions")
