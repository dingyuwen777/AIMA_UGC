"""WisersOne 下载来源、远端任务回执和统一 Campaign 关联。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0080"
down_revision: str | Sequence[str] | None = "20261002_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_wisersone_downloads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_idempotency_key", sa.Text(), nullable=False, unique=True),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("send_state", sa.Text(), nullable=False),
        sa.Column("website_task_id", sa.Text()),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id")),
        sa.Column(
            "campaign_id", sa.Uuid(), sa.ForeignKey("historical_import_campaigns.id"), unique=True
        ),
        sa.Column("sha256", sa.Text()),
        sa.Column("percent", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("file_deleted_at", sa.DateTime(timezone=True)),
        sa.Column("file_delete_pending_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status in ('queued','submitting','waiting','downloading','preflight','importing',"
            "'succeeded','partial_failed','failed','cancelled','attention')",
            name=op.f("ck_ingestion_wisersone_downloads_status_allowed"),
        ),
        sa.CheckConstraint(
            "send_state in ('not_sent','unknown','confirmed')",
            name=op.f("ck_ingestion_wisersone_downloads_send_state_allowed"),
        ),
        sa.CheckConstraint(
            "percent >= 0 and percent <= 100",
            name=op.f("ck_ingestion_wisersone_downloads_percent_valid"),
        ),
        sa.CheckConstraint(
            "step >= 0", name=op.f("ck_ingestion_wisersone_downloads_step_nonnegative")
        ),
    )


def downgrade() -> None:
    op.drop_table("ingestion_wisersone_downloads")
