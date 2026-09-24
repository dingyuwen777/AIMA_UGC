"""将声音广场同步从逐行触发改为语句级集合刷新。

Revision ID: 20260924_0061
Revises: 20260923_0060
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0061"
down_revision: str | Sequence[str] | None = "20260923_0060"
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
_CATALOG_TABLES = ("vehicle_brands", "vehicle_models")


def _drop_row_triggers() -> None:
    """删除 0054 建立的逐行触发器，函数保留给 downgrade 复用。"""

    for table_name in _CATALOG_TABLES:
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_voice_plaza_projection ON {table_name}"
            )
        )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_content_contributions_voice_plaza_projection "
            "ON content_source_contributions"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_analysis_labels_voice_plaza_projection "
            "ON analysis_content_label_pairs"
        )
    )
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_contents_voice_plaza_projection ON contents"))
    for table_name in _CONTENT_FACT_TABLES:
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_voice_plaza_projection ON {table_name}"
            )
        )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_voice_plaza_filter_catalog_entry_delta "
            "ON voice_plaza_filter_catalog_entries"
        )
    )


def _create_statement_functions() -> None:
    """建立消费 transition table 的集合刷新函数。"""

    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_visibility_batch(p_content_ids uuid[])
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            DECLARE
                changed_content_ids uuid[];
            BEGIN
                SELECT array_agg(candidate.content_id)
                INTO changed_content_ids
                FROM (
                    SELECT DISTINCT unnest(p_content_ids) AS content_id
                ) AS candidate
                LEFT JOIN voice_plaza_content_projection AS projection
                  ON projection.content_id = candidate.content_id
                WHERE projection.content_id IS NULL
                   OR projection.is_visible IS DISTINCT FROM
                      voice_plaza_has_active_source(candidate.content_id);

                IF COALESCE(cardinality(changed_content_ids), 0) > 0 THEN
                    PERFORM refresh_voice_plaza_content_projection_batch(changed_content_ids);
                END IF;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_vehicle_dimensions_batch(p_content_ids uuid[])
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            DECLARE
                missing_content_ids uuid[];
            BEGIN
                SELECT array_agg(candidate.content_id)
                INTO missing_content_ids
                FROM (
                    SELECT DISTINCT unnest(p_content_ids) AS content_id
                ) AS candidate
                LEFT JOIN voice_plaza_content_projection AS projection
                  ON projection.content_id = candidate.content_id
                WHERE projection.content_id IS NULL;

                IF COALESCE(cardinality(missing_content_ids), 0) > 0 THEN
                    PERFORM refresh_voice_plaza_content_projection_batch(missing_content_ids);
                END IF;

                WITH target AS (
                    SELECT DISTINCT unnest(p_content_ids) AS content_id
                ),
                dimensions AS (
                    SELECT
                        target.content_id,
                        COALESCE(brands.brand_ids, '{}'::uuid[]) AS brand_ids,
                        COALESCE(vehicles.vehicle_model_ids, '{}'::uuid[])
                            AS vehicle_model_ids,
                        CASE
                            WHEN COALESCE(brands.role_count, 0) = 0 THEN 'none_detected'
                            WHEN brands.role_count > 1 THEN 'mixed'
                            WHEN brands.has_owned THEN 'owned_only'
                            WHEN brands.has_competitor THEN 'competitor_only'
                            ELSE 'other_only'
                        END AS competition_scope
                    FROM target
                    LEFT JOIN LATERAL (
                        SELECT
                            array_agg(DISTINCT evidence.brand_id)
                                FILTER (WHERE evidence.brand_id IS NOT NULL) AS brand_ids,
                            count(DISTINCT brand.role) AS role_count,
                            bool_or(brand.role = 'owned') AS has_owned,
                            bool_or(brand.role = 'competitor') AS has_competitor
                        FROM content_brand_evidence AS evidence
                        JOIN vehicle_brands AS brand ON brand.id = evidence.brand_id
                        JOIN contents AS content ON content.id = target.content_id
                        WHERE evidence.content_id = target.content_id
                          AND evidence.content_version = content.current_version
                          AND evidence.is_active
                    ) AS brands ON true
                    LEFT JOIN LATERAL (
                        SELECT array_agg(DISTINCT COALESCE(model.merged_into_id, model.id))
                            FILTER (WHERE model.id IS NOT NULL) AS vehicle_model_ids
                        FROM content_vehicle_evidence AS evidence
                        JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                        JOIN contents AS content ON content.id = target.content_id
                        WHERE evidence.content_id = target.content_id
                          AND evidence.content_version = content.current_version
                          AND evidence.is_active
                    ) AS vehicles ON true
                )
                UPDATE voice_plaza_content_projection AS projection
                SET brand_ids = dimensions.brand_ids,
                    vehicle_model_ids = dimensions.vehicle_model_ids,
                    competition_scope = dimensions.competition_scope,
                    updated_at = clock_timestamp()
                FROM dimensions
                WHERE projection.content_id = dimensions.content_id;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_content_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                affected_content_ids uuid[];
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    SELECT array_agg(DISTINCT id) INTO affected_content_ids FROM new_rows;
                ELSE
                    SELECT array_agg(DISTINCT id) INTO affected_content_ids
                    FROM (
                        SELECT id FROM new_rows
                        UNION
                        SELECT id FROM old_rows
                    ) AS changed;
                END IF;
                IF COALESCE(cardinality(affected_content_ids), 0) > 0 THEN
                    PERFORM refresh_voice_plaza_content_projection_batch(affected_content_ids);
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                affected_content_ids uuid[];
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    SELECT array_agg(DISTINCT content_id)
                    INTO affected_content_ids FROM new_rows;
                ELSIF TG_OP = 'DELETE' THEN
                    SELECT array_agg(DISTINCT content_id)
                    INTO affected_content_ids FROM old_rows;
                ELSE
                    SELECT array_agg(DISTINCT content_id) INTO affected_content_ids
                    FROM (
                        SELECT content_id FROM new_rows
                        UNION
                        SELECT content_id FROM old_rows
                    ) AS changed;
                END IF;
                IF COALESCE(cardinality(affected_content_ids), 0) > 0 THEN
                    IF TG_TABLE_NAME IN (
                        'content_versions',
                        'historical_import_revocation_content_versions',
                        'content_source_contributions'
                    ) THEN
                        PERFORM refresh_voice_plaza_visibility_batch(affected_content_ids);
                    ELSIF TG_TABLE_NAME IN (
                        'content_brand_evidence',
                        'content_vehicle_evidence'
                    ) THEN
                        PERFORM refresh_voice_plaza_vehicle_dimensions_batch(
                            affected_content_ids
                        );
                    ELSE
                        PERFORM refresh_voice_plaza_content_projection_batch(
                            affected_content_ids
                        );
                    END IF;
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_label_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                affected_content_ids uuid[];
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    SELECT array_agg(DISTINCT result.content_id)
                    INTO affected_content_ids
                    FROM new_rows AS changed
                    JOIN analysis_content_results AS result
                      ON result.id = changed.analysis_result_id;
                ELSIF TG_OP = 'DELETE' THEN
                    SELECT array_agg(DISTINCT result.content_id)
                    INTO affected_content_ids
                    FROM old_rows AS changed
                    JOIN analysis_content_results AS result
                      ON result.id = changed.analysis_result_id;
                ELSE
                    SELECT array_agg(DISTINCT result.content_id)
                    INTO affected_content_ids
                    FROM (
                        SELECT analysis_result_id FROM new_rows
                        UNION
                        SELECT analysis_result_id FROM old_rows
                    ) AS changed
                    JOIN analysis_content_results AS result
                      ON result.id = changed.analysis_result_id;
                END IF;
                IF COALESCE(cardinality(affected_content_ids), 0) > 0 THEN
                    PERFORM refresh_voice_plaza_content_projection_batch(affected_content_ids);
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_catalog_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                affected_content_ids uuid[];
            BEGIN
                IF TG_TABLE_NAME = 'vehicle_brands' THEN
                    SELECT array_agg(DISTINCT content_id) INTO affected_content_ids
                    FROM (
                        SELECT evidence.content_id
                        FROM content_brand_evidence AS evidence
                        WHERE evidence.brand_id IN (
                            SELECT id FROM new_rows UNION SELECT id FROM old_rows
                        )
                        UNION
                        SELECT evidence.content_id
                        FROM content_vehicle_evidence AS evidence
                        JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                        WHERE model.brand_id IN (
                            SELECT id FROM new_rows UNION SELECT id FROM old_rows
                        )
                    ) AS affected;
                ELSE
                    SELECT array_agg(DISTINCT evidence.content_id)
                    INTO affected_content_ids
                    FROM content_vehicle_evidence AS evidence
                    WHERE evidence.vehicle_model_id IN (
                        SELECT id FROM new_rows UNION SELECT id FROM old_rows
                    );
                END IF;
                IF COALESCE(cardinality(affected_content_ids), 0) > 0 THEN
                    PERFORM refresh_voice_plaza_vehicle_dimensions_batch(affected_content_ids);
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION voice_plaza_filter_catalog_insert_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                INSERT INTO voice_plaza_filter_catalog (
                    dimension, value, secondary_value, content_count, updated_at
                )
                SELECT
                    dimension,
                    value,
                    secondary_value,
                    count(*)::bigint,
                    clock_timestamp()
                FROM new_rows
                GROUP BY dimension, value, secondary_value
                ON CONFLICT (dimension, value, secondary_value) DO UPDATE
                SET content_count = (
                        voice_plaza_filter_catalog.content_count + EXCLUDED.content_count
                    ),
                    updated_at = EXCLUDED.updated_at;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION voice_plaza_filter_catalog_delete_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM 1
                FROM voice_plaza_filter_catalog AS catalog
                JOIN (
                    SELECT dimension, value, secondary_value
                    FROM old_rows
                    GROUP BY dimension, value, secondary_value
                ) AS removed
                  ON catalog.dimension = removed.dimension
                 AND catalog.value = removed.value
                 AND catalog.secondary_value = removed.secondary_value
                ORDER BY catalog.dimension, catalog.value, catalog.secondary_value
                FOR UPDATE OF catalog;

                DELETE FROM voice_plaza_filter_catalog AS catalog
                USING (
                    SELECT dimension, value, secondary_value, count(*)::bigint AS removed_count
                    FROM old_rows
                    GROUP BY dimension, value, secondary_value
                ) AS removed
                WHERE catalog.dimension = removed.dimension
                  AND catalog.value = removed.value
                  AND catalog.secondary_value = removed.secondary_value
                  AND catalog.content_count <= removed.removed_count;

                UPDATE voice_plaza_filter_catalog AS catalog
                SET content_count = catalog.content_count - removed.removed_count,
                    updated_at = clock_timestamp()
                FROM (
                    SELECT dimension, value, secondary_value, count(*)::bigint AS removed_count
                    FROM old_rows
                    GROUP BY dimension, value, secondary_value
                ) AS removed
                WHERE catalog.dimension = removed.dimension
                  AND catalog.value = removed.value
                  AND catalog.secondary_value = removed.secondary_value;
                RETURN NULL;
            END;
            $$
            """
        )
    )


def _create_statement_triggers() -> None:
    """为每种 DML 事件建立独立 transition-table 触发器。"""

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_contents_voice_plaza_projection_insert_statement
            AFTER INSERT ON contents
            REFERENCING NEW TABLE AS new_rows
            FOR EACH STATEMENT
            EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_statement()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_contents_voice_plaza_projection_update_statement
            AFTER UPDATE ON contents
            REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
            FOR EACH STATEMENT
            EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_statement()
            """
        )
    )
    for table_name in _CONTENT_FACT_TABLES:
        for operation, suffix, relation in (
            ("insert", "ins", "NEW TABLE AS new_rows"),
            ("update", "upd", "OLD TABLE AS old_rows NEW TABLE AS new_rows"),
            ("delete", "del", "OLD TABLE AS old_rows"),
        ):
            op.execute(
                sa.text(
                    f"""
                    CREATE TRIGGER trg_vp_{table_name}_{suffix}
                    AFTER {operation.upper()} ON {table_name}
                    REFERENCING {relation}
                    FOR EACH STATEMENT
                    EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement()
                    """
                )
            )
    for operation, relation in (
        ("insert", "NEW TABLE AS new_rows"),
        ("update", "OLD TABLE AS old_rows NEW TABLE AS new_rows"),
        ("delete", "OLD TABLE AS old_rows"),
    ):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_analysis_labels_voice_plaza_projection_{operation}_statement
                AFTER {operation.upper()} ON analysis_content_label_pairs
                REFERENCING {relation}
                FOR EACH STATEMENT
                EXECUTE FUNCTION refresh_voice_plaza_projection_from_label_statement()
                """
            )
        )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_vp_content_contributions_ins
            AFTER INSERT ON content_source_contributions
            REFERENCING NEW TABLE AS new_rows
            FOR EACH STATEMENT
            EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement()
            """
        )
    )
    for table_name in _CATALOG_TABLES:
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table_name}_voice_plaza_projection_update_statement
                AFTER UPDATE ON {table_name}
                REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
                FOR EACH STATEMENT
                EXECUTE FUNCTION refresh_voice_plaza_projection_from_catalog_statement()
                """
            )
        )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_voice_plaza_filter_catalog_entry_insert_statement
            AFTER INSERT ON voice_plaza_filter_catalog_entries
            REFERENCING NEW TABLE AS new_rows
            FOR EACH STATEMENT
            EXECUTE FUNCTION voice_plaza_filter_catalog_insert_statement()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_voice_plaza_filter_catalog_entry_delete_statement
            AFTER DELETE ON voice_plaza_filter_catalog_entries
            REFERENCING OLD TABLE AS old_rows
            FOR EACH STATEMENT
            EXECUTE FUNCTION voice_plaza_filter_catalog_delete_statement()
            """
        )
    )


def _drop_statement_triggers() -> None:
    """删除 0061 的语句级触发器。"""

    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_voice_plaza_filter_catalog_entry_delete_statement "
            "ON voice_plaza_filter_catalog_entries"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_voice_plaza_filter_catalog_entry_insert_statement "
            "ON voice_plaza_filter_catalog_entries"
        )
    )
    for table_name in reversed(_CATALOG_TABLES):
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS "
                f"trg_{table_name}_voice_plaza_projection_update_statement ON {table_name}"
            )
        )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS "
            "trg_vp_content_contributions_ins "
            "ON content_source_contributions"
        )
    )
    # 兼容 0061 开发阶段曾使用、会被 PostgreSQL 截断到 63 字节的旧草稿名。
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS "
            "trg_content_contributions_voice_plaza_projection_insert_statement "
            "ON content_source_contributions"
        )
    )
    for operation in ("delete", "update", "insert"):
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS "
                f"trg_analysis_labels_voice_plaza_projection_{operation}_statement "
                f"ON analysis_content_label_pairs"
            )
        )
    for table_name in reversed(_CONTENT_FACT_TABLES):
        for suffix in ("del", "upd", "ins"):
            op.execute(
                sa.text(f"DROP TRIGGER IF EXISTS trg_vp_{table_name}_{suffix} ON {table_name}")
            )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_contents_voice_plaza_projection_update_statement "
            "ON contents"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_contents_voice_plaza_projection_insert_statement "
            "ON contents"
        )
    )


def _create_row_triggers() -> None:
    """回滚时重建 0054 的逐行兼容触发器。"""

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_voice_plaza_filter_catalog_entry_delta
            AFTER INSERT OR DELETE ON voice_plaza_filter_catalog_entries
            FOR EACH ROW EXECUTE FUNCTION voice_plaza_filter_catalog_entry_delta()
            """
        )
    )
    for table_name in _CONTENT_FACT_TABLES:
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table_name}_voice_plaza_projection
                AFTER INSERT OR UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact()
                """
            )
        )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_contents_voice_plaza_projection
            AFTER INSERT OR UPDATE ON contents
            FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_content()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_analysis_labels_voice_plaza_projection
            AFTER INSERT OR UPDATE OR DELETE ON analysis_content_label_pairs
            FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_label()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_content_contributions_voice_plaza_projection
            AFTER INSERT ON content_source_contributions
            FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_contribution()
            """
        )
    )
    for table_name in _CATALOG_TABLES:
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table_name}_voice_plaza_projection
                AFTER UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_catalog()
                """
            )
        )


def upgrade() -> None:
    """以 transition table 合并同一 SQL 语句影响的 Content。"""

    _drop_row_triggers()
    _create_statement_functions()
    _create_statement_triggers()


def downgrade() -> None:
    """恢复 0054 的逐行同步实现，派生数据本身保持不变。"""

    _drop_statement_triggers()
    for function_name in (
        "voice_plaza_filter_catalog_delete_statement()",
        "voice_plaza_filter_catalog_insert_statement()",
        "refresh_voice_plaza_projection_from_catalog_statement()",
        "refresh_voice_plaza_projection_from_label_statement()",
        "refresh_voice_plaza_projection_from_content_fact_statement()",
        "refresh_voice_plaza_projection_from_content_statement()",
        "refresh_voice_plaza_vehicle_dimensions_batch(uuid[])",
        "refresh_voice_plaza_visibility_batch(uuid[])",
    ):
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {function_name}"))
    _create_row_triggers()
