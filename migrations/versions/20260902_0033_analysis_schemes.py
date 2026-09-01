"""建立原子 Analysis Scheme，并允许 Run 冻结 Scheme 快照。

Revision ID: 20260902_0033
Revises: 20260902_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0033"
down_revision: str | Sequence[str] | None = "20260902_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_schemes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active_version_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(name) > 0", name=op.f("ck_analysis_schemes_name_nonempty")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_schemes")),
        sa.UniqueConstraint("name", name=op.f("uq_analysis_schemes_name")),
    )
    op.create_index(
        "uq_analysis_schemes_single_active",
        "analysis_schemes",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "analysis_scheme_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheme_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("compiled_prompt", sa.Text(), nullable=False),
        sa.Column("prompt_sha256", sa.Text(), nullable=False),
        sa.Column("taxonomy_sha256", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_analysis_scheme_versions_version_positive")
        ),
        sa.CheckConstraint(
            "status in ('draft','published','retired')",
            name=op.f("ck_analysis_scheme_versions_status_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(definition) = 'object'",
            name=op.f("ck_analysis_scheme_versions_definition_object"),
        ),
        sa.CheckConstraint(
            "char_length(compiled_prompt) > 0",
            name=op.f("ck_analysis_scheme_versions_compiled_prompt_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(created_by) > 0",
            name=op.f("ck_analysis_scheme_versions_created_by_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["scheme_id"],
            ["analysis_schemes.id"],
            name=op.f("fk_analysis_scheme_versions_scheme_id_analysis_schemes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_scheme_versions")),
        sa.UniqueConstraint(
            "scheme_id", "version", name=op.f("uq_analysis_scheme_versions_scheme_id_version")
        ),
    )
    op.create_foreign_key(
        op.f("fk_analysis_schemes_active_version_id_analysis_scheme_versions"),
        "analysis_schemes",
        "analysis_scheme_versions",
        ["active_version_id"],
        ["id"],
    )
    op.add_column(
        "analysis_content_runs", sa.Column("analysis_scheme_version_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "analysis_content_runs", sa.Column("prompt_text_snapshot", sa.Text(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_analysis_content_runs_analysis_scheme_version_id_analysis_scheme_versions"),
        "analysis_content_runs",
        "analysis_scheme_versions",
        ["analysis_scheme_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_analysis_content_runs_analysis_scheme_version_id_analysis_scheme_versions"),
        "analysis_content_runs",
        type_="foreignkey",
    )
    op.drop_column("analysis_content_runs", "prompt_text_snapshot")
    op.drop_column("analysis_content_runs", "analysis_scheme_version_id")
    op.drop_constraint(
        op.f("fk_analysis_schemes_active_version_id_analysis_scheme_versions"),
        "analysis_schemes",
        type_="foreignkey",
    )
    op.drop_table("analysis_scheme_versions")
    op.drop_index("uq_analysis_schemes_single_active", table_name="analysis_schemes")
    op.drop_table("analysis_schemes")
