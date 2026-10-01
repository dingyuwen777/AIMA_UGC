"""Reporting 持有报告、完整冻结数据及 Artifact 关联；字节元数据仍归 Platform。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

report_runs_table = Table(
    "reporting_report_runs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("name", Text(), nullable=False),
    Column("brand_id", Uuid(), ForeignKey("vehicle_brands.id"), nullable=False),
    Column("vehicle_model_ids", JSONB(), nullable=False),
    Column("start_date", Date(), nullable=False),
    Column("end_date", Date(), nullable=False),
    Column("generation_job_id", Uuid(), ForeignKey("jobs.id"), nullable=False, unique=True),
    Column("publication_job_id", Uuid(), ForeignKey("jobs.id"), unique=True),
    Column("snapshot", JSONB(), nullable=False),
    Column("generation_result", JSONB()),
    Column("generation_checkpoint", JSONB(), nullable=False),
    Column("publication_checkpoint", JSONB(), nullable=False),
    Column("created_by", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("expires_at", DateTime(timezone=True)),
    CheckConstraint("start_date <= end_date", name="date_order"),
    CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="snapshot_object"),
    CheckConstraint("jsonb_typeof(vehicle_model_ids) = 'array'", name="vehicles_array"),
    CheckConstraint("jsonb_typeof(publication_checkpoint) = 'object'", name="checkpoint_object"),
    CheckConstraint("(completed_at IS NULL) = (expires_at IS NULL)", name="completion_consistent"),
    Index("ix_reporting_report_runs_created_at", "created_at"),
    info={"owner": "reporting"},
)

report_items_table = Table(
    "reporting_report_items",
    metadata,
    Column(
        "report_run_id",
        Uuid(),
        ForeignKey("reporting_report_runs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("period", Text(), primary_key=True),
    Column("ordinal", Integer(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("data", JSONB(), nullable=False),
    Column("analysis_basis", JSONB(), nullable=False),
    UniqueConstraint("report_run_id", "period", "content_id"),
    CheckConstraint("period IN ('current', 'previous')", name="period_allowed"),
    CheckConstraint("content_version > 0 AND ordinal >= 0", name="position_valid"),
    CheckConstraint("jsonb_typeof(data) = 'object'", name="data_object"),
    info={"owner": "reporting"},
)

report_artifacts_table = Table(
    "reporting_report_artifacts",
    metadata,
    Column(
        "report_run_id",
        Uuid(),
        ForeignKey("reporting_report_runs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("artifact_id", Uuid(), ForeignKey("artifacts.id"), primary_key=True),
    Column("artifact_type", Text(), nullable=False),
    Column("filename", Text(), nullable=False),
    UniqueConstraint("report_run_id", "filename"),
    info={"owner": "reporting"},
)
