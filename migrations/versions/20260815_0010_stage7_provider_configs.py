"""建立 Stage 7 Provider Config 稳定父事实。

Revision ID: 20260815_0010
Revises: 20260814_0009
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260815_0010"
down_revision: str | Sequence[str] | None = "20260814_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_configs")),
        sa.CheckConstraint(
            "char_length(provider) > 0",
            name=op.f("ck_provider_configs_provider_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(display_name) > 0",
            name=op.f("ck_provider_configs_display_name_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(base_url) > 0",
            name=op.f("ck_provider_configs_base_url_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(secret_ref) > 0",
            name=op.f("ck_provider_configs_secret_ref_nonempty"),
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_configs")
