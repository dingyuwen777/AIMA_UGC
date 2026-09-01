"""建立内容车型追加式证据。

Revision ID: 20260902_0032
Revises: 20260902_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0032"
down_revision: str | Sequence[str] | None = "20260902_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_vehicle_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("vehicle_model_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("source_field", sa.Text(), nullable=True),
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
            name=op.f("ck_content_vehicle_evidence_content_version_positive"),
        ),
        sa.CheckConstraint(
            "source in ('alias_match','ai_candidate','manual_review','import')",
            name=op.f("ck_content_vehicle_evidence_source_allowed"),
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name=op.f("ck_content_vehicle_evidence_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version"],
            ["vehicle_catalog_versions.version"],
            name=op.f("fk_content_vehicle_evidence_catalog_version_vehicle_catalog_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_vehicle_evidence_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_model_id"],
            ["vehicle_models.id"],
            name=op.f("fk_content_vehicle_evidence_vehicle_model_id_vehicle_models"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_vehicle_evidence")),
        sa.UniqueConstraint(
            "content_id",
            "content_version",
            "vehicle_model_id",
            "source",
            "catalog_version",
            name="uq_content_vehicle_evidence_identity",
        ),
    )
    op.create_index(
        "ix_content_vehicle_evidence_active_vehicle",
        "content_vehicle_evidence",
        ["vehicle_model_id", "content_id"],
        unique=False,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "content_vehicle_review_locks",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version > 0",
            name=op.f("ck_content_vehicle_review_locks_content_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(actor_ref) > 0",
            name=op.f("ck_content_vehicle_review_locks_actor_ref_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_vehicle_review_locks_content_id_contents"),
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "content_version",
            name=op.f("pk_content_vehicle_review_locks"),
        ),
    )


def downgrade() -> None:
    op.drop_table("content_vehicle_review_locks")
    op.drop_index(
        "ix_content_vehicle_evidence_active_vehicle",
        table_name="content_vehicle_evidence",
    )
    op.drop_table("content_vehicle_evidence")
