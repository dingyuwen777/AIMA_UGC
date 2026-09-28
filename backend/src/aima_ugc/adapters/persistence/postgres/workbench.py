"""PostgreSQL 工作台只读聚合与用户布局持久化。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.contracts.workbench import WorkbenchLayoutModule, WorkbenchQuery
from aima_ugc.modules.workbench.tables import workbench_layouts_table


class WorkbenchLayoutRevisionConflict(RuntimeError):
    pass


class PostgresWorkbenchRepository:
    """读取当前可见 Content + active Scheme Result；布局是 Workbench 唯一写事实。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def stream_rows(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
        limit: int = 30,
    ) -> tuple[RowMapping, ...]:
        sql, params = self._base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        params["limit"] = limit
        return tuple(
            self._session.execute(
                text(
                    sql
                    + """
                    SELECT content_id, platform, author_display_name, published_at,
                           title, body_text, result_id, effective_sentiment,
                           effective_voice_type, effective_labels, vehicle_names
                    FROM base
                    WHERE effective_relevance IS DISTINCT FROM 'irrelevant'
                    ORDER BY published_at DESC NULLS LAST, content_id DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).mappings()
        )

    def trend_snapshot(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        previous_start_at: datetime,
        current_start_at: datetime,
        end_at: datetime,
    ) -> RowMapping:
        """一次恢复前后周期事实并返回趋势所需全部聚合。"""

        self._disable_snapshot_jit()
        sql, params = self._snapshot_base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            previous_start_at=previous_start_at,
            current_start_at=current_start_at,
            end_at=end_at,
        )
        return (
            self._session.execute(
                text(
                    sql
                    + """
                    , summary AS MATERIALIZED (
                        SELECT is_current,
                               COUNT(*)::bigint AS total_count,
                               COUNT(*) FILTER (WHERE result_id IS NOT NULL)::bigint
                                   AS analyzed_count,
                               COUNT(*) FILTER (
                                   WHERE result_id IS NOT NULL
                                     AND effective_relevance = 'relevant'
                               )::bigint AS relevant_count,
                               COUNT(*) FILTER (
                                   WHERE result_id IS NOT NULL
                                     AND effective_relevance = 'relevant'
                                     AND effective_sentiment = '正面'
                               )::bigint AS positive_count
                        FROM base
                        WHERE effective_relevance IS DISTINCT FROM 'irrelevant'
                        GROUP BY is_current
                    ), daily AS (
                        SELECT (published_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
                               COUNT(*)::bigint AS count
                        FROM base
                        WHERE is_current
                          AND effective_relevance IS DISTINCT FROM 'irrelevant'
                        GROUP BY day
                    ), sentiments AS (
                        SELECT effective_sentiment AS sentiment, COUNT(*)::bigint AS count
                        FROM base
                        WHERE is_current
                          AND result_id IS NOT NULL
                          AND effective_relevance = 'relevant'
                          AND effective_sentiment IS NOT NULL
                        GROUP BY effective_sentiment
                    )
                    /* workbench:trend-snapshot */
                    SELECT COALESCE(
                               (
                                   SELECT to_jsonb(summary) - 'is_current'
                                   FROM summary
                                   WHERE is_current
                               ),
                               jsonb_build_object(
                                   'total_count', 0,
                                   'analyzed_count', 0,
                                   'relevant_count', 0,
                                   'positive_count', 0
                               )
                           ) AS current_summary,
                           COALESCE(
                               (
                                   SELECT to_jsonb(summary) - 'is_current'
                                   FROM summary
                                   WHERE NOT is_current
                               ),
                               jsonb_build_object(
                                   'total_count', 0,
                                   'analyzed_count', 0,
                                   'relevant_count', 0,
                                   'positive_count', 0
                               )
                           ) AS previous_summary,
                           COALESCE(
                               (
                                   SELECT jsonb_agg(
                                       jsonb_build_object('day', day, 'count', count)
                                       ORDER BY day
                                   )
                                   FROM daily
                               ),
                               '[]'::jsonb
                           ) AS daily_counts,
                           COALESCE(
                               (
                                   SELECT jsonb_agg(
                                       jsonb_build_object(
                                           'sentiment', sentiment,
                                           'count', count
                                       ) ORDER BY sentiment
                                   )
                                   FROM sentiments
                               ),
                               '[]'::jsonb
                           ) AS sentiment_counts
                    """
                ),
                params,
            )
            .mappings()
            .one()
        )

    def mind_snapshot(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        previous_start_at: datetime,
        current_start_at: datetime,
        end_at: datetime,
    ) -> RowMapping:
        """一次恢复前后周期事实并返回心智所需全部聚合。"""

        self._disable_snapshot_jit()
        sql, params = self._snapshot_base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            previous_start_at=previous_start_at,
            current_start_at=current_start_at,
            end_at=end_at,
        )
        return (
            self._session.execute(
                text(
                    sql
                    + """
                    , summary AS MATERIALIZED (
                        SELECT is_current,
                               COUNT(*)::bigint AS total_count,
                               COUNT(*) FILTER (WHERE result_id IS NOT NULL)::bigint
                                   AS analyzed_count,
                               COUNT(*) FILTER (
                                   WHERE result_id IS NOT NULL
                                     AND effective_relevance = 'relevant'
                                     AND author_account_id IS NULL
                               )::bigint AS unidentified_content_count,
                               COUNT(DISTINCT author_account_id) FILTER (
                                   WHERE result_id IS NOT NULL
                                     AND effective_relevance = 'relevant'
                                     AND author_account_id IS NOT NULL
                               )::bigint AS identified_user_count
                        FROM base
                        WHERE effective_relevance IS DISTINCT FROM 'irrelevant'
                        GROUP BY is_current
                    ), expanded AS MATERIALIZED (
                        SELECT base.is_current,
                               base.content_id,
                               base.author_account_id,
                               base.effective_sentiment,
                               label.item ->> 'primary_label' AS primary_label,
                               label.item ->> 'secondary_label' AS secondary_label
                        FROM base
                        CROSS JOIN LATERAL jsonb_array_elements(base.effective_labels)
                            AS label(item)
                        WHERE base.result_id IS NOT NULL
                          AND base.effective_relevance = 'relevant'
                          AND label.item ->> 'primary_label' <> '无法分类'
                    ), primary_counts AS (
                        SELECT is_current,
                               primary_label,
                               COUNT(DISTINCT author_account_id) FILTER (
                                   WHERE author_account_id IS NOT NULL
                               )::bigint AS user_count,
                               COUNT(DISTINCT content_id)::bigint AS content_count,
                               COUNT(DISTINCT content_id) FILTER (
                                   WHERE effective_sentiment = '正面'
                               )::bigint AS positive_content_count
                        FROM expanded
                        GROUP BY is_current, primary_label
                    ), secondary_counts AS (
                        SELECT primary_label,
                               secondary_label,
                               COUNT(DISTINCT author_account_id) FILTER (
                                   WHERE author_account_id IS NOT NULL
                               )::bigint AS user_count
                        FROM expanded
                        WHERE is_current
                        GROUP BY primary_label, secondary_label
                    )
                    /* workbench:mind-snapshot */
                    SELECT COALESCE(
                               (
                                   SELECT to_jsonb(summary) - 'is_current'
                                   FROM summary
                                   WHERE is_current
                               ),
                               jsonb_build_object(
                                   'total_count', 0,
                                   'analyzed_count', 0,
                                   'unidentified_content_count', 0,
                                   'identified_user_count', 0
                               )
                           ) AS current_summary,
                           COALESCE(
                               (
                                   SELECT to_jsonb(summary) - 'is_current'
                                   FROM summary
                                   WHERE NOT is_current
                               ),
                               jsonb_build_object(
                                   'total_count', 0,
                                   'analyzed_count', 0,
                                   'unidentified_content_count', 0,
                                   'identified_user_count', 0
                               )
                           ) AS previous_summary,
                           COALESCE(
                               (
                                   SELECT jsonb_agg(
                                       to_jsonb(primary_counts) - 'is_current'
                                       ORDER BY user_count DESC, primary_label
                                   )
                                   FROM primary_counts
                                   WHERE is_current
                               ),
                               '[]'::jsonb
                           ) AS current_primary,
                           COALESCE(
                               (
                                   SELECT jsonb_agg(
                                       to_jsonb(primary_counts) - 'is_current'
                                       ORDER BY user_count DESC, primary_label
                                   )
                                   FROM primary_counts
                                   WHERE NOT is_current
                               ),
                               '[]'::jsonb
                           ) AS previous_primary,
                           COALESCE(
                               (
                                   SELECT jsonb_agg(
                                       to_jsonb(secondary_counts)
                                       ORDER BY primary_label, user_count DESC, secondary_label
                                   )
                                   FROM secondary_counts
                               ),
                               '[]'::jsonb
                           ) AS current_secondary
                    """
                ),
                params,
            )
            .mappings()
            .one()
        )

    def get_layout(self, principal_id: str) -> RowMapping | None:
        return (
            self._session.execute(
                workbench_layouts_table.select().where(
                    workbench_layouts_table.c.principal_id == principal_id
                )
            )
            .mappings()
            .one_or_none()
        )

    def save_layout(
        self,
        *,
        principal_id: str,
        expected_revision: int,
        modules: Sequence[WorkbenchLayoutModule],
        now: datetime,
    ) -> RowMapping:
        payload = [item.model_dump(mode="json") for item in modules]
        if expected_revision == 0:
            try:
                self._session.execute(
                    workbench_layouts_table.insert().values(
                        principal_id=principal_id,
                        schema_version=1,
                        revision=1,
                        layout=payload,
                        created_at=now,
                        updated_at=now,
                    )
                )
            except IntegrityError as exc:
                raise WorkbenchLayoutRevisionConflict from exc
        else:
            updated = self._session.execute(
                workbench_layouts_table.update()
                .where(
                    workbench_layouts_table.c.principal_id == principal_id,
                    workbench_layouts_table.c.revision == expected_revision,
                )
                .values(
                    revision=workbench_layouts_table.c.revision + 1,
                    layout=payload,
                    updated_at=now,
                )
                .returning(workbench_layouts_table.c.principal_id)
            ).scalar_one_or_none()
            if updated is None:
                raise WorkbenchLayoutRevisionConflict
        row = self.get_layout(principal_id)
        if row is None:
            raise RuntimeError("工作台布局保存后无法读取")
        return row

    def _base_sql(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[str, dict[str, Any]]:
        projection_clauses = [
            "projection.is_visible IS TRUE",
            "projection.published_at >= :start_at",
            "projection.published_at < :end_at",
        ]
        params: dict[str, Any] = {
            "active_scheme_version_id": active_scheme_version_id,
            "start_at": start_at,
            "end_at": end_at,
        }
        if query.platforms:
            projection_clauses.append("projection.platform = ANY(CAST(:platforms AS text[]))")
            params["platforms"] = list(query.platforms)
        if query.brand_ids:
            projection_clauses.append("projection.brand_ids && CAST(:brand_ids AS uuid[])")
            params["brand_ids"] = list(query.brand_ids)
        if query.vehicle_model_ids:
            projection_clauses.append(
                "projection.vehicle_model_ids && CAST(:vehicle_model_ids AS uuid[])"
            )
            params["vehicle_model_ids"] = list(query.vehicle_model_ids)
        effective_clauses = ["TRUE"]
        if query.voice_types:
            effective_clauses.append("effective_voice_type = ANY(CAST(:voice_types AS text[]))")
            params["voice_types"] = list(query.voice_types)
        if query.sentiments:
            effective_clauses.append("effective_sentiment = ANY(CAST(:sentiments AS text[]))")
            params["sentiments"] = list(query.sentiments)
        if query.primary_labels:
            effective_clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(effective_labels) AS f(item) "
                "WHERE f.item ->> 'primary_label' = ANY(CAST(:primary_labels AS text[])))"
            )
            params["primary_labels"] = list(query.primary_labels)
        if query.secondary_labels:
            effective_clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(effective_labels) AS f(item) "
                "WHERE f.item ->> 'secondary_label' = ANY(CAST(:secondary_labels AS text[])))"
            )
            params["secondary_labels"] = list(query.secondary_labels)

        projection_where_sql = "\n                  AND ".join(projection_clauses)
        effective_where_sql = "\n                  AND ".join(effective_clauses)
        return (
            f"""
            WITH source AS (
                SELECT projection.content_id,
                       projection.content_version,
                       projection.platform,
                       projection.published_at,
                       projection.brand_ids,
                       projection.vehicle_model_ids,
                       projection.is_visible,
                       content.title,
                       content.text AS body_text,
                       content.author_account_id,
                       COALESCE(
                           NULLIF(version.author_snapshot ->> 'display_name', ''),
                           account.display_name
                       ) AS author_display_name,
                       active_result.id AS result_id,
                       CASE
                           WHEN active_result.id IS NULL THEN NULL
                           WHEN review.decision = 'relevant' THEN 'relevant'
                           WHEN review.decision = 'irrelevant' THEN 'irrelevant'
                           ELSE active_result.relevance
                       END AS effective_relevance,
                       CASE
                           WHEN active_result.id IS NULL THEN NULL
                           WHEN manual.voice_type_locked THEN manual.voice_type
                           ELSE active_result.voice_type
                       END AS effective_voice_type,
                       CASE
                           WHEN active_result.id IS NULL THEN NULL
                           WHEN manual.sentiment_locked THEN manual.sentiment
                           ELSE active_result.sentiment
                       END AS effective_sentiment,
                       CASE
                           WHEN active_result.id IS NULL THEN '[]'::jsonb
                           WHEN manual.labels_locked THEN manual.labels
                           ELSE COALESCE(result_labels.items, '[]'::jsonb)
                       END AS effective_labels,
                       COALESCE(vehicle_names.names, ARRAY[]::text[]) AS vehicle_names
                FROM voice_plaza_content_projection AS projection
                JOIN contents AS content
                  ON content.id = projection.content_id
                 AND content.current_version = projection.content_version
                LEFT JOIN content_versions AS version
                  ON version.content_id = content.id
                 AND version.version_no = content.current_version
                LEFT JOIN accounts AS account ON account.id = content.author_account_id
                LEFT JOIN LATERAL (
                    SELECT result.*
                    FROM analysis_content_results AS result
                    JOIN analysis_content_runs AS run ON run.id = result.analysis_run_id
                    WHERE result.content_id = projection.content_id
                      AND result.content_version = projection.content_version
                      AND run.analysis_scheme_version_id = :active_scheme_version_id
                    ORDER BY run.sequence_no DESC, result.id DESC
                    LIMIT 1
                ) AS active_result ON TRUE
                LEFT JOIN LATERAL (
                    SELECT review.decision
                    FROM analysis_content_relevance_reviews AS review
                    WHERE review.content_id = projection.content_id
                      AND review.content_version = projection.content_version
                    ORDER BY review.review_no DESC, review.reviewed_at DESC, review.id DESC
                    LIMIT 1
                ) AS review ON TRUE
                LEFT JOIN analysis_content_manual_overrides AS manual
                  ON manual.content_id = projection.content_id
                 AND manual.content_version = projection.content_version
                LEFT JOIN LATERAL (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'primary_label', pair.primary_label,
                            'secondary_label', pair.secondary_label
                        ) ORDER BY pair.ordinal
                    ) AS items
                    FROM analysis_content_label_pairs AS pair
                    WHERE pair.analysis_result_id = active_result.id
                ) AS result_labels ON TRUE
                LEFT JOIN LATERAL (
                    SELECT array_agg(DISTINCT model.display_name ORDER BY model.display_name)
                        AS names
                    FROM content_vehicle_evidence AS evidence
                    JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                    WHERE evidence.content_id = projection.content_id
                      AND model.merged_into_id IS NULL
                ) AS vehicle_names ON TRUE
                WHERE {projection_where_sql}
            ),
            base AS (
                SELECT *
                FROM source
                WHERE {effective_where_sql}
            )
            """,
            params,
        )

    def _snapshot_base_sql(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        previous_start_at: datetime,
        current_start_at: datetime,
        end_at: datetime,
    ) -> tuple[str, dict[str, Any]]:
        """构建一次物化的前后周期有效分析事实，供单模块复用。"""

        projection_clauses = [
            "projection.is_visible IS TRUE",
            "projection.published_at >= :previous_start_at",
            "projection.published_at < :end_at",
        ]
        params: dict[str, Any] = {
            "active_scheme_version_id": active_scheme_version_id,
            "previous_start_at": previous_start_at,
            "current_start_at": current_start_at,
            "end_at": end_at,
        }
        if query.platforms:
            projection_clauses.append("projection.platform = ANY(CAST(:platforms AS text[]))")
            params["platforms"] = list(query.platforms)
        if query.brand_ids:
            projection_clauses.append("projection.brand_ids && CAST(:brand_ids AS uuid[])")
            params["brand_ids"] = list(query.brand_ids)
        if query.vehicle_model_ids:
            projection_clauses.append(
                "projection.vehicle_model_ids && CAST(:vehicle_model_ids AS uuid[])"
            )
            params["vehicle_model_ids"] = list(query.vehicle_model_ids)
        effective_clauses = ["TRUE"]
        if query.voice_types:
            effective_clauses.append("effective_voice_type = ANY(CAST(:voice_types AS text[]))")
            params["voice_types"] = list(query.voice_types)
        if query.sentiments:
            effective_clauses.append("effective_sentiment = ANY(CAST(:sentiments AS text[]))")
            params["sentiments"] = list(query.sentiments)
        if query.primary_labels:
            effective_clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(effective_labels) AS f(item) "
                "WHERE f.item ->> 'primary_label' = ANY(CAST(:primary_labels AS text[])))"
            )
            params["primary_labels"] = list(query.primary_labels)
        if query.secondary_labels:
            effective_clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(effective_labels) AS f(item) "
                "WHERE f.item ->> 'secondary_label' = ANY(CAST(:secondary_labels AS text[])))"
            )
            params["secondary_labels"] = list(query.secondary_labels)

        projection_where_sql = "\n                  AND ".join(projection_clauses)
        effective_where_sql = "\n                  AND ".join(effective_clauses)
        return (
            f"""
            WITH projection_scope AS NOT MATERIALIZED (
                SELECT projection.content_id,
                       projection.content_version,
                       projection.published_at,
                       content.author_account_id,
                       projection.analysis_result_id,
                       projection.effective_relevance,
                       projection.effective_voice_type,
                       projection.effective_sentiment,
                       projection.labels,
                       projected_run.analysis_scheme_version_id AS projected_scheme_version_id
                FROM voice_plaza_content_projection AS projection
                JOIN contents AS content
                  ON content.id = projection.content_id
                 AND content.current_version = projection.content_version
                LEFT JOIN analysis_content_results AS projected_result
                  ON projected_result.id = projection.analysis_result_id
                LEFT JOIN analysis_content_runs AS projected_run
                  ON projected_run.id = projected_result.analysis_run_id
                WHERE {projection_where_sql}
            ),
            fast_source AS (
                SELECT content_id,
                       published_at,
                       author_account_id,
                       analysis_result_id AS result_id,
                       effective_relevance,
                       effective_voice_type,
                       effective_sentiment,
                       labels AS effective_labels
                FROM projection_scope
                WHERE projected_scheme_version_id = :active_scheme_version_id
            ),
            fallback_source AS (
                SELECT scope.content_id,
                       scope.published_at,
                       scope.author_account_id,
                       fallback_result.id AS result_id,
                       CASE
                           WHEN fallback_result.id IS NULL THEN NULL
                           WHEN review.decision = 'relevant' THEN 'relevant'
                           WHEN review.decision = 'irrelevant' THEN 'irrelevant'
                           ELSE fallback_result.relevance
                       END AS effective_relevance,
                       CASE
                           WHEN fallback_result.id IS NULL THEN NULL
                           WHEN manual.voice_type_locked THEN manual.voice_type
                           ELSE fallback_result.voice_type
                       END AS effective_voice_type,
                       CASE
                           WHEN fallback_result.id IS NULL THEN NULL
                           WHEN manual.sentiment_locked THEN manual.sentiment
                           ELSE fallback_result.sentiment
                       END AS effective_sentiment,
                       CASE
                           WHEN fallback_result.id IS NULL THEN '[]'::jsonb
                           WHEN manual.labels_locked THEN COALESCE(manual.labels, '[]'::jsonb)
                           ELSE COALESCE(result_labels.items, '[]'::jsonb)
                       END AS effective_labels
                FROM projection_scope AS scope
                LEFT JOIN LATERAL (
                    SELECT result.*
                    FROM analysis_content_results AS result
                    JOIN analysis_content_runs AS run ON run.id = result.analysis_run_id
                    WHERE result.content_id = scope.content_id
                      AND result.content_version = scope.content_version
                      AND run.analysis_scheme_version_id = :active_scheme_version_id
                    ORDER BY run.sequence_no DESC, result.id DESC
                    LIMIT 1
                ) AS fallback_result ON TRUE
                LEFT JOIN LATERAL (
                    SELECT relevance_review.decision
                    FROM analysis_content_relevance_reviews AS relevance_review
                    WHERE relevance_review.content_id = scope.content_id
                      AND relevance_review.content_version = scope.content_version
                    ORDER BY relevance_review.review_no DESC,
                             relevance_review.reviewed_at DESC,
                             relevance_review.id DESC
                    LIMIT 1
                ) AS review ON fallback_result.id IS NOT NULL
                LEFT JOIN analysis_content_manual_overrides AS manual
                  ON fallback_result.id IS NOT NULL
                 AND manual.content_id = scope.content_id
                 AND manual.content_version = scope.content_version
                LEFT JOIN LATERAL (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'primary_label', pair.primary_label,
                            'secondary_label', pair.secondary_label
                        ) ORDER BY pair.ordinal
                    ) AS items
                    FROM analysis_content_label_pairs AS pair
                    WHERE pair.analysis_result_id = fallback_result.id
                ) AS result_labels ON fallback_result.id IS NOT NULL
                WHERE scope.projected_scheme_version_id IS DISTINCT FROM
                      :active_scheme_version_id
            ),
            source AS (
                SELECT * FROM fast_source
                UNION ALL
                SELECT * FROM fallback_source
            ),
            base AS MATERIALIZED (
                SELECT source.*,
                       source.published_at >= :current_start_at AS is_current
                FROM source
                WHERE {effective_where_sql}
            )
            """,
            params,
        )

    def _disable_snapshot_jit(self) -> None:
        """避免复杂回退分支的高估成本触发一次性请求的大额 JIT 编译。"""

        self._session.execute(text("SET LOCAL jit = off"))


__all__ = ["PostgresWorkbenchRepository", "WorkbenchLayoutRevisionConflict"]
