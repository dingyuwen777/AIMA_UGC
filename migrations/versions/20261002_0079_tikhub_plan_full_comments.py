"""显式TikHub计划类型、全量评论动作与冻结完整度输入。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0079"
down_revision: str | Sequence[str] | None = "20261001_0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """回填既有类型，不改评论策略、历史Run或既有Coverage事实。"""
    op.add_column(
        "collection_plans",
        sa.Column("plan_type", sa.Text(), nullable=False, server_default="tikhub"),
    )
    op.create_check_constraint(
        op.f("ck_collection_plans_plan_type_allowed"), "collection_plans", "plan_type in ('tikhub')"
    )
    op.create_check_constraint(
        op.f("ck_collection_plans_comment_policy_allowed"),
        "collection_plans",
        "comment_policy in ('adaptive','full')",
    )
    op.add_column(
        "collection_content_actions",
        sa.Column(
            "previous_capture_complete", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    _replace_action_constraint(include_full=True)
    op.execute("""
        CREATE INDEX ix_comment_coverage_latest_capture
        ON comment_coverage_observations (content_id, observed_at DESC, id DESC)
        WHERE coverage <> 'not_requested'
    """)
    op.execute("""
        CREATE INDEX ix_comment_thread_coverage_latest_capture
        ON comment_thread_coverage_observations (content_id, root_comment_id, observed_at DESC, id DESC)
        WHERE coverage <> 'not_requested'
    """)


def downgrade() -> None:
    """拒绝静默丢弃full语义；历史动作不能通过篡改为采样来回滚。"""
    blocked = op.get_bind().scalar(
        sa.text("""
        SELECT EXISTS (SELECT 1 FROM collection_plans WHERE comment_policy = 'full')
          OR EXISTS (SELECT 1 FROM collection_content_actions WHERE comment_action = 'fetch_full')
          OR EXISTS (SELECT 1 FROM collection_runs
                     WHERE config_snapshot->>'schema_version' = 'collection-run-config.v4'
                       AND status IN ('queued', 'running'))
    """)
    )
    if blocked:
        raise RuntimeError("存在full计划/审计动作或未完成v4 Run，不能安全降级")
    _replace_action_constraint(include_full=False)
    op.drop_index("ix_comment_thread_coverage_latest_capture")
    op.drop_index("ix_comment_coverage_latest_capture")
    op.drop_column("collection_content_actions", "previous_capture_complete")
    op.drop_constraint(
        op.f("ck_collection_plans_comment_policy_allowed"), "collection_plans", type_="check"
    )
    op.drop_constraint(
        op.f("ck_collection_plans_plan_type_allowed"), "collection_plans", type_="check"
    )
    op.drop_column("collection_plans", "plan_type")


def _replace_action_constraint(*, include_full: bool) -> None:
    name = op.f("ck_collection_content_actions_comment_action_allowed")
    op.drop_constraint(name, "collection_content_actions", type_="check")
    actions = (
        "'skip','fetch_adaptive','fetch_incremental','refresh_controlled',"
        "'probe_first_page','defer_until_detail'"
    )
    if include_full:
        actions += ",'fetch_full'"
    op.create_check_constraint(name, "collection_content_actions", f"comment_action in ({actions})")
