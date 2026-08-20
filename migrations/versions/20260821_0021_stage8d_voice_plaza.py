"""建立声音广场 Analysis 历史与 durable Excel Export。

Revision ID: 20260821_0021
Revises: 20260820_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0021"
down_revision: str | Sequence[str] | None = "20260820_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_content_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("prompt_sha256", sa.Text(), nullable=False),
        sa.Column("taxonomy_sha256", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version >= 1",
            name=op.f("ck_analysis_content_results_content_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(input_hash) = 64",
            name=op.f("ck_analysis_content_results_input_hash_sha256_length"),
        ),
        sa.CheckConstraint(
            "char_length(prompt_sha256) = 64",
            name=op.f("ck_analysis_content_results_prompt_sha256_length"),
        ),
        sa.CheckConstraint(
            "char_length(taxonomy_sha256) = 64",
            name=op.f("ck_analysis_content_results_taxonomy_sha256_length"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_analysis_content_results_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_analysis_content_results_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_content_results")),
        sa.UniqueConstraint(
            "content_id",
            "content_version",
            "input_hash",
            "prompt_sha256",
            "taxonomy_sha256",
            "model_provider",
            "model",
            name=op.f("uq_analysis_content_results_identity"),
        ),
    )
    op.create_table(
        "analysis_content_label_pairs",
        sa.Column("analysis_result_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("primary_label", sa.Text(), nullable=False),
        sa.Column("secondary_label", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0",
            name=op.f("ck_analysis_content_label_pairs_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "char_length(primary_label) > 0",
            name=op.f("ck_analysis_content_label_pairs_primary_label_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(secondary_label) > 0",
            name=op.f("ck_analysis_content_label_pairs_secondary_label_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_result_id"],
            ["analysis_content_results.id"],
            name=op.f(
                "fk_analysis_content_label_pairs_analysis_result_id_analysis_content_results"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "analysis_result_id",
            "ordinal",
            name=op.f("pk_analysis_content_label_pairs"),
        ),
        sa.UniqueConstraint(
            "analysis_result_id",
            "primary_label",
            "secondary_label",
            name=op.f("uq_analysis_content_label_pairs_value"),
        ),
    )
    op.create_table(
        "analysis_content_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column(
            "filter_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope in ('query','selected')",
            name=op.f("ck_analysis_content_requests_scope_allowed"),
        ),
        sa.CheckConstraint(
            "target_count > 0",
            name=op.f("ck_analysis_content_requests_target_count_positive"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(filter_snapshot) = 'object'",
            name=op.f("ck_analysis_content_requests_filter_snapshot_object"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_analysis_content_requests_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_content_requests")),
        sa.UniqueConstraint("job_id", name=op.f("uq_analysis_content_requests_job_id")),
    )
    op.create_table(
        "analysis_content_request_items",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("analysis_result_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "content_version >= 1",
            name=op.f("ck_analysis_content_request_items_content_version_positive"),
        ),
        sa.CheckConstraint(
            "ordinal >= 0",
            name=op.f("ck_analysis_content_request_items_ordinal_nonnegative"),
        ),
        sa.CheckConstraint(
            "status in ('pending','succeeded','failed','stale')",
            name=op.f("ck_analysis_content_request_items_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' and analysis_result_id is null and error_code is null) or "
            "(status = 'succeeded' and analysis_result_id is not null and error_code is null) or "
            "(status in ('failed','stale') and analysis_result_id is null "
            "and error_code is not null)",
            name=op.f("ck_analysis_content_request_items_status_fields_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_result_id"],
            ["analysis_content_results.id"],
            name=op.f(
                "fk_analysis_content_request_items_analysis_result_id_analysis_content_results"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_analysis_content_request_items_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["analysis_content_requests.id"],
            name=op.f("fk_analysis_content_request_items_request_id_analysis_content_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "request_id", "content_id", name=op.f("pk_analysis_content_request_items")
        ),
        sa.UniqueConstraint(
            "request_id",
            "ordinal",
            name=op.f("uq_analysis_content_request_items_ordinal"),
        ),
    )
    op.create_table(
        "reporting_data_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("request_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("format = 'xlsx'", name=op.f("ck_reporting_data_exports_format_xlsx")),
        sa.CheckConstraint(
            "jsonb_typeof(request_snapshot) = 'object'",
            name=op.f("ck_reporting_data_exports_request_snapshot_object"),
        ),
        sa.CheckConstraint(
            "stats is null or jsonb_typeof(stats) = 'object'",
            name=op.f("ck_reporting_data_exports_stats_object"),
        ),
        sa.CheckConstraint(
            "(artifact_id is null and stats is null and completed_at is null) or "
            "(artifact_id is not null and stats is not null and completed_at is not null)",
            name=op.f("ck_reporting_data_exports_completion_fields_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_reporting_data_exports_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_reporting_data_exports_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reporting_data_exports")),
        sa.UniqueConstraint("artifact_id", name=op.f("uq_reporting_data_exports_artifact_id")),
        sa.UniqueConstraint("job_id", name=op.f("uq_reporting_data_exports_job_id")),
    )
    op.create_table(
        "reporting_data_export_items",
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "content_version >= 1",
            name=op.f("ck_reporting_data_export_items_content_version_positive"),
        ),
        sa.CheckConstraint(
            "ordinal >= 0",
            name=op.f("ck_reporting_data_export_items_ordinal_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_reporting_data_export_items_content_id_contents"),
        ),
        sa.ForeignKeyConstraint(
            ["export_id"],
            ["reporting_data_exports.id"],
            name=op.f("fk_reporting_data_export_items_export_id_reporting_data_exports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "export_id", "content_id", name=op.f("pk_reporting_data_export_items")
        ),
        sa.UniqueConstraint(
            "export_id", "ordinal", name=op.f("uq_reporting_data_export_items_ordinal")
        ),
    )


def downgrade() -> None:
    op.drop_table("reporting_data_export_items")
    op.drop_table("reporting_data_exports")
    op.drop_table("analysis_content_request_items")
    op.drop_table("analysis_content_requests")
    op.drop_table("analysis_content_label_pairs")
    op.drop_table("analysis_content_results")
