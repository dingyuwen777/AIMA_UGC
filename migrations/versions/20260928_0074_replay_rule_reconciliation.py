"""让成功的全历史重筛原子收敛当前业务有效结果。

Revision ID: 20260928_0074
Revises: 20260928_0073
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260928_0074"
down_revision: str | Sequence[str] | None = "20260928_0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_visibility_function(*, rule_filter: bool) -> None:
    """保持既有来源/撤回规则，只追加可回滚的最新重筛可见性门禁。"""

    rule_clause = (
        """
        AND EXISTS (
            SELECT 1
            FROM contents AS filtered_content
            WHERE filtered_content.id = p_content_id
              AND filtered_content.rule_filter_visible
        )
        """
        if rule_filter
        else ""
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION voice_plaza_has_active_source(p_content_id uuid)
            RETURNS boolean LANGUAGE sql STABLE AS $$
                SELECT (
                    EXISTS (
                        SELECT 1 FROM processing_import_batch_items AS ledger
                        JOIN historical_import_campaign_items AS campaign_item
                          ON campaign_item.id = ledger.campaign_item_id
                        WHERE ledger.content_id = p_content_id
                          AND NOT EXISTS (
                              SELECT 1 FROM historical_import_campaign_revocations AS revocation
                              WHERE revocation.campaign_id = campaign_item.campaign_id
                          )
                    )
                    OR EXISTS (
                        SELECT 1 FROM collection_candidate_ingestions AS ingestion
                        JOIN collection_candidates AS candidate
                          ON candidate.id = ingestion.candidate_id
                        JOIN provider_request_attempts AS attempt
                          ON attempt.id = candidate.provider_request_attempt_id
                        JOIN provider_requests AS request
                          ON request.id = attempt.provider_request_id
                        JOIN collection_scopes AS scope ON scope.id = request.scope_id
                        JOIN collection_runs AS run ON run.id = scope.run_id
                        WHERE ingestion.content_id = p_content_id
                          AND (
                              run.data_import_campaign_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = run.data_import_campaign_id
                              )
                          )
                    )
                    OR EXISTS (
                        SELECT 1 FROM content_versions AS version
                        JOIN provider_request_attempts AS attempt
                          ON attempt.id = version.provider_attempt_id
                        JOIN provider_requests AS request
                          ON request.id = attempt.provider_request_id
                        JOIN processing_import_batches AS batch
                          ON batch.id = request.import_batch_id
                        LEFT JOIN historical_import_campaign_items AS campaign_item
                          ON campaign_item.id = batch.historical_campaign_item_id
                        WHERE version.content_id = p_content_id
                          AND request.import_batch_id IS NOT NULL
                          AND (
                              batch.historical_campaign_item_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = campaign_item.campaign_id
                              )
                          )
                    )
                    OR EXISTS (
                        SELECT 1 FROM content_versions AS version
                        JOIN provider_request_attempts AS attempt
                          ON attempt.id = version.provider_attempt_id
                        JOIN provider_requests AS request
                          ON request.id = attempt.provider_request_id
                        JOIN collection_scopes AS scope ON scope.id = request.scope_id
                        JOIN collection_runs AS run ON run.id = scope.run_id
                        WHERE version.content_id = p_content_id
                          AND request.scope_id IS NOT NULL
                          AND (
                              run.data_import_campaign_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = run.data_import_campaign_id
                              )
                          )
                    )
                )
                AND NOT EXISTS (
                    SELECT 1 FROM contents AS owned
                    JOIN canonical_replay_all_requests AS replay
                      ON replay.id = owned.replay_visibility_owner_id
                    WHERE owned.id = p_content_id
                      AND (
                          replay.lifecycle_status = 'reverted'
                          OR EXISTS (
                              SELECT 1 FROM canonical_replay_content_changes AS change
                              WHERE change.all_request_id = replay.id
                                AND change.content_id = p_content_id
                                AND change.reverted_at IS NOT NULL
                          )
                      )
                )
                {rule_clause};
            $$
            """
        )
    )


def upgrade() -> None:
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("filter_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column(
            "reconciliation_status",
            sa.Text(),
            server_default="legacy",
            nullable=False,
        ),
    )
    op.add_column(
        "canonical_replay_all_requests",
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_filter_snapshot_object"),
        "canonical_replay_all_requests",
        "filter_snapshot is null or jsonb_typeof(filter_snapshot) = 'object'",
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_reconciliation_status_allowed"),
        "canonical_replay_all_requests",
        "reconciliation_status in ('legacy','pending','succeeded')",
    )
    op.create_check_constraint(
        op.f("ck_canonical_replay_all_requests_reconciliation_consistent"),
        "canonical_replay_all_requests",
        "(reconciliation_status = 'succeeded') = (reconciled_at is not null)",
    )

    op.add_column(
        "contents",
        sa.Column("rule_filter_visible", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "contents",
        sa.Column("latest_normal_filter_match_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_canonical_replay_content_changes_active_request_content",
        "canonical_replay_content_changes",
        ["all_request_id", "content_id"],
        unique=False,
        postgresql_where=sa.text("reverted_at IS NULL"),
    )
    op.create_table(
        "canonical_replay_filter_state",
        sa.Column("singleton", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("active_request_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "singleton",
            name=op.f("ck_canonical_replay_filter_state_singleton_true"),
        ),
        sa.ForeignKeyConstraint(
            ["active_request_id"],
            ["canonical_replay_all_requests.id"],
            name=op.f(
                "fk_canonical_replay_filter_state_active_request_id_canonical_replay_all_requests"
            ),
        ),
        sa.PrimaryKeyConstraint("singleton", name=op.f("pk_canonical_replay_filter_state")),
    )
    op.execute(
        sa.text(
            "INSERT INTO canonical_replay_filter_state(singleton, active_request_id, updated_at) "
            "VALUES (true, NULL, clock_timestamp())"
        )
    )
    _replace_visibility_function(rule_filter=True)


def downgrade() -> None:
    _replace_visibility_function(rule_filter=False)
    op.drop_table("canonical_replay_filter_state")
    op.drop_index(
        "ix_canonical_replay_content_changes_active_request_content",
        table_name="canonical_replay_content_changes",
    )
    op.drop_column("contents", "latest_normal_filter_match_at")
    op.drop_column("contents", "rule_filter_visible")
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_reconciliation_consistent"),
        "canonical_replay_all_requests",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_reconciliation_status_allowed"),
        "canonical_replay_all_requests",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_canonical_replay_all_requests_filter_snapshot_object"),
        "canonical_replay_all_requests",
        type_="check",
    )
    op.drop_column("canonical_replay_all_requests", "reconciled_at")
    op.drop_column("canonical_replay_all_requests", "reconciliation_status")
    op.drop_column("canonical_replay_all_requests", "filter_snapshot")
