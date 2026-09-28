"""新增工作台聚合快照与声音广场数据修订序列。

Revision ID: 20260928_0073
Revises: 20260928_0072
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260928_0073"
down_revision: str | Sequence[str] | None = "20260928_0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE workbench_data_revision_seq START WITH 1"))
    # 先占用初始值，保证第一次投影写入把可观察 revision 从 1 推进到 2。
    op.execute(sa.text("SELECT nextval('workbench_data_revision_seq')"))
    op.create_table(
        "workbench_snapshots",
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.Text(), nullable=False),
        sa.Column("query", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("analysis_scheme_version_id", sa.Uuid()),
        sa.Column("target_analysis_scheme_version_id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_sha256", sa.Text()),
        sa.Column("source_revision", sa.BigInteger()),
        sa.Column("target_revision", sa.BigInteger(), nullable=False),
        sa.Column("refresh_generation", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("computed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "module in ('mind','trend')", name=op.f("ck_workbench_snapshots_module_allowed")
        ),
        sa.CheckConstraint(
            "char_length(query_hash) = 64", name=op.f("ck_workbench_snapshots_query_hash_length")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(query) = 'object'", name=op.f("ck_workbench_snapshots_query_object")
        ),
        sa.CheckConstraint(
            "taxonomy_sha256 is null or char_length(taxonomy_sha256) = 64",
            name=op.f("ck_workbench_snapshots_taxonomy_hash_length"),
        ),
        sa.CheckConstraint(
            "source_revision is null or source_revision > 0",
            name=op.f("ck_workbench_snapshots_source_revision_positive"),
        ),
        sa.CheckConstraint(
            "target_revision > 0", name=op.f("ck_workbench_snapshots_target_revision_positive")
        ),
        sa.CheckConstraint(
            "refresh_generation > 0",
            name=op.f("ck_workbench_snapshots_refresh_generation_positive"),
        ),
        sa.CheckConstraint(
            "status in ('refreshing','ready','failed')",
            name=op.f("ck_workbench_snapshots_status_allowed"),
        ),
        sa.CheckConstraint(
            "response is null or jsonb_typeof(response) = 'object'",
            name=op.f("ck_workbench_snapshots_response_object"),
        ),
        sa.CheckConstraint(
            "(response is null) = (computed_at is null)",
            name=op.f("ck_workbench_snapshots_response_computed_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_scheme_version_id"],
            ["analysis_scheme_versions.id"],
            name=op.f("fk_workbench_snapshots_analysis_scheme_version_id_analysis_scheme_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_analysis_scheme_version_id"],
            ["analysis_scheme_versions.id"],
            name=op.f(
                "fk_workbench_snapshots_target_analysis_scheme_version_id_analysis_scheme_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("module", "query_hash", name=op.f("pk_workbench_snapshots")),
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION workbench_bump_data_revision()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM nextval('workbench_data_revision_seq');
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_workbench_projection_revision
            AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON voice_plaza_content_projection
            FOR EACH STATEMENT EXECUTE FUNCTION workbench_bump_data_revision()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_workbench_projection_revision "
            "ON voice_plaza_content_projection"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS workbench_bump_data_revision()"))
    op.drop_table("workbench_snapshots")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS workbench_data_revision_seq"))
