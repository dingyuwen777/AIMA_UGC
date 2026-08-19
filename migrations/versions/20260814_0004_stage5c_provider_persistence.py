"""建立 Stage 5C Provider Request/Attempt 持久化基础。

Revision ID: 20260814_0004
Revises: 20260814_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0004"
down_revision: str | Sequence[str] | None = "20260814_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column("request_params", postgresql.JSONB(), nullable=False),
        sa.Column(
            "pagination_input",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "estimated_cost",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "actual_cost",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("cost_currency", sa.Text()),
        sa.Column("cost_unit", sa.Text()),
        sa.Column("unit_price_snapshot", sa.Numeric(18, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_detail", sa.Text()),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["collection_scopes.id"],
            name=op.f("fk_provider_requests_scope_id_collection_scopes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_requests")),
        sa.UniqueConstraint(
            "scope_id",
            "request_fingerprint",
            name=op.f("uq_provider_requests_scope_id_request_fingerprint"),
        ),
        sa.CheckConstraint(
            "char_length(provider) > 0",
            name=op.f("ck_provider_requests_provider_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(operation) > 0",
            name=op.f("ck_provider_requests_operation_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(status) > 0",
            name=op.f("ck_provider_requests_status_nonempty"),
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_provider_requests_request_fingerprint_sha256"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(request_params) = 'object'",
            name=op.f("ck_provider_requests_request_params_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(pagination_input) = 'object'",
            name=op.f("ck_provider_requests_pagination_input_object"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_provider_requests_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "estimated_cost >= 0 and actual_cost >= 0 "
            "and (unit_price_snapshot is null or unit_price_snapshot >= 0)",
            name=op.f("ck_provider_requests_costs_nonnegative"),
        ),
        sa.CheckConstraint(
            "cost_currency is null or cost_currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_provider_requests_cost_currency_format"),
        ),
    )
    op.create_index(
        "ix_provider_requests_scope_id_created_at",
        "provider_requests",
        ["scope_id", "created_at"],
    )

    op.create_table(
        "provider_request_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_request_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("dispatch_status", sa.Text(), nullable=False),
        sa.Column("dispatch_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("http_status", sa.Integer()),
        sa.Column("external_request_id", sa.Text()),
        sa.Column("raw_artifact_id", sa.Uuid()),
        sa.Column(
            "estimated_cost",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "actual_cost",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("cost_currency", sa.Text()),
        sa.Column("cost_unit", sa.Text()),
        sa.Column("unit_price_snapshot", sa.Numeric(18, 6)),
        sa.Column("billing_status", sa.Text(), nullable=False),
        sa.Column(
            "potential_duplicate_charge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_request_id"],
            ["provider_requests.id"],
            name=op.f("fk_provider_request_attempts_provider_request_id_provider_requests"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_provider_request_attempts_raw_artifact_id_artifacts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_request_attempts")),
        sa.UniqueConstraint(
            "provider_request_id",
            "attempt_no",
            name=op.f("uq_provider_request_attempts_provider_request_id_attempt_no"),
        ),
        sa.UniqueConstraint(
            "id",
            "provider_request_id",
            name=op.f("uq_provider_request_attempts_id_provider_request_id"),
        ),
        sa.CheckConstraint(
            "attempt_no >= 1",
            name=op.f("ck_provider_request_attempts_attempt_no_positive"),
        ),
        sa.CheckConstraint(
            "dispatch_status in ('reserved','dispatching','completed','not_sent','unknown')",
            name=op.f("ck_provider_request_attempts_dispatch_status_allowed"),
        ),
        sa.CheckConstraint(
            "(dispatch_status = 'reserved' and dispatch_started_at is null "
            "and completed_at is null) or "
            "(dispatch_status = 'dispatching' and dispatch_started_at is not null "
            "and completed_at is null) or "
            "(dispatch_status = 'not_sent' and dispatch_started_at is null "
            "and completed_at is not null) or "
            "(dispatch_status in ('completed','unknown') and dispatch_started_at is not null "
            "and completed_at is not null)",
            name=op.f("ck_provider_request_attempts_dispatch_times_consistent"),
        ),
        sa.CheckConstraint(
            "dispatch_status not in ('reserved','dispatching') or raw_artifact_id is null",
            name=op.f("ck_provider_request_attempts_unfinished_has_no_raw"),
        ),
        sa.CheckConstraint(
            "completed_at is null or completed_at >= created_at",
            name=op.f("ck_provider_request_attempts_completed_after_created"),
        ),
        sa.CheckConstraint(
            "dispatch_started_at is null or completed_at is null "
            "or completed_at >= dispatch_started_at",
            name=op.f("ck_provider_request_attempts_completed_after_dispatch"),
        ),
        sa.CheckConstraint(
            "http_status is null or http_status between 100 and 599",
            name=op.f("ck_provider_request_attempts_http_status_range"),
        ),
        sa.CheckConstraint(
            "billing_status in ('not_billable','estimated','confirmed','unknown')",
            name=op.f("ck_provider_request_attempts_billing_status_allowed"),
        ),
        sa.CheckConstraint(
            "estimated_cost >= 0 and actual_cost >= 0 "
            "and (unit_price_snapshot is null or unit_price_snapshot >= 0)",
            name=op.f("ck_provider_request_attempts_costs_nonnegative"),
        ),
        sa.CheckConstraint(
            "cost_currency is null or cost_currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_provider_request_attempts_cost_currency_format"),
        ),
        sa.CheckConstraint(
            "billing_status <> 'not_billable' or "
            "(estimated_cost = 0 and actual_cost = 0 "
            "and coalesce(unit_price_snapshot, 0) = 0)",
            name=op.f("ck_provider_request_attempts_not_billable_has_zero_cost"),
        ),
        sa.CheckConstraint(
            "billing_status <> 'confirmed' or cost_currency is not null",
            name=op.f("ck_provider_request_attempts_confirmed_has_currency"),
        ),
        sa.CheckConstraint(
            "dispatch_status <> 'not_sent' or "
            "(billing_status = 'not_billable' and potential_duplicate_charge = false "
            "and error_code is not null and error_detail is not null)",
            name=op.f("ck_provider_request_attempts_not_sent_consistent"),
        ),
        sa.CheckConstraint(
            "dispatch_status <> 'unknown' or "
            "(billing_status = 'unknown' and potential_duplicate_charge = true "
            "and error_code is not null and error_detail is not null)",
            name=op.f("ck_provider_request_attempts_unknown_consistent"),
        ),
    )
    op.create_index(
        "ix_provider_attempts_dispatch_status_started_at",
        "provider_request_attempts",
        ["dispatch_status", "dispatch_started_at"],
    )
    op.create_index(
        "ix_provider_request_attempts_completed_at",
        "provider_request_attempts",
        ["completed_at"],
    )

    _create_lineage_triggers()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_provider_attempt_lineage_immutable ON provider_request_attempts"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_provider_request_lineage_immutable ON provider_requests")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_collection_scope_provider_identity_immutable "
        "ON collection_scopes"
    )
    op.execute("DROP FUNCTION IF EXISTS guard_provider_attempt_lineage()")
    op.execute("DROP FUNCTION IF EXISTS guard_provider_request_lineage()")
    op.execute("DROP FUNCTION IF EXISTS guard_collection_scope_provider_identity()")
    op.drop_index(
        "ix_provider_request_attempts_completed_at",
        table_name="provider_request_attempts",
    )
    op.drop_index(
        "ix_provider_attempts_dispatch_status_started_at",
        table_name="provider_request_attempts",
    )
    op.drop_table("provider_request_attempts")
    op.drop_index("ix_provider_requests_scope_id_created_at", table_name="provider_requests")
    op.drop_table("provider_requests")


def _create_lineage_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_collection_scope_provider_identity()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF ROW(OLD.run_id, OLD.platform, OLD.source_type, OLD.source_value,
                   OLD.operation_group)
               IS DISTINCT FROM
               ROW(NEW.run_id, NEW.platform, NEW.source_type, NEW.source_value,
                   NEW.operation_group)
               AND EXISTS (
                   SELECT 1
                   FROM provider_requests
                   WHERE scope_id = OLD.id
               ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Collection Scope 已有 Provider Request，来源身份不可修改';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_collection_scope_provider_identity_immutable
        BEFORE UPDATE OF run_id, platform, source_type, source_value, operation_group
        ON collection_scopes
        FOR EACH ROW
        EXECUTE FUNCTION guard_collection_scope_provider_identity()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_provider_request_lineage()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF ROW(OLD.scope_id, OLD.provider, OLD.operation)
               IS DISTINCT FROM
               ROW(NEW.scope_id, NEW.provider, NEW.operation)
               AND EXISTS (
                   SELECT 1
                   FROM provider_request_attempts
                   WHERE provider_request_id = OLD.id
               ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Provider Request 已有 Attempt，来源身份不可修改';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_provider_request_lineage_immutable
        BEFORE UPDATE OF scope_id, provider, operation
        ON provider_requests
        FOR EACH ROW
        EXECUTE FUNCTION guard_provider_request_lineage()
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_provider_attempt_lineage()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.dispatch_status <> 'reserved'
               AND ROW(OLD.provider_request_id, OLD.raw_artifact_id)
                   IS DISTINCT FROM
                   ROW(NEW.provider_request_id, NEW.raw_artifact_id) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Provider Attempt 离开 reserved 后来源引用不可修改';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_provider_attempt_lineage_immutable
        BEFORE UPDATE OF provider_request_id, raw_artifact_id
        ON provider_request_attempts
        FOR EACH ROW
        EXECUTE FUNCTION guard_provider_attempt_lineage()
        """
    )
