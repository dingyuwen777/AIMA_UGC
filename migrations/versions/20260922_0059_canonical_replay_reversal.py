"""增加 Canonical Replay 精确撤回账本与生命周期。

Revision ID: 20260922_0059
Revises: 20260922_0058
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260922_0059"
down_revision: str | Sequence[str] | None = "20260922_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为新建全量重筛记录精确贡献，并让旧记录保持 fail-closed。"""

    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reversible", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column(
            "lifecycle_status",
            sa.Text(),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reversal_job_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reversal_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reversal_requested_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reversal_request_id", sa.Text(), nullable=True),
    )
    for column in (
        "reverted_content_count",
        "hidden_content_count",
        "retained_content_count",
        "skipped_content_count",
        "restored_evidence_count",
        "skipped_evidence_count",
    ):
        op.add_column(
            "canonical_replay_all_requests",
            sa.Column(column, sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_lifecycle_status_allowed"),
        "canonical_replay_all_requests",
        "lifecycle_status in ('active','cancelling','reverting','reverted','revert_failed')",
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_reversal_counts_nonnegative"),
        "canonical_replay_all_requests",
        "reverted_content_count >= 0 and hidden_content_count >= 0 "
        "and retained_content_count >= 0 and skipped_content_count >= 0 "
        "and restored_evidence_count >= 0 and skipped_evidence_count >= 0",
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_reversal_requested_by_length"),
        "canonical_replay_all_requests",
        "reversal_requested_by is null or char_length(reversal_requested_by) between 1 and 200",
    )
    op.create_unique_constraint(
        op.f("uq_canonical_replay_all_requests_reversal_job_id"),
        "canonical_replay_all_requests",
        ["reversal_job_id"],
    )
    op.create_foreign_key(
        op.f("fk_canonical_replay_all_requests_reversal_job_id_jobs"),
        "canonical_replay_all_requests",
        "jobs",
        ["reversal_job_id"],
        ["id"],
    )

    op.add_column(
        "contents",
        sa.Column("replay_visibility_owner_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_contents_replay_visibility_owner_id_canonical_replay_all_requests"),
        "contents",
        "canonical_replay_all_requests",
        ["replay_visibility_owner_id"],
        ["id"],
    )

    op.create_table(
        "canonical_replay_content_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("all_request_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("provider_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("version_before", sa.Integer(), nullable=True),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.Column("delta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("visibility_owner_before", sa.Uuid(), nullable=True),
        sa.Column(
            "vehicle_evidence_before",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "vehicle_evidence_after",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "brand_evidence_before",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "brand_evidence_after",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_version_no", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(brand_evidence_after) = 'array'",
            name=op.f("ck_canonical_replay_content_changes_brand_after_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(brand_evidence_before) = 'array'",
            name=op.f("ck_canonical_replay_content_changes_brand_before_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(delta) = 'object'",
            name=op.f("ck_canonical_replay_content_changes_delta_object"),
        ),
        sa.CheckConstraint(
            "(reverted_at is null and reversal_version_no is null) or "
            "(reverted_at is not null and reversal_version_no >= 1)",
            name=op.f("ck_canonical_replay_content_changes_reversal_fields_consistent"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(vehicle_evidence_after) = 'array'",
            name=op.f("ck_canonical_replay_content_changes_vehicle_after_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(vehicle_evidence_before) = 'array'",
            name=op.f("ck_canonical_replay_content_changes_vehicle_before_array"),
        ),
        sa.CheckConstraint(
            "version_after >= 1",
            name=op.f("ck_canonical_replay_content_changes_version_after_positive"),
        ),
        sa.CheckConstraint(
            "version_before is null or version_before >= 1",
            name=op.f("ck_canonical_replay_content_changes_version_before_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["all_request_id"],
            ["canonical_replay_all_requests.id"],
            name=op.f(
                "fk_canonical_replay_content_changes_all_request_id_canonical_replay_all_requests"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_canonical_replay_content_changes_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_request_attempts.id"],
            name=op.f(
                "fk_canonical_replay_content_changes_provider_attempt_id_provider_request_attempts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_canonical_replay_content_changes_raw_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["canonical_replay_runs.id"],
            name=op.f("fk_canonical_replay_content_changes_run_id_canonical_replay_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["visibility_owner_before"],
            ["canonical_replay_all_requests.id"],
            name=op.f(
                "fk_canonical_replay_content_changes_visibility_owner_before_canonical_replay_all_requests"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_canonical_replay_content_changes")),
        sa.UniqueConstraint(
            "run_id",
            "content_id",
            name=op.f("uq_canonical_replay_content_changes_run_content"),
        ),
    )
    op.create_index(
        "ix_canonical_replay_content_changes_request_created",
        "canonical_replay_content_changes",
        ["all_request_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """删除撤回能力；Canonical、Raw、Content 历史仍保留。"""

    op.drop_index(
        "ix_canonical_replay_content_changes_request_created",
        table_name="canonical_replay_content_changes",
    )
    op.drop_table("canonical_replay_content_changes")
    op.drop_constraint(
        op.f("fk_contents_replay_visibility_owner_id_canonical_replay_all_requests"),
        "contents",
        type_="foreignkey",
    )
    op.drop_column("contents", "replay_visibility_owner_id")
    op.drop_constraint(
        op.f("fk_canonical_replay_all_requests_reversal_job_id_jobs"),
        "canonical_replay_all_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_canonical_replay_all_requests_reversal_job_id"),
        "canonical_replay_all_requests",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_reversal_requested_by_length"),
        "canonical_replay_all_requests",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_reversal_counts_nonnegative"),
        "canonical_replay_all_requests",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_lifecycle_status_allowed"),
        "canonical_replay_all_requests",
        type_="check",
    )
    for column in (
        "skipped_evidence_count",
        "restored_evidence_count",
        "skipped_content_count",
        "retained_content_count",
        "hidden_content_count",
        "reverted_content_count",
        "reversal_request_id",
        "reversal_requested_by",
        "reversed_at",
        "reversal_requested_at",
        "cancellation_requested_at",
        "reversal_job_id",
        "lifecycle_status",
        "reversible",
    ):
        op.drop_column("canonical_replay_all_requests", column)
