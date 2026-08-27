"""建立 Stage 12 Analysis Run/Shard 与按 Run 保留结果。

Revision ID: 20260826_0027
Revises: 20260826_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_0027"
down_revision: str | Sequence[str] | None = "20260826_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPTY_CONFIG_SHA256 = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
_ZERO_SHA256 = "0" * 64


def upgrade() -> None:
    op.create_table(
        "analysis_content_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "sequence_no",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("client_idempotency_key", sa.Text(), nullable=False),
        sa.Column("planner_job_id", sa.Uuid(), nullable=False),
        sa.Column("run_intent", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("filter_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("shard_count", sa.Integer(), nullable=False),
        sa.Column("shard_size", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("prompt_sha256", sa.Text(), nullable=False),
        sa.Column("taxonomy_sha256", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "generation_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("generation_config_hash", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "run_intent in ('initial_analysis','manual_reanalysis')",
            name=op.f("ck_analysis_content_runs_run_intent_allowed"),
        ),
        sa.CheckConstraint(
            "scope in ('query','selected')",
            name=op.f("ck_analysis_content_runs_scope_allowed"),
        ),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','partial_failed','failed',"
            "'cancelling','cancelled')",
            name=op.f("ck_analysis_content_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "target_count > 0",
            name=op.f("ck_analysis_content_runs_target_count_positive"),
        ),
        sa.CheckConstraint(
            "shard_count > 0",
            name=op.f("ck_analysis_content_runs_shard_count_positive"),
        ),
        sa.CheckConstraint(
            "shard_size > 0",
            name=op.f("ck_analysis_content_runs_shard_size_positive"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(filter_snapshot) = 'object'",
            name=op.f("ck_analysis_content_runs_filter_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(generation_config) = 'object'",
            name=op.f("ck_analysis_content_runs_generation_config_object"),
        ),
        sa.CheckConstraint(
            "char_length(prompt_sha256) = 64",
            name=op.f("ck_analysis_content_runs_prompt_sha256_length"),
        ),
        sa.CheckConstraint(
            "char_length(taxonomy_sha256) = 64",
            name=op.f("ck_analysis_content_runs_taxonomy_sha256_length"),
        ),
        sa.CheckConstraint(
            "char_length(generation_config_hash) = 64",
            name=op.f("ck_analysis_content_runs_generation_config_hash_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_content_runs")),
        sa.ForeignKeyConstraint(
            ["planner_job_id"],
            ["jobs.id"],
            name=op.f("fk_analysis_content_runs_planner_job_id_jobs"),
        ),
        sa.UniqueConstraint(
            "sequence_no",
            name=op.f("uq_analysis_content_runs_sequence_no"),
        ),
        sa.UniqueConstraint(
            "client_idempotency_key",
            name=op.f("uq_analysis_content_runs_client_idempotency_key"),
        ),
        sa.UniqueConstraint(
            "planner_job_id",
            name=op.f("uq_analysis_content_runs_planner_job_id"),
        ),
    )
    op.add_column("analysis_content_requests", sa.Column("run_id", sa.Uuid(), nullable=True))
    op.add_column("analysis_content_requests", sa.Column("shard_no", sa.Integer(), nullable=True))
    op.add_column(
        "analysis_content_results", sa.Column("analysis_run_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "analysis_content_results",
        sa.Column("generation_config_hash", sa.Text(), nullable=True),
    )
    op.drop_constraint(
        op.f("ck_analysis_content_request_items_status_allowed"),
        "analysis_content_request_items",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_request_items_status_fields_consistent"),
        "analysis_content_request_items",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_request_items_status_allowed"),
        "analysis_content_request_items",
        "status in ('pending','succeeded','failed','stale','cancelled')",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_request_items_status_fields_consistent"),
        "analysis_content_request_items",
        "(status = 'pending' and analysis_result_id is null and error_code is null) or "
        "(status = 'succeeded' and analysis_result_id is not null and error_code is null) or "
        "(status in ('failed','stale','cancelled') and analysis_result_id is null "
        "and error_code is not null)",
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO analysis_content_runs (
                id, client_idempotency_key, planner_job_id, run_intent, scope,
                filter_snapshot, status, target_count, shard_count, shard_size,
                prompt_version, prompt_sha256, taxonomy_sha256,
                model_provider, model, generation_config, generation_config_hash, error_code,
                created_at, started_at, finished_at, cancel_requested_at
            )
            SELECT
                request.id,
                'legacy-request:' || request.id::text,
                request.job_id,
                'initial_analysis',
                request.scope,
                request.filter_snapshot,
                CASE job.status
                    WHEN 'succeeded' THEN 'succeeded'
                    WHEN 'failed' THEN 'failed'
                    WHEN 'cancelled' THEN 'cancelled'
                    WHEN 'running' THEN 'running'
                    ELSE 'queued'
                END,
                request.target_count,
                1,
                request.target_count,
                COALESCE(identity.prompt_version, 'legacy-unknown'),
                COALESCE(identity.prompt_sha256, '{_ZERO_SHA256}'),
                COALESCE(identity.taxonomy_sha256, '{_ZERO_SHA256}'),
                COALESCE(identity.model_provider, 'legacy-unknown'),
                COALESCE(identity.model, 'legacy-unknown'),
                '{{}}'::jsonb,
                '{_EMPTY_CONFIG_SHA256}',
                job.error_code,
                request.created_at,
                job.started_at,
                job.finished_at,
                job.cancel_requested_at
            FROM analysis_content_requests AS request
            JOIN jobs AS job ON job.id = request.job_id
            LEFT JOIN LATERAL (
                SELECT
                    result.prompt_version,
                    result.prompt_sha256,
                    result.taxonomy_sha256,
                    result.model_provider,
                    result.model
                FROM analysis_content_results AS result
                WHERE result.job_id = request.job_id
                ORDER BY result.created_at, result.id
                LIMIT 1
            ) AS identity ON true
            ORDER BY request.created_at, request.id
            """
        )
    )
    op.execute("UPDATE analysis_content_requests SET run_id = id, shard_no = 0")
    op.create_table(
        "analysis_content_run_targets",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("target_ordinal", sa.BigInteger(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "target_ordinal >= 0",
            name=op.f("ck_analysis_content_run_targets_target_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "content_version >= 1",
            name=op.f("ck_analysis_content_run_targets_content_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_analysis_content_run_targets_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_content_runs.id"],
            name=op.f("fk_analysis_content_run_targets_run_id_analysis_content_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "run_id",
            "target_ordinal",
            name=op.f("pk_analysis_content_run_targets"),
        ),
        sa.UniqueConstraint(
            "run_id",
            "content_id",
            name=op.f("uq_analysis_content_run_targets_content"),
        ),
    )
    op.create_index(
        op.f("ix_analysis_content_run_targets_run_ordinal"),
        "analysis_content_run_targets",
        ["run_id", "target_ordinal"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO analysis_content_run_targets (
            run_id, target_ordinal, content_id, content_version
        )
        SELECT request.run_id, item.ordinal, item.content_id, item.content_version
        FROM analysis_content_request_items AS item
        JOIN analysis_content_requests AS request ON request.id = item.request_id
        """
    )
    op.execute(
        sa.text(
            f"""
            UPDATE analysis_content_results AS result
            SET analysis_run_id = request.run_id,
                generation_config_hash = '{_EMPTY_CONFIG_SHA256}'
            FROM analysis_content_requests AS request
            WHERE request.job_id = result.job_id
            """
        )
    )
    connection = op.get_bind()
    unmatched = connection.scalar(
        sa.text("SELECT count(*) FROM analysis_content_results WHERE analysis_run_id IS NULL")
    )
    if unmatched:
        raise RuntimeError("存在无法映射到 Analysis Request 的历史 Result，停止 0027 回填")

    op.alter_column("analysis_content_requests", "run_id", nullable=False)
    op.alter_column("analysis_content_requests", "shard_no", nullable=False)
    op.alter_column("analysis_content_results", "analysis_run_id", nullable=False)
    op.alter_column("analysis_content_results", "generation_config_hash", nullable=False)
    op.create_foreign_key(
        op.f("fk_analysis_content_requests_run_id_analysis_content_runs"),
        "analysis_content_requests",
        "analysis_content_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        op.f("uq_analysis_content_requests_run_shard"),
        "analysis_content_requests",
        ["run_id", "shard_no"],
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_requests_shard_no_nonnegative"),
        "analysis_content_requests",
        "shard_no >= 0",
    )
    op.create_foreign_key(
        op.f("fk_analysis_content_results_analysis_run_id_analysis_content_runs"),
        "analysis_content_results",
        "analysis_content_runs",
        ["analysis_run_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_generation_config_hash_length"),
        "analysis_content_results",
        "char_length(generation_config_hash) = 64",
    )
    op.drop_constraint(
        op.f("uq_analysis_content_results_identity"),
        "analysis_content_results",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_analysis_content_results_identity"),
        "analysis_content_results",
        ["analysis_run_id", "content_id", "content_version"],
    )


def downgrade() -> None:
    duplicate = op.get_bind().scalar(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT
                    content_id, content_version, input_hash, prompt_sha256,
                    taxonomy_sha256, model_provider, model
                FROM analysis_content_results
                GROUP BY
                    content_id, content_version, input_hash, prompt_sha256,
                    taxonomy_sha256, model_provider, model
                HAVING count(*) > 1
            ) AS repeated
            """
        )
    )
    if duplicate:
        raise RuntimeError(
            "0027 之后已产生跨 Run 重复结果；为避免删除历史，禁止直接降级，"
            "请先走独立数据保全/补偿方案"
        )
    op.drop_index(
        op.f("ix_analysis_content_run_targets_run_ordinal"),
        table_name="analysis_content_run_targets",
    )
    op.drop_table("analysis_content_run_targets")
    op.drop_constraint(
        op.f("ck_analysis_content_request_items_status_fields_consistent"),
        "analysis_content_request_items",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_request_items_status_allowed"),
        "analysis_content_request_items",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_request_items_status_allowed"),
        "analysis_content_request_items",
        "status in ('pending','succeeded','failed','stale')",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_request_items_status_fields_consistent"),
        "analysis_content_request_items",
        "(status = 'pending' and analysis_result_id is null and error_code is null) or "
        "(status = 'succeeded' and analysis_result_id is not null and error_code is null) or "
        "(status in ('failed','stale') and analysis_result_id is null and error_code is not null)",
    )
    op.drop_constraint(
        op.f("uq_analysis_content_results_identity"),
        "analysis_content_results",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_analysis_content_results_identity"),
        "analysis_content_results",
        [
            "content_id",
            "content_version",
            "input_hash",
            "prompt_sha256",
            "taxonomy_sha256",
            "model_provider",
            "model",
        ],
    )
    op.drop_constraint(
        op.f("ck_analysis_content_results_generation_config_hash_length"),
        "analysis_content_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_analysis_content_results_analysis_run_id_analysis_content_runs"),
        "analysis_content_results",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_requests_shard_no_nonnegative"),
        "analysis_content_requests",
        type_="check",
    )
    op.drop_constraint(
        op.f("uq_analysis_content_requests_run_shard"),
        "analysis_content_requests",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_analysis_content_requests_run_id_analysis_content_runs"),
        "analysis_content_requests",
        type_="foreignkey",
    )
    op.drop_column("analysis_content_results", "generation_config_hash")
    op.drop_column("analysis_content_results", "analysis_run_id")
    op.drop_column("analysis_content_requests", "shard_no")
    op.drop_column("analysis_content_requests", "run_id")
    op.drop_table("analysis_content_runs")
