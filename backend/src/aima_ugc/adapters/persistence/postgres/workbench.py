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

    def period_summary(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
    ) -> RowMapping:
        sql, params = self._base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        return (
            self._session.execute(
                text(
                    sql
                    + """
                    SELECT COUNT(*)::bigint AS total_count,
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
                           )::bigint AS positive_count,
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
                    """
                ),
                params,
            )
            .mappings()
            .one()
        )

    def daily_counts(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[RowMapping, ...]:
        sql, params = self._base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        return tuple(
            self._session.execute(
                text(
                    sql
                    + """
                    SELECT (published_at AT TIME ZONE 'Asia/Shanghai')::date AS day,
                           COUNT(*)::bigint AS count
                    FROM base
                    WHERE effective_relevance IS DISTINCT FROM 'irrelevant'
                      AND published_at IS NOT NULL
                    GROUP BY day
                    ORDER BY day
                    """
                ),
                params,
            ).mappings()
        )

    def sentiment_counts(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[RowMapping, ...]:
        sql, params = self._base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        return tuple(
            self._session.execute(
                text(
                    sql
                    + """
                    SELECT effective_sentiment AS sentiment, COUNT(*)::bigint AS count
                    FROM base
                    WHERE result_id IS NOT NULL
                      AND effective_relevance = 'relevant'
                      AND effective_sentiment IS NOT NULL
                    GROUP BY effective_sentiment
                    ORDER BY effective_sentiment
                    """
                ),
                params,
            ).mappings()
        )

    def mind_counts(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[RowMapping, ...]:
        sql, params = self._base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        return tuple(
            self._session.execute(
                text(
                    sql
                    + """
                    SELECT label.item ->> 'primary_label' AS primary_label,
                           COUNT(DISTINCT author_account_id) FILTER (
                               WHERE author_account_id IS NOT NULL
                           )::bigint AS user_count,
                           COUNT(DISTINCT content_id)::bigint AS content_count,
                           COUNT(DISTINCT content_id) FILTER (
                               WHERE effective_sentiment = '正面'
                           )::bigint AS positive_content_count
                    FROM base
                    CROSS JOIN LATERAL jsonb_array_elements(effective_labels) AS label(item)
                    WHERE result_id IS NOT NULL
                      AND effective_relevance = 'relevant'
                      AND label.item ->> 'primary_label' <> '无法分类'
                    GROUP BY primary_label
                    ORDER BY user_count DESC, primary_label
                    """
                ),
                params,
            ).mappings()
        )

    def secondary_mind_counts(
        self,
        *,
        active_scheme_version_id: UUID,
        query: WorkbenchQuery,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[RowMapping, ...]:
        sql, params = self._base_sql(
            active_scheme_version_id=active_scheme_version_id,
            query=query,
            start_at=start_at,
            end_at=end_at,
        )
        return tuple(
            self._session.execute(
                text(
                    sql
                    + """
                    SELECT label.item ->> 'primary_label' AS primary_label,
                           label.item ->> 'secondary_label' AS secondary_label,
                           COUNT(DISTINCT author_account_id) FILTER (
                               WHERE author_account_id IS NOT NULL
                           )::bigint AS user_count
                    FROM base
                    CROSS JOIN LATERAL jsonb_array_elements(effective_labels) AS label(item)
                    WHERE result_id IS NOT NULL
                      AND effective_relevance = 'relevant'
                      AND label.item ->> 'primary_label' <> '无法分类'
                    GROUP BY primary_label, secondary_label
                    ORDER BY primary_label, user_count DESC, secondary_label
                    """
                ),
                params,
            ).mappings()
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
        clauses = [
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
            clauses.append("projection.platform = ANY(CAST(:platforms AS text[]))")
            params["platforms"] = list(query.platforms)
        if query.brand_ids:
            clauses.append("projection.brand_ids && CAST(:brand_ids AS uuid[])")
            params["brand_ids"] = list(query.brand_ids)
        if query.vehicle_model_ids:
            clauses.append("projection.vehicle_model_ids && CAST(:vehicle_model_ids AS uuid[])")
            params["vehicle_model_ids"] = list(query.vehicle_model_ids)
        if query.voice_types:
            clauses.append("effective_voice_type = ANY(CAST(:voice_types AS text[]))")
            params["voice_types"] = list(query.voice_types)
        if query.sentiments:
            clauses.append("effective_sentiment = ANY(CAST(:sentiments AS text[]))")
            params["sentiments"] = list(query.sentiments)
        if query.primary_labels:
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(effective_labels) AS f(item) "
                "WHERE f.item ->> 'primary_label' = ANY(CAST(:primary_labels AS text[])))"
            )
            params["primary_labels"] = list(query.primary_labels)
        if query.secondary_labels:
            clauses.append(
                "EXISTS (SELECT 1 FROM jsonb_array_elements(effective_labels) AS f(item) "
                "WHERE f.item ->> 'secondary_label' = ANY(CAST(:secondary_labels AS text[])))"
            )
            params["secondary_labels"] = list(query.secondary_labels)

        where_sql = "\n              AND ".join(clauses)
        return (
            f"""
            WITH active_result AS (
                SELECT DISTINCT ON (result.content_id, result.content_version)
                       result.*
                FROM analysis_content_results AS result
                JOIN analysis_content_runs AS run ON run.id = result.analysis_run_id
                WHERE run.analysis_scheme_version_id = :active_scheme_version_id
                ORDER BY result.content_id, result.content_version,
                         run.sequence_no DESC, result.id DESC
            ),
            latest_review AS (
                SELECT DISTINCT ON (review.content_id, review.content_version)
                       review.content_id, review.content_version, review.decision
                FROM analysis_content_relevance_reviews AS review
                ORDER BY review.content_id, review.content_version,
                         review.review_no DESC, review.reviewed_at DESC, review.id DESC
            ),
            result_labels AS (
                SELECT pair.analysis_result_id,
                       jsonb_agg(
                           jsonb_build_object(
                               'primary_label', pair.primary_label,
                               'secondary_label', pair.secondary_label
                           )
                           ORDER BY pair.ordinal
                       ) AS items
                FROM analysis_content_label_pairs AS pair
                GROUP BY pair.analysis_result_id
            ),
            vehicle_names AS (
                SELECT evidence.content_id,
                       array_agg(DISTINCT model.display_name ORDER BY model.display_name)
                           AS names
                FROM content_vehicle_evidence AS evidence
                JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                WHERE model.merged_into_id IS NULL
                GROUP BY evidence.content_id
            ),
            source AS (
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
                       account.display_name AS author_display_name,
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
                LEFT JOIN accounts AS account ON account.id = content.author_account_id
                LEFT JOIN active_result
                  ON active_result.content_id = projection.content_id
                 AND active_result.content_version = projection.content_version
                LEFT JOIN latest_review AS review
                  ON review.content_id = projection.content_id
                 AND review.content_version = projection.content_version
                LEFT JOIN analysis_content_manual_overrides AS manual
                  ON manual.content_id = projection.content_id
                 AND manual.content_version = projection.content_version
                LEFT JOIN result_labels ON result_labels.analysis_result_id = active_result.id
                LEFT JOIN vehicle_names ON vehicle_names.content_id = projection.content_id
            ),
            base AS (
                SELECT *
                FROM source AS projection
                WHERE {where_sql}
            )
            """,
            params,
        )


__all__ = ["PostgresWorkbenchRepository", "WorkbenchLayoutRevisionConflict"]
