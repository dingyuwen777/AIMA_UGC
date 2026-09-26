"""按 Source 增量维护历史导入 Chunk 进度并索引下一待处理项。

Revision ID: 20260926_0070
Revises: 20260926_0069
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0070"
down_revision: str | Sequence[str] | None = "20260926_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """以 Source 为分片累计终态行数，避免读时逐 Chunk 聚合。"""

    op.add_column(
        "historical_import_campaign_items",
        sa.Column("completed_row_count", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "historical_import_campaign_items",
        sa.Column("failed_chunk_count", sa.BigInteger(), nullable=False, server_default="0"),
    )
    invalid_chunk_count = op.get_bind().scalar(
        sa.text(
            """
            SELECT COUNT(*)
            FROM historical_import_campaign_items AS chunk
            LEFT JOIN historical_import_campaign_items AS source
              ON source.id = chunk.parent_item_id
            WHERE chunk.item_kind = 'chunk'
              AND (source.id IS NULL OR source.item_kind <> 'source_file'
                   OR source.campaign_id <> chunk.campaign_id)
            """
        )
    )
    if invalid_chunk_count:
        raise RuntimeError(
            "历史 Chunk 缺少同 Campaign 的 Source Item，无法安全建立进度计数"
        )
    op.create_check_constraint(
        op.f("ck_historical_import_campaign_items_completed_rows_nonnegative"),
        "historical_import_campaign_items",
        "completed_row_count >= 0",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaign_items_failed_chunks_nonnegative"),
        "historical_import_campaign_items",
        "failed_chunk_count >= 0",
    )
    op.create_index(
        "ix_historical_items_chunk_parent_status_ordinal",
        "historical_import_campaign_items",
        ["parent_item_id", "status", "ordinal"],
        postgresql_where=sa.text("item_kind = 'chunk'"),
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_import_campaign_items AS source
            SET completed_row_count = totals.completed_rows,
                failed_chunk_count = totals.failed_chunks
            FROM (
                SELECT parent_item_id,
                       COALESCE(SUM(row_count) FILTER (
                           WHERE status IN ('succeeded', 'failed', 'cancelled')
                       ), 0)::bigint AS completed_rows,
                       COUNT(*) FILTER (WHERE status = 'failed')::bigint AS failed_chunks
                FROM historical_import_campaign_items
                WHERE item_kind = 'chunk'
                GROUP BY parent_item_id
            ) AS totals
            WHERE source.id = totals.parent_item_id
              AND source.item_kind = 'source_file'
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION update_historical_source_progress_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM new_rows
                        WHERE item_kind = 'chunk'
                          AND status IN ('succeeded', 'failed', 'cancelled')
                    ) THEN
                        RETURN NULL;
                    END IF;
                    WITH delta AS (
                        SELECT parent_item_id,
                               SUM(row_count)::bigint AS completed_rows,
                               COUNT(*) FILTER (WHERE status = 'failed')::bigint
                                   AS failed_chunks
                        FROM new_rows
                        WHERE item_kind = 'chunk'
                          AND status IN ('succeeded', 'failed', 'cancelled')
                        GROUP BY parent_item_id
                        HAVING SUM(row_count) <> 0
                            OR COUNT(*) FILTER (WHERE status = 'failed') > 0
                    )
                    UPDATE historical_import_campaign_items AS source
                    SET completed_row_count = source.completed_row_count + delta.completed_rows,
                        failed_chunk_count = source.failed_chunk_count + delta.failed_chunks
                    FROM delta
                    WHERE source.id = delta.parent_item_id;
                ELSIF TG_OP = 'DELETE' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM old_rows
                        WHERE item_kind = 'chunk'
                          AND status IN ('succeeded', 'failed', 'cancelled')
                    ) THEN
                        RETURN NULL;
                    END IF;
                    WITH delta AS (
                        SELECT parent_item_id,
                               SUM(row_count)::bigint AS completed_rows,
                               COUNT(*) FILTER (WHERE status = 'failed')::bigint
                                   AS failed_chunks
                        FROM old_rows
                        WHERE item_kind = 'chunk'
                          AND status IN ('succeeded', 'failed', 'cancelled')
                        GROUP BY parent_item_id
                        HAVING SUM(row_count) <> 0
                            OR COUNT(*) FILTER (WHERE status = 'failed') > 0
                    )
                    UPDATE historical_import_campaign_items AS source
                    SET completed_row_count = source.completed_row_count - delta.completed_rows,
                        failed_chunk_count = source.failed_chunk_count - delta.failed_chunks
                    FROM delta
                    WHERE source.id = delta.parent_item_id;
                ELSE
                    IF NOT EXISTS (SELECT 1 FROM old_rows WHERE item_kind = 'chunk')
                       AND NOT EXISTS (SELECT 1 FROM new_rows WHERE item_kind = 'chunk') THEN
                        RETURN NULL;
                    END IF;
                    WITH delta AS (
                        SELECT parent_item_id,
                               SUM(completed_delta)::bigint AS completed_rows,
                               SUM(failed_delta)::bigint AS failed_chunks
                        FROM (
                            SELECT parent_item_id,
                                   -row_count AS completed_delta,
                                   CASE WHEN status = 'failed' THEN -1 ELSE 0 END
                                       AS failed_delta
                            FROM old_rows
                            WHERE item_kind = 'chunk'
                              AND status IN ('succeeded', 'failed', 'cancelled')
                            UNION ALL
                            SELECT parent_item_id,
                                   row_count AS completed_delta,
                                   CASE WHEN status = 'failed' THEN 1 ELSE 0 END
                                       AS failed_delta
                            FROM new_rows
                            WHERE item_kind = 'chunk'
                              AND status IN ('succeeded', 'failed', 'cancelled')
                        ) AS changes
                        GROUP BY parent_item_id
                        HAVING SUM(completed_delta) <> 0 OR SUM(failed_delta) <> 0
                    )
                    UPDATE historical_import_campaign_items AS source
                    SET completed_row_count = source.completed_row_count + delta.completed_rows,
                        failed_chunk_count = source.failed_chunk_count + delta.failed_chunks
                    FROM delta
                    WHERE source.id = delta.parent_item_id;
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    for operation, transition in (
        ("INSERT", "NEW TABLE AS new_rows"),
        ("UPDATE", "OLD TABLE AS old_rows NEW TABLE AS new_rows"),
        ("DELETE", "OLD TABLE AS old_rows"),
    ):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_historical_source_progress_{operation.lower()}
                AFTER {operation} ON historical_import_campaign_items
                REFERENCING {transition}
                FOR EACH STATEMENT
                EXECUTE FUNCTION update_historical_source_progress_statement()
                """
            )
        )


def downgrade() -> None:
    """移除派生计数；旧应用仍可从 Chunk 状态重算进度。"""

    for operation in ("INSERT", "UPDATE", "DELETE"):
        op.execute(
            sa.text(
                f"DROP TRIGGER trg_historical_source_progress_{operation.lower()} "
                "ON historical_import_campaign_items"
            )
        )
    op.execute(sa.text("DROP FUNCTION update_historical_source_progress_statement()"))
    op.drop_index(
        "ix_historical_items_chunk_parent_status_ordinal",
        table_name="historical_import_campaign_items",
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaign_items_failed_chunks_nonnegative"),
        "historical_import_campaign_items",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaign_items_completed_rows_nonnegative"),
        "historical_import_campaign_items",
        type_="check",
    )
    op.drop_column("historical_import_campaign_items", "failed_chunk_count")
    op.drop_column("historical_import_campaign_items", "completed_row_count")
