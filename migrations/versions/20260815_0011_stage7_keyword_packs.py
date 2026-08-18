"""建立 Stage 7 关键词与词包稳定父事实。

Revision ID: 20260815_0011
Revises: 20260815_0010
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260815_0011"
down_revision: str | Sequence[str] | None = "20260815_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "keyword_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_packs")),
        sa.UniqueConstraint("name", name=op.f("uq_keyword_packs_name")),
        sa.CheckConstraint(
            "char_length(name) > 0",
            name=op.f("ck_keyword_packs_name_nonempty"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_keyword_packs_version_positive"),
        ),
    )
    op.create_table(
        "keywords",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keywords")),
        sa.UniqueConstraint(
            "normalized_text",
            name=op.f("uq_keywords_normalized_text"),
        ),
        sa.CheckConstraint(
            "char_length(text) > 0",
            name=op.f("ck_keywords_text_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(normalized_text) > 0",
            name=op.f("ck_keywords_normalized_text_nonempty"),
        ),
    )
    op.create_table(
        "keyword_pack_items",
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("keyword_id", sa.Uuid(), nullable=False),
        sa.Column("operations", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("note", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.ForeignKeyConstraint(
            ["keyword_id"],
            ["keywords.id"],
            name=op.f("fk_keyword_pack_items_keyword_id_keywords"),
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["keyword_packs.id"],
            name=op.f("fk_keyword_pack_items_pack_id_keyword_packs"),
        ),
        sa.PrimaryKeyConstraint(
            "pack_id",
            "keyword_id",
            "operations",
            name=op.f("pk_keyword_pack_items"),
        ),
        sa.CheckConstraint(
            "char_length(operations) > 0",
            name=op.f("ck_keyword_pack_items_platform_nonempty"),
        ),
    )


def downgrade() -> None:
    op.drop_table("keyword_pack_items")
    op.drop_table("keywords")
    op.drop_table("keyword_packs")
