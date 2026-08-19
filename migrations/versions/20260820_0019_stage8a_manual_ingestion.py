"""建立 Stage 8A Processing / Import Batch 与 File Provider 来源父级。

Revision ID: 20260820_0019
Revises: 20260818_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0019"
down_revision: str | Sequence[str] | None = "20260818_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("input_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "stats",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('processing','succeeded','failed')",
            name=op.f("ck_processing_import_batches_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["input_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_processing_import_batches_input_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_processing_import_batches_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_import_batches")),
        sa.UniqueConstraint("job_id", name=op.f("uq_processing_import_batches_job_id")),
    )
    op.add_column(
        "provider_requests",
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_provider_requests_import_batch_id_processing_import_batches"),
        "provider_requests",
        "processing_import_batches",
        ["import_batch_id"],
        ["id"],
    )
    op.alter_column(
        "provider_requests",
        "scope_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_check_constraint(
        op.f("ck_provider_requests_source_parent_exactly_one"),
        "provider_requests",
        "(scope_id is not null and import_batch_id is null) or "
        "(scope_id is null and import_batch_id is not null)",
    )
    op.create_unique_constraint(
        op.f("uq_provider_requests_import_batch_id_request_fingerprint"),
        "provider_requests",
        ["import_batch_id", "request_fingerprint"],
    )
    op.create_index(
        "ix_provider_requests_import_batch_id_created_at",
        "provider_requests",
        ["import_batch_id", "created_at"],
    )
    _replace_provider_request_lineage_guard(include_import_batch=True)


def downgrade() -> None:
    import_request_count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM provider_requests WHERE import_batch_id IS NOT NULL")
    )
    if int(import_request_count or 0) > 0:
        raise RuntimeError(
            "Stage 8A 已存在 File Import Provider Request，不能安全 downgrade；"
            "先保留当前 Revision 或显式迁移这些来源事实"
        )

    _replace_provider_request_lineage_guard(include_import_batch=False)
    op.drop_index(
        "ix_provider_requests_import_batch_id_created_at",
        table_name="provider_requests",
    )
    op.drop_constraint(
        op.f("uq_provider_requests_import_batch_id_request_fingerprint"),
        "provider_requests",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_provider_requests_source_parent_exactly_one"),
        "provider_requests",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_provider_requests_import_batch_id_processing_import_batches"),
        "provider_requests",
        type_="foreignkey",
    )
    op.drop_column("provider_requests", "import_batch_id")
    op.alter_column(
        "provider_requests",
        "scope_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.drop_table("processing_import_batches")


def _replace_provider_request_lineage_guard(*, include_import_batch: bool) -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_provider_request_lineage_immutable ON provider_requests"
    )
    op.execute("DROP FUNCTION IF EXISTS guard_provider_request_lineage()")

    if include_import_batch:
        old_row = "ROW(OLD.scope_id, OLD.import_batch_id, OLD.provider, OLD.operation)"
        new_row = "ROW(NEW.scope_id, NEW.import_batch_id, NEW.provider, NEW.operation)"
        update_columns = "scope_id, import_batch_id, provider, operation"
    else:
        old_row = "ROW(OLD.scope_id, OLD.provider, OLD.operation)"
        new_row = "ROW(NEW.scope_id, NEW.provider, NEW.operation)"
        update_columns = "scope_id, provider, operation"

    op.execute(
        f"""
        CREATE FUNCTION guard_provider_request_lineage()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF {old_row}
               IS DISTINCT FROM
               {new_row}
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
        BEFORE UPDATE OF {update_columns}
        ON provider_requests
        FOR EACH ROW
        EXECUTE FUNCTION guard_provider_request_lineage()
        """
    )
