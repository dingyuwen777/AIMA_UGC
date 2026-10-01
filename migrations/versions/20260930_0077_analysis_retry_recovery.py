"""持久化 Analysis 待重试与独立健康窗口。

Revision ID: 20260930_0077
Revises: 20260930_0076
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260930_0077"
down_revision: str | Sequence[str] | None = "20260930_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """扩展已有 Run/Item，不改写旧协议 Snapshot 或已终态内容。"""

    for name in ("transport_failure_started_at", "last_transport_success_at"):
        op.add_column("analysis_content_runs", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column(
        "analysis_content_runs",
        sa.Column(
            "transport_failure_spans",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_runs_transport_failure_spans_bounded"),
        "analysis_content_runs",
        "jsonb_typeof(transport_failure_spans) = 'array' "
        "and jsonb_array_length(transport_failure_spans) <= 4096",
    )
    op.add_column(
        "analysis_content_runs",
        sa.Column("probe_job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
    )
    op.add_column(
        "analysis_content_runs", sa.Column("probe_not_before", sa.DateTime(timezone=True))
    )
    item = "analysis_content_request_items"
    op.add_column(item, sa.Column("retry_kind", sa.Text()))
    op.add_column(item, sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    for name in ("retry_not_before", "last_retry_at", "validation_failure_started_at"):
        op.add_column(item, sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column(
        item,
        sa.Column(
            "validation_error_codes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    for name, expression in (
        ("retry_count_nonnegative", "retry_count >= 0"),
        ("retry_kind_allowed", "retry_kind is null or retry_kind in ('validation','transport')"),
        ("retry_errors_array", "jsonb_typeof(validation_error_codes) = 'array'"),
    ):
        op.create_check_constraint(op.f(f"ck_{item}_{name}"), item, expression)
    op.create_index(
        "ix_analysis_items_retry_ready",
        item,
        ["request_id", "retry_not_before", "ordinal"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_analysis_items_validation_window",
        item,
        ["request_id", "validation_failure_started_at"],
        postgresql_where=sa.text(
            "status = 'pending' AND validation_failure_started_at IS NOT NULL"
        ),
    )


def downgrade() -> None:
    """必须先排空新恢复协议 Run，防止丢失待重试与熔断计时。"""

    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM analysis_content_runs r "
                "WHERE r.runtime_config_snapshot->>'recovery_mode' "
                "IN ('recovery.v1','recovery.v2') "
                "AND (r.status IN ('queued','running','cancelling') OR EXISTS ("
                "SELECT 1 FROM jobs j WHERE j.status IN ('queued','running') AND ("
                "j.id = r.planner_job_id OR j.id IN (SELECT q.job_id "
                "FROM analysis_content_requests q WHERE q.run_id = r.id)))) LIMIT 1"
            )
        )
        .scalar_one_or_none()
        is not None
    ):
        raise RuntimeError("存在未结束的 recovery Run，不能移除重试状态")
    item = "analysis_content_request_items"
    op.drop_index("ix_analysis_items_retry_ready", table_name=item)
    op.drop_index("ix_analysis_items_validation_window", table_name=item)
    for name in ("retry_count_nonnegative", "retry_kind_allowed", "retry_errors_array"):
        op.drop_constraint(op.f(f"ck_{item}_{name}"), item, type_="check")
    for name in (
        "validation_error_codes",
        "validation_failure_started_at",
        "last_retry_at",
        "retry_not_before",
        "retry_count",
        "retry_kind",
    ):
        op.drop_column(item, name)
    op.drop_constraint(
        op.f("ck_analysis_content_runs_transport_failure_spans_bounded"),
        "analysis_content_runs",
        type_="check",
    )
    for name in (
        "probe_not_before",
        "probe_job_id",
        "transport_failure_spans",
        "last_transport_success_at",
        "transport_failure_started_at",
    ):
        op.drop_column("analysis_content_runs", name)
