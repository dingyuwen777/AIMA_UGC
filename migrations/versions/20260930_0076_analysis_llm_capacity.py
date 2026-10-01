"""持久化 LLM 自适应容量，保留业务 Run 与结果表不变。

Revision ID: 20260930_0076
Revises: 20260929_0075
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260930_0076"
down_revision: str | Sequence[str] | None = "20260929_0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """只新增可冷启动重建的派生学习状态，不改写历史 Run。"""

    op.create_table(
        "analysis_llm_capacity_profiles",
        sa.Column("provider_config_id", sa.Uuid(), primary_key=True),
        sa.Column("model", sa.Text(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("prompt_sha256", sa.Text(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("window", postgresql.JSONB(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_adjusted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision > 0", name=op.f("ck_analysis_llm_capacity_profiles_revision_positive")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(state) = 'object'",
            name=op.f("ck_analysis_llm_capacity_profiles_state_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(\"window\") = 'object'",
            name=op.f("ck_analysis_llm_capacity_profiles_window_object"),
        ),
        sa.CheckConstraint(
            "(state->>'current')::integer between 1 and 5000",
            name=op.f("ck_analysis_llm_capacity_profiles_current_bounded"),
        ),
    )


def downgrade() -> None:
    """回滚前必须排空 adaptive Run；删除派生状态后下次升级从冷启动恢复。"""

    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM analysis_content_runs r "
                "WHERE r.runtime_config_snapshot->>'capacity_mode' LIKE 'adaptive.v%' "
                "AND (r.status IN ('queued','running','cancelling') OR EXISTS ("
                "SELECT 1 FROM jobs j WHERE j.status IN ('queued','running') AND ("
                "j.id = r.planner_job_id OR j.id IN (SELECT q.job_id "
                "FROM analysis_content_requests q WHERE q.run_id = r.id)))) LIMIT 1"
            )
        )
        .scalar_one_or_none()
        is not None
    ):
        raise RuntimeError("存在未结束的 adaptive Run，不能移除容量状态")
    op.drop_table("analysis_llm_capacity_profiles")
