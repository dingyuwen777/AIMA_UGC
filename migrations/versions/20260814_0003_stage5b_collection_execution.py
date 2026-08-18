"""建立 Stage 5B Collection Run/Scope 父事实。

Revision ID: 20260814_0003
Revises: 20260814_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0003"
down_revision: str | Sequence[str] | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("config_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("requested_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("content_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_collection_runs_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_runs")),
        sa.UniqueConstraint("job_id", name=op.f("uq_collection_runs_job_id")),
        sa.CheckConstraint(
            "trigger_type in ('manual','api','backfill')",
            name=op.f("ck_collection_runs_trigger_type_allowed"),
        ),
        sa.CheckConstraint(
            "status in ('queued','running','partial_success','succeeded','failed','cancelled')",
            name=op.f("ck_collection_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "requested_count >= 0 and succeeded_count >= 0 and failed_count >= 0 "
            "and content_count >= 0 and comment_count >= 0",
            name=op.f("ck_collection_runs_counts_nonnegative"),
        ),
    )
    op.create_index(
        "ix_collection_runs_status_created_at",
        "collection_runs",
        ["status", sa.text("created_at DESC")],
    )

    op.create_table(
        "collection_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("operations", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=False),
        sa.Column("operation_group", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "pagination_state",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("stop_reason", sa.Text()),
        sa.Column(
            "stats",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["collection_runs.id"],
            name=op.f("fk_collection_scopes_run_id_collection_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_scopes")),
        sa.UniqueConstraint(
            "run_id",
            "operations",
            "source_type",
            "source_value",
            "operation_group",
            name=op.f(
                "uq_collection_scopes_run_id_platform_source_type_source_value_operation_group"
            ),
        ),
    )
    op.create_index(
        "ix_collection_scopes_run_id_status",
        "collection_scopes",
        ["run_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_scopes_run_id_status", table_name="collection_scopes")
    op.drop_table("collection_scopes")
    op.drop_index("ix_collection_runs_status_created_at", table_name="collection_runs")
    op.drop_table("collection_runs")
