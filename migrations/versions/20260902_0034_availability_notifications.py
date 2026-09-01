"""建立第三方可用状态观察与 Principal Inbox。

Revision ID: 20260902_0034
Revises: 20260902_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0034"
down_revision: str | Sequence[str] | None = "20260902_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_availability_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("evidence_kind", sa.Text(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("safe_summary", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('available','unavailable_confirmed','unavailable_suspected','unknown')",
            name=op.f("ck_content_availability_observations_status_allowed"),
        ),
        sa.CheckConstraint(
            "evidence_kind in ('provider_explicit','technical_failure','manual_review')",
            name=op.f("ck_content_availability_observations_evidence_kind_allowed"),
        ),
        sa.CheckConstraint(
            "status <> 'unavailable_confirmed' or "
            "(evidence_kind = 'provider_explicit' and "
            "(provider_attempt_id is not null or raw_artifact_id is not null))",
            name=op.f(
                "ck_content_availability_observations_confirmed_requires_explicit_evidence"
            ),
        ),
        sa.CheckConstraint(
            "evidence_kind <> 'technical_failure' or "
            "status in ('unknown','unavailable_suspected')",
            name=op.f(
                "ck_content_availability_observations_technical_failure_status_limited"
            ),
        ),
        sa.CheckConstraint(
            "content_version > 0",
            name=op.f("ck_content_availability_observations_content_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_availability_observations_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f(
                "fk_content_availability_observations_provider_attempt_id_provider_request_attempts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_content_availability_observations_raw_artifact_id_artifacts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_availability_observations")),
        sa.UniqueConstraint(
            "content_id",
            "observed_at",
            "status",
            name="uq_content_availability_observation_identity",
        ),
    )
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deduplication_key", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column(
            "safe_detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(deduplication_key) > 0",
            name=op.f("ck_notification_events_deduplication_key_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(event_type) > 0",
            name=op.f("ck_notification_events_event_type_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(title) > 0", name=op.f("ck_notification_events_title_nonempty")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(safe_detail) = 'object'",
            name=op.f("ck_notification_events_safe_detail_object"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_events")),
        sa.UniqueConstraint(
            "deduplication_key", name=op.f("uq_notification_events_deduplication_key")
        ),
    )
    op.create_table(
        "notification_inbox_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(principal_id) > 0",
            name=op.f("ck_notification_inbox_items_principal_id_nonempty"),
        ),
        sa.CheckConstraint(
            "(is_read and read_at is not null) or (not is_read and read_at is null)",
            name=op.f("ck_notification_inbox_items_read_state_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["notification_events.id"],
            name=op.f("fk_notification_inbox_items_event_id_notification_events"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_inbox_items")),
        sa.UniqueConstraint(
            "event_id",
            "principal_id",
            name=op.f("uq_notification_inbox_items_event_id_principal_id"),
        ),
    )
    op.create_index(
        "ix_notification_inbox_principal_created",
        "notification_inbox_items",
        ["principal_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_inbox_principal_created", table_name="notification_inbox_items")
    op.drop_table("notification_inbox_items")
    op.drop_table("notification_events")
    op.drop_table("content_availability_observations")
