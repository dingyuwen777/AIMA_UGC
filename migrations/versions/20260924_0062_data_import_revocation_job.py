"""为不可变导入撤销事实增加可恢复请求状态。

Revision ID: 20260924_0062
Revises: 20260924_0061
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0062"
down_revision: str | Sequence[str] | None = "20260924_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """进度写入独立表，不修改已有禁止 UPDATE 的撤销事实。"""

    op.create_table(
        "historical_import_revocation_requests",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("checkpoint_content_id", sa.Uuid(), nullable=True),
        sa.Column("recomputed_content_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed')",
            name=op.f("ck_historical_import_revocation_requests_status_allowed"),
        ),
        sa.CheckConstraint(
            "recomputed_content_count >= 0",
            name=op.f("ck_historical_import_revocation_requests_recomputed_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["historical_import_campaign_revocations.campaign_id"],
            name=op.f(
                "fk_historical_import_revocation_requests_campaign_id_historical_import_campaign_revocations"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_historical_import_revocation_requests_job_id_jobs"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_historical_import_revocation_requests_raw_artifact_id_artifacts"),
        ),
        sa.PrimaryKeyConstraint(
            "campaign_id", name=op.f("pk_historical_import_revocation_requests")
        ),
        sa.UniqueConstraint("job_id", name=op.f("uq_historical_import_revocation_requests_job_id")),
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        "status in ('uploading','discovering','snapshotting','ready','queued','running',"
        "'cancelling','cancelled','succeeded','partial_failed','failed','revoking','revoked')",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM historical_import_revocation_requests)")
    ):
        raise RuntimeError("撤销请求已产生持久断点，禁止就地回退此 Migration；应恢复协调备份")
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        "status in ('uploading','discovering','snapshotting','ready','queued','running',"
        "'cancelling','cancelled','succeeded','partial_failed','failed')",
    )
    op.drop_table("historical_import_revocation_requests")
