"""建立 Stage 4 PostgreSQL Job Runtime。

Revision ID: 20260814_0002
Revises: 20260813_0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0002"
down_revision: str | Sequence[str] | None = "20260813_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("payload_version", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("internal_idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text()),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column(
            "lease_takeover_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("attempt_started_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.Text()),
        sa.Column("lease_token", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint(
            "job_type",
            "internal_idempotency_key",
            name=op.f("uq_jobs_job_type_internal_idempotency_key"),
        ),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed','cancelled')",
            name=op.f("ck_jobs_status_allowed"),
        ),
        sa.CheckConstraint("attempt >= 0", name=op.f("ck_jobs_attempt_nonnegative")),
        sa.CheckConstraint("max_attempts > 0", name=op.f("ck_jobs_max_attempts_positive")),
        sa.CheckConstraint("attempt <= max_attempts", name=op.f("ck_jobs_attempt_within_max")),
        sa.CheckConstraint(
            "status <> 'queued' or attempt < max_attempts",
            name=op.f("ck_jobs_queued_has_attempt_left"),
        ),
        sa.CheckConstraint(
            "lease_takeover_count >= 0",
            name=op.f("ck_jobs_lease_takeover_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "timeout_seconds > 0",
            name=op.f("ck_jobs_timeout_seconds_positive"),
        ),
        sa.CheckConstraint(
            "progress between 0 and 100",
            name=op.f("ck_jobs_progress_range"),
        ),
        sa.CheckConstraint(
            "(status = 'running' and attempt >= 1 and lease_owner is not null "
            "and lease_token is not null "
            "and lease_expires_at is not null and attempt_started_at is not null "
            "and attempt_deadline_at is not null and lease_expires_at <= attempt_deadline_at) or "
            "(status <> 'running' and lease_owner is null and lease_token is null "
            "and lease_expires_at is null)",
            name=op.f("ck_jobs_lease_state_consistent"),
        ),
        sa.CheckConstraint(
            "status <> 'queued' or (attempt_started_at is null and attempt_deadline_at is null "
            "and finished_at is null)",
            name=op.f("ck_jobs_queued_state_consistent"),
        ),
        sa.CheckConstraint(
            "((status in ('succeeded','failed','cancelled')) and finished_at is not null) or "
            "((status in ('queued','running')) and finished_at is null)",
            name=op.f("ck_jobs_finished_state_consistent"),
        ),
    )
    op.create_index(
        "ix_jobs_status_available_priority_created",
        "jobs",
        ["status", "available_at", sa.text("priority DESC"), "created_at"],
    )
    op.create_index(
        "ix_jobs_status_lease_expires",
        "jobs",
        ["status", "lease_expires_at"],
    )
    op.create_index(
        "ix_jobs_status_attempt_deadline",
        "jobs",
        ["status", "attempt_deadline_at"],
    )

    op.create_table(
        "job_attempt_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_takeover_count", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("worker_id", sa.Text()),
        sa.Column("lease_token_fingerprint", sa.Text()),
        sa.Column("reason_code", sa.Text()),
        sa.Column("safe_detail", sa.Text()),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_attempt_events_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_attempt_events")),
        sa.UniqueConstraint(
            "job_id",
            "event_seq",
            name=op.f("uq_job_attempt_events_job_id_event_seq"),
        ),
        sa.CheckConstraint(
            "attempt >= 0",
            name=op.f("ck_job_attempt_events_attempt_nonnegative"),
        ),
        sa.CheckConstraint(
            "lease_takeover_count >= 0",
            name=op.f("ck_job_attempt_events_lease_takeover_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "event_type in ('claimed','lease_taken_over','retry_scheduled','succeeded','failed',"
            "'cancelled','timed_out','lease_lost')",
            name=op.f("ck_job_attempt_events_event_type_allowed"),
        ),
    )
    op.create_index(
        "ix_job_attempt_events_job_seq",
        "job_attempt_events",
        ["job_id", "event_seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_attempt_events_job_seq", table_name="job_attempt_events")
    op.drop_table("job_attempt_events")
    op.drop_index("ix_jobs_status_attempt_deadline", table_name="jobs")
    op.drop_index("ix_jobs_status_lease_expires", table_name="jobs")
    op.drop_index("ix_jobs_status_available_priority_created", table_name="jobs")
    op.drop_table("jobs")
