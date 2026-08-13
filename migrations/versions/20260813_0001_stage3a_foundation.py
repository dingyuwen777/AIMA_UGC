"""建立 Stage 3A 基础表。

Revision ID: 20260813_0001
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("storage_backend", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("encoding", sa.Text()),
        sa.Column("sha256", sa.Text()),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("retention_class", sa.Text(), nullable=False),
        sa.Column("storage_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True)),
        sa.Column("linked_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint(
            "storage_backend",
            "storage_key",
            name=op.f("uq_artifacts_storage_backend_storage_key"),
        ),
        sa.CheckConstraint(
            "storage_status in ('pending','stored','linked','delete_pending','deleted','error')",
            name=op.f("ck_artifacts_storage_status_allowed"),
        ),
        sa.CheckConstraint(
            "(storage_status = 'pending' and sha256 is null and byte_size is null "
            "and stored_at is null and linked_at is null and deleted_at is null) or "
            "(storage_status = 'stored' and sha256 is not null and byte_size >= 0 "
            "and stored_at is not null and linked_at is null and deleted_at is null) or "
            "(storage_status = 'linked' and sha256 is not null and byte_size >= 0 "
            "and stored_at is not null and linked_at is not null and deleted_at is null) or "
            "(storage_status = 'delete_pending' and sha256 is not null and byte_size >= 0 "
            "and stored_at is not null and deleted_at is null) or "
            "(storage_status = 'deleted' and sha256 is not null and byte_size >= 0 "
            "and stored_at is not null and deleted_at is not null) or storage_status = 'error'",
            name=op.f("ck_artifacts_storage_state_consistent"),
        ),
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_system_settings")),
        sa.CheckConstraint("char_length(key) > 0", name=op.f("ck_system_settings_key_nonempty")),
        sa.CheckConstraint("version > 0", name=op.f("ck_system_settings_version_positive")),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_ref", sa.Text()),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text()),
        sa.Column("object_id", sa.Text()),
        sa.Column("request_id", sa.Text()),
        sa.Column(
            "safe_detail",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
        sa.CheckConstraint(
            "actor_kind in ('system','principal')",
            name=op.f("ck_audit_events_actor_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(event_type) > 0",
            name=op.f("ck_audit_events_event_type_nonempty"),
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("system_settings")
    op.drop_table("artifacts")
