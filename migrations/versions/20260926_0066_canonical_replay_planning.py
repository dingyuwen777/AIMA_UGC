"""为全历史 Replay Planner 增加显式持久规划状态与受理边界。

Revision ID: 20260926_0066
Revises: 20260925_0065
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0066"
down_revision: str | Sequence[str] | None = "20260925_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """旧请求标记为已规划；新请求可持久观察 Planner 生命周期。"""

    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("accepted_before", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column(
            "planning_status",
            sa.Text(),
            server_default=sa.text("'planned'"),
            nullable=False,
        ),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("planner_job_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        "UPDATE canonical_replay_all_requests "
        "SET accepted_before = created_at "
        "WHERE accepted_before IS NULL"
    )
    op.alter_column(
        "canonical_replay_all_requests",
        "accepted_before",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_planning_status_allowed"),
        "canonical_replay_all_requests",
        "planning_status in ('queued','running','planned','failed','cancelled')",
    )
    op.create_unique_constraint(
        op.f("uq_canonical_replay_all_requests_planner_job_id"),
        "canonical_replay_all_requests",
        ["planner_job_id"],
    )
    op.create_foreign_key(
        op.f("fk_canonical_replay_all_requests_planner_job_id_jobs"),
        "canonical_replay_all_requests",
        "jobs",
        ["planner_job_id"],
        ["id"],
    )


def downgrade() -> None:
    """仍有未完成 Planner 时拒绝降级，避免旧代码误读受理中的请求。"""

    pending = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM canonical_replay_all_requests "
            "WHERE planning_status <> 'planned' LIMIT 1"
        )
    ).first()
    if pending is not None:
        raise RuntimeError("仍存在未完成的 Replay Planner 请求，不能安全 downgrade 0066")
    op.drop_constraint(
        op.f("fk_canonical_replay_all_requests_planner_job_id_jobs"),
        "canonical_replay_all_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_canonical_replay_all_requests_planner_job_id"),
        "canonical_replay_all_requests",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_planning_status_allowed"),
        "canonical_replay_all_requests",
        type_="check",
    )
    op.drop_column("canonical_replay_all_requests", "planner_job_id")
    op.drop_column("canonical_replay_all_requests", "planning_status")
    op.drop_column("canonical_replay_all_requests", "accepted_before")
