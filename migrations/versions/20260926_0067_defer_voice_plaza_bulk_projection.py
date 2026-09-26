"""允许批量写事务把声音广场派生投影刷新延迟到事务尾部。

Revision ID: 20260926_0067
Revises: 20260925_0065
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0067"
down_revision: str | Sequence[str] | None = "20260925_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTENT_FACT_TABLES = (
    "content_versions",
    "analysis_content_results",
    "analysis_content_manual_overrides",
    "analysis_content_relevance_reviews",
    "content_brand_evidence",
    "content_vehicle_evidence",
    "historical_import_revocation_content_versions",
)


def _replace_visibility_function(*, replay_guard: bool) -> None:
    """使投影可见性与 Content Owner 的已撤回重筛来源语义一致。"""

    replay_clause = (
        """
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
        """
        if replay_guard
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
                                  SELECT 1 FROM historical_import_campaign_revocations AS revocation
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
                                  SELECT 1 FROM historical_import_campaign_revocations AS revocation
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
                                  SELECT 1 FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = run.data_import_campaign_id
                              )
                          )
                    )
                ) {replay_clause};
            $$
            """
        )
    )


def _replace_projection_triggers(*, deferred: bool) -> None:
    """只调整业务事实触发器；目录 Entry 的精确计数触发器继续同步执行。"""

    when = (
        "WHEN (current_setting('aima.defer_voice_plaza', true) IS DISTINCT FROM 'on')"
        if deferred
        else ""
    )
    for operation, relation in (
        ("insert", "NEW TABLE AS new_rows"),
        ("update", "OLD TABLE AS old_rows NEW TABLE AS new_rows"),
    ):
        name = f"trg_contents_voice_plaza_projection_{operation}_statement"
        op.execute(sa.text(f"DROP TRIGGER {name} ON contents"))
        op.execute(
            sa.text(
                f"CREATE TRIGGER {name} AFTER {operation.upper()} ON contents "
                f"REFERENCING {relation} FOR EACH STATEMENT {when} "
                "EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_statement()"
            )
        )
    for table_name in _CONTENT_FACT_TABLES:
        for operation, suffix, relation in (
            ("insert", "ins", "NEW TABLE AS new_rows"),
            ("update", "upd", "OLD TABLE AS old_rows NEW TABLE AS new_rows"),
            ("delete", "del", "OLD TABLE AS old_rows"),
        ):
            name = f"trg_vp_{table_name}_{suffix}"
            op.execute(sa.text(f"DROP TRIGGER {name} ON {table_name}"))
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {name} AFTER {operation.upper()} ON {table_name} "
                    f"REFERENCING {relation} FOR EACH STATEMENT {when} "
                    "EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement()"
                )
            )
    op.execute(
        sa.text("DROP TRIGGER trg_vp_content_contributions_ins ON content_source_contributions")
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_vp_content_contributions_ins "
            "AFTER INSERT ON content_source_contributions "
            f"REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT {when} "
            "EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement()"
        )
    )


def _repair_reverted_replay_projections() -> None:
    """只修复已有撤回归属的错误可见行，避免迁移时全表回填。"""

    op.execute(
        sa.text(
            """
            DO $repair$
            DECLARE
                content_ids uuid[];
                last_content_id uuid;
            BEGIN
                LOOP
                    SELECT array_agg(candidate.id ORDER BY candidate.id)
                      INTO content_ids
                    FROM (
                        SELECT owned.id
                        FROM contents AS owned
                        JOIN canonical_replay_all_requests AS replay
                          ON replay.id = owned.replay_visibility_owner_id
                        JOIN voice_plaza_content_projection AS projection
                          ON projection.content_id = owned.id
                        WHERE projection.is_visible
                          AND (last_content_id IS NULL OR owned.id > last_content_id)
                          AND (
                              replay.lifecycle_status = 'reverted'
                              OR EXISTS (
                                  SELECT 1 FROM canonical_replay_content_changes AS change
                                  WHERE change.all_request_id = replay.id
                                    AND change.content_id = owned.id
                                    AND change.reverted_at IS NOT NULL
                              )
                          )
                        ORDER BY owned.id
                        LIMIT 1000
                    ) AS candidate;
                    EXIT WHEN content_ids IS NULL;
                    PERFORM refresh_voice_plaza_content_projection_batch(content_ids);
                    last_content_id := content_ids[array_length(content_ids, 1)];
                END LOOP;
            END
            $repair$;
            """
        )
    )


def upgrade() -> None:
    op.create_index(
        "ix_canonical_replay_content_changes_reverted_visibility",
        "canonical_replay_content_changes",
        ["all_request_id", "content_id"],
        postgresql_where=sa.text("reverted_at IS NOT NULL"),
    )
    _replace_visibility_function(replay_guard=True)
    _replace_projection_triggers(deferred=True)
    _repair_reverted_replay_projections()


def downgrade() -> None:
    _replace_projection_triggers(deferred=False)
    _replace_visibility_function(replay_guard=False)
    op.drop_index(
        "ix_canonical_replay_content_changes_reverted_visibility",
        table_name="canonical_replay_content_changes",
    )
