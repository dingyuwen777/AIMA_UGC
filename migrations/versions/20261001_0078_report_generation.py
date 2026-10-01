"""数据库报告快照与产物

Revision ID: 20261001_0078
Revises: 20260930_0077
Create Date: 2026-10-01 11:43:24.557615
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261001_0078"
down_revision: str | Sequence[str] | None = "20260930_0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立报告父事实、冻结数据和Artifact关联，不修改已有业务表。"""
    op.create_table(
        "reporting_report_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_model_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("publication_job_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "publication_checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(publication_checkpoint) = 'object'",
            name=op.f("ck_reporting_report_runs_checkpoint_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(snapshot) = 'object'",
            name=op.f("ck_reporting_report_runs_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(vehicle_model_ids) = 'array'",
            name=op.f("ck_reporting_report_runs_vehicles_array"),
        ),
        sa.CheckConstraint(
            "(completed_at IS NULL) = (expires_at IS NULL)",
            name=op.f("ck_reporting_report_runs_completion_consistent"),
        ),
        sa.CheckConstraint(
            "start_date <= end_date", name=op.f("ck_reporting_report_runs_date_order")
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["vehicle_brands.id"],
            name=op.f("fk_reporting_report_runs_brand_id_vehicle_brands"),
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id"],
            ["jobs.id"],
            name=op.f("fk_reporting_report_runs_generation_job_id_jobs"),
        ),
        sa.ForeignKeyConstraint(
            ["publication_job_id"],
            ["jobs.id"],
            name=op.f("fk_reporting_report_runs_publication_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reporting_report_runs")),
        sa.UniqueConstraint(
            "generation_job_id", name=op.f("uq_reporting_report_runs_generation_job_id")
        ),
        sa.UniqueConstraint(
            "publication_job_id", name=op.f("uq_reporting_report_runs_publication_job_id")
        ),
        info={"owner": "reporting"},
    )
    op.create_index(
        "ix_reporting_report_runs_created_at", "reporting_report_runs", ["created_at"], unique=False
    )
    op.create_table(
        "reporting_report_artifacts",
        sa.Column("report_run_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_reporting_report_artifacts_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["report_run_id"],
            ["reporting_report_runs.id"],
            name=op.f("fk_reporting_report_artifacts_report_run_id_reporting_report_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "report_run_id", "artifact_id", name=op.f("pk_reporting_report_artifacts")
        ),
        sa.UniqueConstraint(
            "report_run_id",
            "filename",
            name=op.f("uq_reporting_report_artifacts_report_run_id_filename"),
        ),
        info={"owner": "reporting"},
    )
    op.create_table(
        "reporting_report_items",
        sa.Column("report_run_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("analysis_basis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(data) = 'object'", name=op.f("ck_reporting_report_items_data_object")
        ),
        sa.CheckConstraint(
            "period IN ('current', 'previous')",
            name=op.f("ck_reporting_report_items_period_allowed"),
        ),
        sa.CheckConstraint(
            "content_version > 0 AND ordinal >= 0",
            name=op.f("ck_reporting_report_items_position_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_reporting_report_items_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["report_run_id"],
            ["reporting_report_runs.id"],
            name=op.f("fk_reporting_report_items_report_run_id_reporting_report_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "report_run_id", "period", "ordinal", name=op.f("pk_reporting_report_items")
        ),
        sa.UniqueConstraint(
            "report_run_id",
            "period",
            "content_id",
            name=op.f("uq_reporting_report_items_report_run_id_period_content_id"),
        ),
        info={"owner": "reporting"},
    )


def downgrade() -> None:
    """撤销新增报告表；执行前应按部署手册处理报告任务与保留产物。"""
    op.drop_table("reporting_report_items")
    op.drop_table("reporting_report_artifacts")
    op.drop_index("ix_reporting_report_runs_created_at", table_name="reporting_report_runs")
    op.drop_table("reporting_report_runs")
