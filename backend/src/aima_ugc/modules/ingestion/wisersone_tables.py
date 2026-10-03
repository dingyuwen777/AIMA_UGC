"""WisersOne 下载到统一导入的持久来源事实。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

wisersone_downloads_table = Table(
    "ingestion_wisersone_downloads",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("client_idempotency_key", Text(), nullable=False, unique=True),
    Column("request", JSONB(), nullable=False),
    Column("filter_snapshot", JSONB(), nullable=False),
    Column("occurrence_id", Uuid(), ForeignKey("collection_schedule_occurrences.id"), unique=True),
    Column("status", Text(), nullable=False),
    Column("send_state", Text(), nullable=False),
    Column("website_task_id", Text()),
    Column("step", Integer(), nullable=False),
    Column("job_id", Uuid(), ForeignKey("jobs.id")),
    Column("campaign_id", Uuid(), ForeignKey("historical_import_campaigns.id"), unique=True),
    Column("sha256", Text()),
    Column("percent", Integer(), nullable=False),
    Column("error_code", Text()),
    Column("cancel_requested_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("file_deleted_at", DateTime(timezone=True)),
    Column("file_delete_pending_at", DateTime(timezone=True)),
    CheckConstraint(
        "status in ('queued','submitting','waiting','downloading','preflight','importing',"
        "'succeeded','partial_failed','failed','cancelled','attention')",
        name="status_allowed",
    ),
    CheckConstraint("send_state in ('not_sent','unknown','confirmed')", name="send_state_allowed"),
    CheckConstraint("percent >= 0 and percent <= 100", name="percent_valid"),
    CheckConstraint("step >= 0", name="step_nonnegative"),
    info={"owner": "ingestion"},
)
