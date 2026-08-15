"""建立 Stage 7 Provider 多级预算账本。

Revision ID: 20260815_0012
Revises: 20260815_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0012"
down_revision: str | Sequence[str] | None = "20260815_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.add_column(
        "provider_requests",
        sa.Column("provider_config_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_provider_requests_provider_config_id_provider_configs"),
        "provider_requests",
        "provider_configs",
        ["provider_config_id"],
        ["id"],
    )
    _replace_provider_request_lineage_trigger(include_provider_config=True)

    op.create_table(
        "provider_budget_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_config_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Uuid()),
        sa.Column("content_id", sa.Uuid()),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "reserved_amount",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "settled_amount",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "unknown_amount",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_config_id"],
            ["provider_configs.id"],
            name=op.f("fk_provider_budget_accounts_provider_config_id_provider_configs"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["collection_runs.id"],
            name=op.f("fk_provider_budget_accounts_run_id_collection_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_provider_budget_accounts_content_id_contents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_budget_accounts")),
        sa.UniqueConstraint(
            "provider_config_id",
            "scope_key",
            "period_start",
            "dimension",
            "unit",
            name=op.f(
                "uq_provider_budget_accounts_provider_config_id_scope_key_period_start_dimension_unit"
            ),
        ),
        sa.CheckConstraint(
            "scope_type in ('global','run','run_comments','content_comments')",
            name=op.f("ck_provider_budget_accounts_scope_type_allowed"),
        ),
        sa.CheckConstraint(
            "period_end > period_start",
            name=op.f("ck_provider_budget_accounts_period_valid"),
        ),
        sa.CheckConstraint(
            "dimension in ('request_count','monetary_cost')",
            name=op.f("ck_provider_budget_accounts_dimension_allowed"),
        ),
        sa.CheckConstraint(
            "(dimension = 'request_count' and unit = 'request') or "
            "(dimension = 'monetary_cost' and unit ~ '^[A-Z]{3}$')",
            name=op.f("ck_provider_budget_accounts_dimension_unit_consistent"),
        ),
        sa.CheckConstraint(
            "limit_amount >= 0 and reserved_amount >= 0 and settled_amount >= 0 "
            "and unknown_amount >= 0",
            name=op.f("ck_provider_budget_accounts_amounts_nonnegative"),
        ),
        sa.CheckConstraint(
            "(scope_type = 'global' and run_id is null and content_id is null "
            "and scope_key = 'global') or "
            "(scope_type = 'run' and run_id is not null and content_id is null "
            "and scope_key = 'run:' || run_id::text) or "
            "(scope_type = 'run_comments' and run_id is not null and content_id is null "
            "and scope_key = 'run_comments:' || run_id::text) or "
            "(scope_type = 'content_comments' and content_id is not null and run_id is null "
            "and scope_key = 'content_comments:' || content_id::text)",
            name=op.f("ck_provider_budget_accounts_scope_identity_consistent"),
        ),
    )
    op.execute(
        """
        ALTER TABLE provider_budget_accounts
        ADD CONSTRAINT ex_provider_budget_accounts_no_overlap
        EXCLUDE USING gist (
            provider_config_id WITH =,
            scope_key WITH =,
            dimension WITH =,
            unit WITH =,
            tstzrange(period_start, period_end, '[)') WITH &&
        )
        """
    )
    op.create_index(
        "ix_provider_budget_accounts_provider_config_id_period",
        "provider_budget_accounts",
        ["provider_config_id", "period_start", "period_end"],
    )

    op.create_table(
        "provider_budget_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("budget_account_id", sa.Uuid(), nullable=False),
        sa.Column("provider_request_id", sa.Uuid(), nullable=False),
        sa.Column("provider_request_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("reserved_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("settled_amount", sa.Numeric(18, 6)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["budget_account_id"],
            ["provider_budget_accounts.id"],
            name=op.f(
                "fk_provider_budget_reservations_budget_account_id_provider_budget_accounts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["provider_request_id"],
            ["provider_requests.id"],
            name=op.f(
                "fk_provider_budget_reservations_provider_request_id_provider_requests"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["provider_request_attempt_id", "provider_request_id"],
            ["provider_request_attempts.id", "provider_request_attempts.provider_request_id"],
            name=op.f(
                "fk_provider_budget_reservations_provider_request_attempt_id_provider_request_attempts"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_budget_reservations")),
        sa.UniqueConstraint(
            "budget_account_id",
            "provider_request_attempt_id",
            name=op.f(
                "uq_provider_budget_reservations_budget_account_id_provider_request_attempt_id"
            ),
        ),
        sa.CheckConstraint(
            "reserved_amount >= 0 and (settled_amount is null or settled_amount >= 0)",
            name=op.f("ck_provider_budget_reservations_amounts_nonnegative"),
        ),
        sa.CheckConstraint(
            "status in ('reserved','settled','released','unknown')",
            name=op.f("ck_provider_budget_reservations_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status in ('reserved','unknown') and settled_amount is null) or "
            "(status = 'settled' and settled_amount is not null) or "
            "(status = 'released' and coalesce(settled_amount, 0) = 0)",
            name=op.f("ck_provider_budget_reservations_status_amount_consistent"),
        ),
    )
    op.create_index(
        "ix_provider_budget_reservations_attempt_id",
        "provider_budget_reservations",
        ["provider_request_attempt_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_budget_reservations_attempt_id",
        table_name="provider_budget_reservations",
    )
    op.drop_table("provider_budget_reservations")
    op.drop_index(
        "ix_provider_budget_accounts_provider_config_id_period",
        table_name="provider_budget_accounts",
    )
    op.drop_table("provider_budget_accounts")

    _replace_provider_request_lineage_trigger(include_provider_config=False)
    op.drop_constraint(
        op.f("fk_provider_requests_provider_config_id_provider_configs"),
        "provider_requests",
        type_="foreignkey",
    )
    op.drop_column("provider_requests", "provider_config_id")


def _replace_provider_request_lineage_trigger(*, include_provider_config: bool) -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_provider_request_lineage_immutable ON provider_requests")
    if include_provider_config:
        old_identity = "OLD.scope_id, OLD.provider_config_id, OLD.provider, OLD.operation"
        new_identity = "NEW.scope_id, NEW.provider_config_id, NEW.provider, NEW.operation"
        columns = "scope_id, provider_config_id, provider, operation"
    else:
        old_identity = "OLD.scope_id, OLD.provider, OLD.operation"
        new_identity = "NEW.scope_id, NEW.provider, NEW.operation"
        columns = "scope_id, provider, operation"
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION guard_provider_request_lineage()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF ROW({old_identity}) IS DISTINCT FROM ROW({new_identity})
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
        f"""
        CREATE TRIGGER trg_provider_request_lineage_immutable
        BEFORE UPDATE OF {columns}
        ON provider_requests
        FOR EACH ROW
        EXECUTE FUNCTION guard_provider_request_lineage()
        """
    )
