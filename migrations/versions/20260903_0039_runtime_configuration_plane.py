"""扩展 Provider Config 并为 Analysis Run 增加安全运行时快照。

Revision ID: 20260903_0039
Revises: 20260902_0038
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0039"
down_revision: str | Sequence[str] | None = "20260902_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """把 Provider Config 升级为 LLM/Collection 共用的非敏感控制面。"""

    op.add_column(
        "provider_configs",
        sa.Column("provider_kind", sa.Text(), nullable=False, server_default="collection"),
    )
    op.add_column("provider_configs", sa.Column("model", sa.Text(), nullable=True))
    op.add_column(
        "provider_configs",
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="45"),
    )
    op.add_column(
        "provider_configs",
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "provider_configs",
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column("provider_configs", sa.Column("max_rps", sa.Integer(), nullable=True))
    op.add_column(
        "provider_configs",
        sa.Column(
            "extra_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "provider_configs",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "provider_configs",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "provider_kind_allowed",
        "provider_configs",
        "provider_kind in ('collection','llm')",
    )
    op.create_check_constraint(
        "timeout_seconds_positive",
        "provider_configs",
        "timeout_seconds > 0",
    )
    op.create_check_constraint(
        "max_retries_nonnegative",
        "provider_configs",
        "max_retries >= 0",
    )
    op.create_check_constraint(
        "max_concurrency_positive",
        "provider_configs",
        "max_concurrency > 0",
    )
    op.create_check_constraint(
        "max_rps_positive_or_null",
        "provider_configs",
        "max_rps is null or max_rps > 0",
    )
    op.create_check_constraint(
        "revision_positive",
        "provider_configs",
        "revision > 0",
    )
    op.create_check_constraint(
        "llm_model_required",
        "provider_configs",
        "provider_kind <> 'llm' or (model is not null and char_length(model) > 0)",
    )
    op.create_index(
        "uq_provider_configs_default_llm",
        "provider_configs",
        ["provider_kind"],
        unique=True,
        postgresql_where=sa.text("provider_kind = 'llm' and is_default and enabled"),
    )

    op.add_column(
        "analysis_content_runs",
        sa.Column(
            "runtime_config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "runtime_config_snapshot_object",
        "analysis_content_runs",
        "jsonb_typeof(runtime_config_snapshot) = 'object'",
    )


def downgrade() -> None:
    """移除 Runtime Configuration Plane 的新增数据库结构。"""

    op.drop_constraint(
        "runtime_config_snapshot_object",
        "analysis_content_runs",
        type_="check",
    )
    op.drop_column("analysis_content_runs", "runtime_config_snapshot")

    op.drop_index("uq_provider_configs_default_llm", table_name="provider_configs")
    op.drop_constraint("llm_model_required", "provider_configs", type_="check")
    op.drop_constraint("revision_positive", "provider_configs", type_="check")
    op.drop_constraint("max_rps_positive_or_null", "provider_configs", type_="check")
    op.drop_constraint("max_concurrency_positive", "provider_configs", type_="check")
    op.drop_constraint("max_retries_nonnegative", "provider_configs", type_="check")
    op.drop_constraint("timeout_seconds_positive", "provider_configs", type_="check")
    op.drop_constraint("provider_kind_allowed", "provider_configs", type_="check")
    op.drop_column("provider_configs", "revision")
    op.drop_column("provider_configs", "is_default")
    op.drop_column("provider_configs", "extra_config")
    op.drop_column("provider_configs", "max_rps")
    op.drop_column("provider_configs", "max_concurrency")
    op.drop_column("provider_configs", "max_retries")
    op.drop_column("provider_configs", "timeout_seconds")
    op.drop_column("provider_configs", "model")
    op.drop_column("provider_configs", "provider_kind")
