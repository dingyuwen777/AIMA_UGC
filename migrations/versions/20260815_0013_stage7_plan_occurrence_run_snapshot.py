"""建立 Stage 7 Plan、Occurrence 与 Run Snapshot 父事实。

Revision ID: 20260815_0013
Revises: 20260815_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0013"
down_revision: str | Sequence[str] | None = "20260815_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_expr", sa.Text()),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column(
            "schedule_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("misfire_policy", sa.Text(), nullable=False),
        sa.Column("max_catch_up_runs", sa.Integer(), nullable=False),
        sa.Column("detail_policy", sa.Text(), nullable=False),
        sa.Column("comment_policy", sa.Text(), nullable=False),
        sa.Column("request_budget", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_plans")),
        sa.UniqueConstraint("name", name=op.f("uq_collection_plans_name")),
        sa.CheckConstraint(
            "char_length(name) > 0",
            name=op.f("ck_collection_plans_name_nonempty"),
        ),
        sa.CheckConstraint(
            "schedule_expr is null or char_length(schedule_expr) > 0",
            name=op.f("ck_collection_plans_schedule_expr_nonempty"),
        ),
        sa.CheckConstraint(
            "timezone = 'Asia/Shanghai'",
            name=op.f("ck_collection_plans_timezone_first_release"),
        ),
        sa.CheckConstraint(
            "schedule_version >= 1",
            name=op.f("ck_collection_plans_schedule_version_positive"),
        ),
        sa.CheckConstraint(
            "char_length(misfire_policy) > 0",
            name=op.f("ck_collection_plans_misfire_policy_nonempty"),
        ),
        sa.CheckConstraint(
            "max_catch_up_runs >= 0",
            name=op.f("ck_collection_plans_max_catch_up_runs_nonnegative"),
        ),
        sa.CheckConstraint(
            "char_length(detail_policy) > 0",
            name=op.f("ck_collection_plans_detail_policy_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(comment_policy) > 0",
            name=op.f("ck_collection_plans_comment_policy_nonempty"),
        ),
        sa.CheckConstraint(
            "request_budget >= 0",
            name=op.f("ck_collection_plans_request_budget_nonnegative"),
        ),
    )

    op.create_table(
        "collection_plan_platforms",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("operations", sa.Text(), nullable=False),
        sa.Column("provider_config_id", sa.Uuid(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["collection_plans.id"],
            name=op.f("fk_collection_plan_platforms_plan_id_collection_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id"],
            ["provider_configs.id"],
            name=op.f("fk_collection_plan_platforms_provider_config_id_provider_configs"),
        ),
        sa.PrimaryKeyConstraint(
            "plan_id",
            "operations",
            name=op.f("pk_collection_plan_platforms"),
        ),
        sa.CheckConstraint(
            "char_length(operations) > 0",
            name=op.f("ck_collection_plan_platforms_platform_nonempty"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(config) = 'object'",
            name=op.f("ck_collection_plan_platforms_config_object"),
        ),
    )

    op.create_table(
        "collection_plan_keyword_packs",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("keyword_pack_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["collection_plans.id"],
            name=op.f("fk_collection_plan_keyword_packs_plan_id_collection_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["keyword_pack_id"],
            ["keyword_packs.id"],
            name=op.f("fk_collection_plan_keyword_packs_keyword_pack_id_keyword_packs"),
        ),
        sa.PrimaryKeyConstraint(
            "plan_id",
            "keyword_pack_id",
            name=op.f("pk_collection_plan_keyword_packs"),
        ),
    )

    op.create_table(
        "collection_schedule_occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("skip_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["collection_plans.id"],
            name=op.f("fk_collection_schedule_occurrences_plan_id_collection_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_collection_schedule_occurrences_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_schedule_occurrences")),
        sa.UniqueConstraint(
            "plan_id",
            "schedule_version",
            "scheduled_for",
            name=op.f("uq_collection_schedule_occurrences_plan_id_schedule_version_scheduled_for"),
        ),
        sa.UniqueConstraint(
            "job_id",
            name=op.f("uq_collection_schedule_occurrences_job_id"),
        ),
        sa.CheckConstraint(
            "schedule_version >= 1",
            name=op.f("ck_collection_schedule_occurrences_schedule_version_positive"),
        ),
        sa.CheckConstraint(
            "status in ('enqueued','skipped')",
            name=op.f("ck_collection_schedule_occurrences_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'enqueued' and job_id is not null and skip_reason is null) or "
            "(status = 'skipped' and job_id is null and skip_reason is not null "
            "and char_length(skip_reason) > 0)",
            name=op.f("ck_collection_schedule_occurrences_status_binding_consistent"),
        ),
    )

    op.add_column("collection_runs", sa.Column("manual_plan_id", sa.Uuid()))
    op.add_column("collection_runs", sa.Column("occurrence_id", sa.Uuid()))
    op.create_foreign_key(
        op.f("fk_collection_runs_manual_plan_id_collection_plans"),
        "collection_runs",
        "collection_plans",
        ["manual_plan_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_collection_runs_occurrence_id_collection_schedule_occurrences"),
        "collection_runs",
        "collection_schedule_occurrences",
        ["occurrence_id"],
        ["id"],
    )
    op.create_unique_constraint(
        op.f("uq_collection_runs_occurrence_id"),
        "collection_runs",
        ["occurrence_id"],
    )
    op.drop_constraint(
        op.f("ck_collection_runs_trigger_type_allowed"),
        "collection_runs",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_collection_runs_trigger_binding_consistent"),
        "collection_runs",
        "(trigger_type = 'scheduled' and occurrence_id is not null and manual_plan_id is null) "
        "or (trigger_type in ('manual','api','backfill') and occurrence_id is null)",
    )

    _create_occurrence_run_consistency_constraints()


def downgrade() -> None:
    _drop_occurrence_run_consistency_constraints()

    op.drop_constraint(
        op.f("ck_collection_runs_trigger_binding_consistent"),
        "collection_runs",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_collection_runs_trigger_type_allowed"),
        "collection_runs",
        "trigger_type in ('manual','api','backfill')",
    )
    op.drop_constraint(
        op.f("uq_collection_runs_occurrence_id"),
        "collection_runs",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_collection_runs_occurrence_id_collection_schedule_occurrences"),
        "collection_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_collection_runs_manual_plan_id_collection_plans"),
        "collection_runs",
        type_="foreignkey",
    )
    op.drop_column("collection_runs", "occurrence_id")
    op.drop_column("collection_runs", "manual_plan_id")

    op.drop_table("collection_schedule_occurrences")
    op.drop_table("collection_plan_keyword_packs")
    op.drop_table("collection_plan_platforms")
    op.drop_table("collection_plans")


def _create_occurrence_run_consistency_constraints() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION assert_collection_occurrence_run_consistency(
            occurrence_uuid uuid
        )
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            occurrence_status text;
            occurrence_job_id uuid;
            reverse_run_count integer;
            inconsistent_run_count integer;
        BEGIN
            IF occurrence_uuid IS NULL THEN
                RETURN;
            END IF;

            SELECT status, job_id
            INTO occurrence_status, occurrence_job_id
            FROM collection_schedule_occurrences
            WHERE id = occurrence_uuid;

            IF NOT FOUND THEN
                RETURN;
            END IF;

            SELECT
                count(*),
                count(*) FILTER (
                    WHERE job_id IS DISTINCT FROM occurrence_job_id
                    OR trigger_type <> 'scheduled'
                )
            INTO reverse_run_count, inconsistent_run_count
            FROM collection_runs
            WHERE occurrence_id = occurrence_uuid;

            IF occurrence_status = 'enqueued' THEN
                IF reverse_run_count <> 1 OR inconsistent_run_count <> 0 THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = 'enqueued Occurrence 必须恰有一个同 Job 的 scheduled Run';
                END IF;
            ELSIF occurrence_status = 'skipped' AND reverse_run_count <> 0 THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'skipped Collection Occurrence 不允许关联 Run';
            END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_collection_occurrence_run_consistency()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_TABLE_NAME = 'collection_runs' THEN
                IF TG_OP IN ('UPDATE', 'DELETE') THEN
                    PERFORM assert_collection_occurrence_run_consistency(OLD.occurrence_id);
                END IF;
                IF TG_OP IN ('INSERT', 'UPDATE')
                   AND (
                       TG_OP = 'INSERT'
                       OR NEW.occurrence_id IS DISTINCT FROM OLD.occurrence_id
                   ) THEN
                    PERFORM assert_collection_occurrence_run_consistency(NEW.occurrence_id);
                END IF;
            ELSE
                IF TG_OP = 'DELETE' THEN
                    PERFORM assert_collection_occurrence_run_consistency(OLD.id);
                ELSE
                    PERFORM assert_collection_occurrence_run_consistency(NEW.id);
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_collection_occurrence_run_consistency_occurrence
        AFTER INSERT OR UPDATE OR DELETE
        ON collection_schedule_occurrences
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_collection_occurrence_run_consistency()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_collection_occurrence_run_consistency_run
        AFTER INSERT OR UPDATE OR DELETE
        ON collection_runs
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_collection_occurrence_run_consistency()
        """
    )


def _drop_occurrence_run_consistency_constraints() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_collection_occurrence_run_consistency_run ON collection_runs"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_collection_occurrence_run_consistency_occurrence "
        "ON collection_schedule_occurrences"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_collection_occurrence_run_consistency()")
    op.execute("DROP FUNCTION IF EXISTS assert_collection_occurrence_run_consistency(uuid)")
