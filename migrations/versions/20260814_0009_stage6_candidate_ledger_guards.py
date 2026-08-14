"""保护 Stage 6 Candidate 追加账本与成功结果完整性。

Revision ID: 20260814_0009
Revises: 20260814_0008
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260814_0009"
down_revision: str | Sequence[str] | None = "20260814_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_collection_candidate_ingestions_success_target_required"),
        "collection_candidate_ingestions",
        "result not in ('ingested','duplicate') or "
        "(target_type is not null and canonical_version is not null "
        "and canonical_identity is not null)",
    )
    op.execute(
        """
        CREATE FUNCTION reject_collection_ledger_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% 是追加账本，禁止 %', TG_TABLE_NAME, TG_OP;
        END; $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_collection_candidates_append_only
        BEFORE UPDATE OR DELETE ON collection_candidates
        FOR EACH ROW EXECUTE FUNCTION reject_collection_ledger_mutation();

        CREATE TRIGGER trg_collection_candidate_ingestions_append_only
        BEFORE UPDATE OR DELETE ON collection_candidate_ingestions
        FOR EACH ROW EXECUTE FUNCTION reject_collection_ledger_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_collection_candidate_ingestions_append_only
        ON collection_candidate_ingestions;
        DROP TRIGGER IF EXISTS trg_collection_candidates_append_only
        ON collection_candidates;
        DROP FUNCTION IF EXISTS reject_collection_ledger_mutation();
        """
    )
    op.drop_constraint(
        op.f("ck_collection_candidate_ingestions_success_target_required"),
        "collection_candidate_ingestions",
        type_="check",
    )
