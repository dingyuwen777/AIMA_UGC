"""Platform 模块拥有的持久化 Job Runtime 数据表。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

jobs_table = Table(
    "jobs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_type", Text(), nullable=False),
    Column("payload_version", Text(), nullable=False),
    Column("payload", JSONB(), nullable=False),
    Column("result", JSONB()),
    Column("status", Text(), nullable=False),
    Column("internal_idempotency_key", Text(), nullable=False),
    Column("request_id", Text()),
    Column("priority", Integer(), nullable=False),
    Column("attempt", Integer(), nullable=False),
    Column("lease_takeover_count", Integer(), nullable=False, server_default=text("0")),
    Column("max_attempts", Integer(), nullable=False),
    Column("timeout_seconds", Integer(), nullable=False),
    Column("attempt_started_at", DateTime(timezone=True)),
    Column("attempt_deadline_at", DateTime(timezone=True)),
    Column("progress", Integer(), nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("lease_owner", Text()),
    Column("lease_token", Text()),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("heartbeat_at", DateTime(timezone=True)),
    Column("cancel_requested_at", DateTime(timezone=True)),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_code", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_type", "internal_idempotency_key"),
    CheckConstraint(
        "status in ('queued','running','succeeded','failed','cancelled')",
        name="status_allowed",
    ),
    CheckConstraint("attempt >= 0", name="attempt_nonnegative"),
    CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
    CheckConstraint("attempt <= max_attempts", name="attempt_within_max"),
    CheckConstraint("status <> 'queued' or attempt < max_attempts", name="queued_has_attempt_left"),
    CheckConstraint("lease_takeover_count >= 0", name="lease_takeover_count_nonnegative"),
    CheckConstraint("timeout_seconds > 0", name="timeout_seconds_positive"),
    CheckConstraint("progress between 0 and 100", name="progress_range"),
    CheckConstraint(
        "(status = 'running' and attempt >= 1 and lease_owner is not null "
        "and lease_token is not null "
        "and lease_expires_at is not null and attempt_started_at is not null "
        "and attempt_deadline_at is not null and lease_expires_at <= attempt_deadline_at) or "
        "(status <> 'running' and lease_owner is null and lease_token is null "
        "and lease_expires_at is null)",
        name="lease_state_consistent",
    ),
    CheckConstraint(
        "status <> 'queued' or (attempt_started_at is null and attempt_deadline_at is null "
        "and finished_at is null)",
        name="queued_state_consistent",
    ),
    CheckConstraint(
        "((status in ('succeeded','failed','cancelled')) and finished_at is not null) or "
        "((status in ('queued','running')) and finished_at is null)",
        name="finished_state_consistent",
    ),
    info={"owner": "operations"},
)

job_attempt_events_table = Table(
    "job_attempt_events",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("event_seq", Integer(), nullable=False),
    Column("attempt", Integer(), nullable=False),
    Column("lease_takeover_count", Integer(), nullable=False),
    Column("event_type", Text(), nullable=False),
    Column("worker_id", Text()),
    Column("lease_token_fingerprint", Text()),
    Column("reason_code", Text()),
    Column("safe_detail", Text()),
    Column("happened_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", "event_seq"),
    CheckConstraint("attempt >= 0", name="attempt_nonnegative"),
    CheckConstraint("lease_takeover_count >= 0", name="lease_takeover_count_nonnegative"),
    CheckConstraint(
        "event_type in ('claimed','lease_taken_over','retry_scheduled','succeeded','failed',"
        "'cancelled','timed_out','lease_lost')",
        name="event_type_allowed",
    ),
    info={"owner": "operations"},
)

Index(
    "ix_jobs_status_available_priority_created",
    jobs_table.c.status,
    jobs_table.c.available_at,
    jobs_table.c.priority.desc(),
    jobs_table.c.created_at,
)
Index("ix_jobs_status_lease_expires", jobs_table.c.status, jobs_table.c.lease_expires_at)
Index("ix_jobs_status_attempt_deadline", jobs_table.c.status, jobs_table.c.attempt_deadline_at)
Index(
    "ix_job_attempt_events_job_seq",
    job_attempt_events_table.c.job_id,
    job_attempt_events_table.c.event_seq,
)
