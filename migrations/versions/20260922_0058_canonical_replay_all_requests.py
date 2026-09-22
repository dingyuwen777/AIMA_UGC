"""增加全历史 Canonical Replay 请求与子 Run 追溯。

Revision ID: 20260922_0058
Revises: 20260922_0057
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0058"
down_revision: str | Sequence[str] | None = "20260922_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """保存全量请求的冻结清单摘要，并把拆分后的 Run 关联回父请求。"""

    op.create_table(
        "canonical_replay_all_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_idempotency_key", sa.Text(), nullable=False),
        sa.Column("selection_digest", sa.Text(), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("artifacts_per_run", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_count >= 0",
            name=op.f("ck_canonical_replay_all_requests_artifact_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "artifacts_per_run = 100",
            name=op.f("ck_canonical_replay_all_requests_artifacts_per_run_fixed"),
        ),
        sa.CheckConstraint(
            "batch_size = 1000",
            name=op.f("ck_canonical_replay_all_requests_batch_size_fixed"),
        ),
        sa.CheckConstraint(
            "char_length(created_by) between 1 and 200",
            name=op.f("ck_canonical_replay_all_requests_created_by_length"),
        ),
        sa.CheckConstraint(
            "char_length(client_idempotency_key) between 1 and 120",
            name=op.f("ck_canonical_replay_all_requests_idempotency_key_length"),
        ),
        sa.CheckConstraint(
            "run_count >= 0",
            name=op.f("ck_canonical_replay_all_requests_run_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "char_length(selection_digest) = 64",
            name=op.f("ck_canonical_replay_all_requests_selection_digest_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_canonical_replay_all_requests")),
        sa.UniqueConstraint(
            "client_idempotency_key",
            name=op.f("uq_canonical_replay_all_requests_client_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_canonical_replay_all_requests_created_at"),
        "canonical_replay_all_requests",
        ["created_at", "id"],
        unique=False,
    )
    op.add_column(
        "canonical_replay_runs",
        sa.Column("all_request_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "canonical_replay_runs",
        sa.Column("all_request_ordinal", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_canonical_replay_runs_all_request_id_canonical_replay_all_requests"),
        "canonical_replay_runs",
        "canonical_replay_all_requests",
        ["all_request_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_runs_all_request_fields_consistent"),
        "canonical_replay_runs",
        "(all_request_id is null and all_request_ordinal is null) or "
        "(all_request_id is not null and all_request_ordinal >= 0)",
    )
    op.create_unique_constraint(
        op.f("uq_canonical_replay_runs_all_request_ordinal"),
        "canonical_replay_runs",
        ["all_request_id", "all_request_ordinal"],
    )


def downgrade() -> None:
    """删除全量编排父事实，不改写 Canonical Artifact 或 Content。"""

    op.drop_constraint(
        op.f("uq_canonical_replay_runs_all_request_ordinal"),
        "canonical_replay_runs",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_runs_all_request_fields_consistent"),
        "canonical_replay_runs",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_canonical_replay_runs_all_request_id_canonical_replay_all_requests"),
        "canonical_replay_runs",
        type_="foreignkey",
    )
    op.drop_column("canonical_replay_runs", "all_request_ordinal")
    op.drop_column("canonical_replay_runs", "all_request_id")
    op.drop_index(
        op.f("ix_canonical_replay_all_requests_created_at"),
        table_name="canonical_replay_all_requests",
    )
    op.drop_table("canonical_replay_all_requests")
