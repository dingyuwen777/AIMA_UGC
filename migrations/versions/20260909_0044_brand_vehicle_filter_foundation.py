"""建立品牌目录、车型品牌归属与内容品牌证据基础结构。

Revision ID: 20260909_0044
Revises: 20260908_0043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0044"
down_revision: str | Sequence[str] | None = "20260908_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """以 Expand-only 方式增加品牌与车型过滤所需的数据库基础。"""

    op.create_table(
        "vehicle_brands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(code) > 0",
            name=op.f("ck_vehicle_brands_code_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(display_name) > 0",
            name=op.f("ck_vehicle_brands_display_name_nonempty"),
        ),
        sa.CheckConstraint(
            "role in ('owned','competitor','other')",
            name=op.f("ck_vehicle_brands_role_allowed"),
        ),
        sa.CheckConstraint(
            "status in ('active','deprecated')",
            name=op.f("ck_vehicle_brands_status_allowed"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_vehicle_brands_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version"],
            ["vehicle_catalog_versions.version"],
            name=op.f("fk_vehicle_brands_catalog_version_vehicle_catalog_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicle_brands")),
        sa.UniqueConstraint("code", name=op.f("uq_vehicle_brands_code")),
    )
    op.create_table(
        "vehicle_brand_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(text) > 0",
            name=op.f("ck_vehicle_brand_aliases_text_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(normalized_text) > 0",
            name=op.f("ck_vehicle_brand_aliases_normalized_text_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["vehicle_brands.id"],
            name=op.f("fk_vehicle_brand_aliases_brand_id_vehicle_brands"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicle_brand_aliases")),
        sa.UniqueConstraint(
            "brand_id",
            "normalized_text",
            name=op.f("uq_vehicle_brand_aliases_brand_id_normalized_text"),
        ),
    )

    op.add_column("vehicle_models", sa.Column("brand_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_vehicle_models_brand_id_vehicle_brands"),
        "vehicle_models",
        "vehicle_brands",
        ["brand_id"],
        ["id"],
    )
    op.create_index(
        "ix_vehicle_models_brand_id_status",
        "vehicle_models",
        ["brand_id", "status"],
        unique=False,
    )

    op.create_table(
        "content_brand_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("source_field", sa.Text(), nullable=True),
        sa.Column("derived_vehicle_model_id", sa.Uuid(), nullable=True),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "is_manual_locked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version > 0",
            name=op.f("ck_content_brand_evidence_content_version_positive"),
        ),
        sa.CheckConstraint(
            "source in ('alias_match','vehicle_match','manual_review','import')",
            name=op.f("ck_content_brand_evidence_source_allowed"),
        ),
        sa.CheckConstraint(
            "(source = 'vehicle_match' and derived_vehicle_model_id is not null) or "
            "(source <> 'vehicle_match' and derived_vehicle_model_id is null)",
            name=op.f("ck_content_brand_evidence_derived_vehicle_model_consistent"),
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name=op.f("ck_content_brand_evidence_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["vehicle_brands.id"],
            name=op.f("fk_content_brand_evidence_brand_id_vehicle_brands"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version"],
            ["vehicle_catalog_versions.version"],
            name=op.f("fk_content_brand_evidence_catalog_version_vehicle_catalog_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_brand_evidence_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["derived_vehicle_model_id"],
            ["vehicle_models.id"],
            name=op.f(
                "fk_content_brand_evidence_derived_vehicle_model_id_vehicle_models"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_brand_evidence")),
    )
    op.create_index(
        "uq_content_brand_evidence_direct_identity",
        "content_brand_evidence",
        ["content_id", "content_version", "brand_id", "source", "catalog_version"],
        unique=True,
        postgresql_where=sa.text("derived_vehicle_model_id is null"),
    )
    op.create_index(
        "uq_content_brand_evidence_vehicle_identity",
        "content_brand_evidence",
        [
            "content_id",
            "content_version",
            "brand_id",
            "source",
            "derived_vehicle_model_id",
            "catalog_version",
        ],
        unique=True,
        postgresql_where=sa.text("derived_vehicle_model_id is not null"),
    )
    op.create_index(
        "ix_content_brand_evidence_active_content",
        "content_brand_evidence",
        ["content_id", "content_version", "brand_id"],
        unique=False,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_content_brand_evidence_active_brand",
        "content_brand_evidence",
        ["brand_id", "content_id"],
        unique=False,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "content_brand_review_locks",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version > 0",
            name=op.f("ck_content_brand_review_locks_content_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(actor_ref) > 0",
            name=op.f("ck_content_brand_review_locks_actor_ref_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_brand_review_locks_content_id_contents"),
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "content_version",
            name=op.f("pk_content_brand_review_locks"),
        ),
    )


def downgrade() -> None:
    """按依赖逆序移除 Stage 1 新增结构，不触碰既有车型与旧筛选表。"""

    op.drop_table("content_brand_review_locks")
    op.drop_index(
        "ix_content_brand_evidence_active_brand",
        table_name="content_brand_evidence",
    )
    op.drop_index(
        "ix_content_brand_evidence_active_content",
        table_name="content_brand_evidence",
    )
    op.drop_index(
        "uq_content_brand_evidence_vehicle_identity",
        table_name="content_brand_evidence",
    )
    op.drop_index(
        "uq_content_brand_evidence_direct_identity",
        table_name="content_brand_evidence",
    )
    op.drop_table("content_brand_evidence")
    op.drop_index("ix_vehicle_models_brand_id_status", table_name="vehicle_models")
    op.drop_constraint(
        op.f("fk_vehicle_models_brand_id_vehicle_brands"),
        "vehicle_models",
        type_="foreignkey",
    )
    op.drop_column("vehicle_models", "brand_id")
    op.drop_table("vehicle_brand_aliases")
    op.drop_table("vehicle_brands")
