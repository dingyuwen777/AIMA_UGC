"""Stage 8D 声音广场 PostgreSQL 只读 Query Adapter。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import BigInteger, and_, case, exists, func, literal, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.brand_vehicle import (
    BrandRole,
    competition_scope_for_brand_roles,
)
from aima_ugc.contracts.http import (
    CollectionRuntimeStatus,
    CommentCoverageResponse,
    ContentCommentResponse,
    ContentFilterSnapshot,
    ContentMediaResponse,
    ContentSourceResponse,
    ContentSupplementStatusResponse,
)
from aima_ugc.contracts.platform import require_platform_name
from aima_ugc.modules.analysis.manual_override_tables import (
    analysis_content_manual_overrides_table,
)
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_results_table,
    analysis_content_run_targets_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.availability_tables import (
    content_availability_observations_table,
)
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.query import (
    ContentAnalysisRead,
    ContentAvailabilityRead,
    ContentBrandEvidenceRead,
    ContentBrandRead,
    ContentBrandReferenceRead,
    ContentFilterValues,
    ContentReadQuery,
    ContentReadRecord,
    ContentSourceRead,
    ContentTarget,
    ContentVehicleEvidenceRead,
    ContentVehicleRead,
)
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_coverage_observations_table,
    comments_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.tables import (
    register_ingestion_schema,
)
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_vehicle_evidence_table,
    vehicle_brands_table,
    vehicle_models_table,
)

from .content_visibility import content_has_active_source

register_ingestion_schema()


class PostgresContentQueryRepository:
    """统一读取 Content Current、当前 Analysis 和当前来源；不写业务表。"""

    def __init__(
        self,
        session: Session,
        *,
        analysis_identity: AnalysisConfigurationIdentity | None,
    ) -> None:
        self._session = session
        self._analysis_identity = analysis_identity

    def list_contents(self, query: ContentReadQuery) -> tuple[ContentReadRecord, ...]:
        """在全量查询中排序分页；双向排序均将缺失值置后，以 ID 消除同值歧义。"""
        statement, columns = self._base_statement(query.filters)
        content = contents_table
        sort_column = (
            columns["author_follower_count"]
            if query.sort_by == "follower_count"
            else content.c.published_at
            if query.sort_by == "published_at"
            else columns["sort_at"]
        )
        ascending = query.sort_direction == "asc"
        if query.position is not None:
            boundary = (
                query.position.follower_count
                if query.sort_by == "follower_count"
                else query.position.sort_at
            )
            id_after = (
                content.c.id > query.position.content_id
                if ascending
                else content.c.id < query.position.content_id
            )
            if boundary is None:
                after = and_(sort_column.is_(None), id_after)
            else:
                after = or_(
                    sort_column > boundary if ascending else sort_column < boundary,
                    and_(sort_column == boundary, id_after),
                    sort_column.is_(None),
                )
            statement = statement.where(after)
        order = sort_column.asc() if ascending else sort_column.desc()
        id_order = content.c.id.asc() if ascending else content.c.id.desc()
        rows = tuple(
            self._session.execute(
                statement.order_by(order.nulls_last(), id_order).limit(query.limit)
            ).mappings()
        )
        return self._records(rows)

    def get_content(self, content_id: UUID) -> ContentReadRecord | None:
        statement, _ = self._base_statement(
            ContentFilterSnapshot(),
            include_irrelevant=True,
        )
        row = (
            self._session.execute(statement.where(contents_table.c.id == content_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return self._records((row,))[0]

    def list_filter_values(self) -> ContentFilterValues:
        """读取当前可见 Content 的有效筛选值，避免旧版本或失效来源泄漏。"""

        statement, _ = self._base_statement(
            ContentFilterSnapshot(),
            include_irrelevant=True,
        )
        current = statement.subquery("current_content_filter_values")

        def distinct_strings(column: Any) -> tuple[str, ...]:
            return tuple(
                cast(str, value)
                for value in self._session.scalars(
                    select(column)
                    .where(column.is_not(None), column != "")
                    .distinct()
                    .order_by(column)
                )
            )

        label_pair = analysis_content_label_pairs_table
        ai_pairs = {
            (cast(str, row[0]), cast(str, row[1]))
            for row in self._session.execute(
                select(label_pair.c.primary_label, label_pair.c.secondary_label)
                .select_from(
                    current.join(
                        label_pair,
                        label_pair.c.analysis_result_id == current.c.analysis_result_id,
                    )
                )
                .where(or_(current.c.labels_locked.is_(False), current.c.labels_locked.is_(None)))
                .distinct()
            )
        }
        manual_pairs: set[tuple[str, str]] = set()
        for raw_labels in self._session.scalars(
            select(current.c.manual_labels).where(current.c.labels_locked.is_(True))
        ):
            if not isinstance(raw_labels, list):
                continue
            for item in raw_labels:
                if not isinstance(item, dict):
                    continue
                primary = item.get("primary_label")
                secondary = item.get("secondary_label")
                if (
                    isinstance(primary, str)
                    and primary
                    and isinstance(secondary, str)
                    and secondary
                ):
                    manual_pairs.add((primary, secondary))

        return ContentFilterValues(
            content_types=distinct_strings(current.c.content_type),
            sentiments=distinct_strings(current.c.sentiment),
            voice_types=distinct_strings(current.c.voice_type),
            label_pairs=tuple(sorted(ai_pairs | manual_pairs)),
        )

    def freeze_targets(
        self,
        *,
        filters: ContentFilterSnapshot | None = None,
        content_ids: tuple[UUID, ...] = (),
    ) -> tuple[ContentTarget, ...]:
        if filters is not None and content_ids:
            raise ValueError("filters 与 content_ids 不能同时提供")
        if filters is None and not content_ids:
            raise ValueError("必须提供 filters 或 content_ids")
        rows = self._session.execute(
            self.freeze_target_statement(filters=filters, content_ids=content_ids)
        ).mappings()
        return tuple(
            ContentTarget(
                content_id=cast(UUID, row["content_id"]),
                content_version=cast(int, row["content_version"]),
            )
            for row in rows
        )

    def freeze_target_statement(
        self,
        *,
        filters: ContentFilterSnapshot | None = None,
        content_ids: tuple[UUID, ...] = (),
    ) -> Any:
        """返回可供 `INSERT ... SELECT` 使用的稳定 Content ID + Version 选择语句。"""

        if filters is not None and content_ids:
            raise ValueError("filters 与 content_ids 不能同时提供")
        if filters is None and not content_ids:
            raise ValueError("必须提供 filters 或 content_ids")
        content = contents_table
        if filters is not None:
            statement, _ = self._base_statement(filters, targets_only=True)
            selected = statement.subquery("analysis_target_selection")
            ordinal = (
                func.row_number().over(order_by=(selected.c.sort_at.desc(), selected.c.id.desc()))
                - 1
            ).label("target_ordinal")
            return select(
                selected.c.id.label("content_id"),
                selected.c.current_version.label("content_version"),
                ordinal,
            ).order_by(selected.c.sort_at.desc(), selected.c.id.desc())

        order = case(
            {content_id: ordinal for ordinal, content_id in enumerate(content_ids)},
            value=content.c.id,
        )
        return (
            select(
                content.c.id.label("content_id"),
                content.c.current_version.label("content_version"),
                order.label("target_ordinal"),
            )
            .where(
                content.c.id.in_(content_ids),
                content_has_active_source(content.c.id),
            )
            .order_by(order)
        )

    def count_all_analysis_targets(self) -> int:
        """统计全部仍有有效来源的 Content Current，不继承相关性筛选。"""

        return cast(
            int,
            self._session.scalar(
                select(func.count())
                .select_from(contents_table)
                .where(content_has_active_source(contents_table.c.id))
            )
            or 0,
        )

    def list_all_analysis_targets(
        self,
        *,
        after_content_id: UUID | None,
        limit: int,
    ) -> tuple[ContentTarget, ...]:
        """按 Content UUID 稳定读取仍有有效来源的一批全量 Analysis Target。"""

        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        statement = select(contents_table.c.id, contents_table.c.current_version).where(
            content_has_active_source(contents_table.c.id)
        )
        if after_content_id is not None:
            statement = statement.where(contents_table.c.id > after_content_id)
        rows = self._session.execute(statement.order_by(contents_table.c.id).limit(limit)).all()
        return tuple(
            ContentTarget(
                content_id=cast(UUID, row.id), content_version=cast(int, row.current_version)
            )
            for row in rows
        )

    def list_media(self, content_id: UUID) -> tuple[ContentMediaResponse, ...]:
        rows = self._session.execute(
            select(content_media_table)
            .where(content_media_table.c.content_id == content_id)
            .order_by(content_media_table.c.position)
        ).mappings()
        return tuple(
            ContentMediaResponse(
                position=cast(int, row["position"]),
                media_type=cast(str, row["media_type"]),
                url=cast(str | None, row["url"]),
                preview_url=cast(str | None, row["preview_url"]),
                alt_text=cast(str | None, row["alt_text"]),
            )
            for row in rows
        )

    def list_comments(
        self,
        content_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[ContentCommentResponse, ...]:
        comment = comments_table
        author = accounts_table
        rows = self._session.execute(
            select(
                comment.c.id,
                comment.c.external_comment_id,
                author.c.display_name.label("author_display_name"),
                comment.c.text,
                comment.c.published_at,
                comment.c.current_like_count,
                comment.c.current_reply_count,
            )
            .select_from(comment.outerjoin(author, author.c.id == comment.c.author_account_id))
            .where(comment.c.content_id == content_id)
            .order_by(comment.c.published_at.desc().nullslast(), comment.c.id.desc())
            .limit(limit)
        ).mappings()
        return tuple(
            ContentCommentResponse(
                id=cast(UUID, row["id"]),
                external_comment_id=cast(str, row["external_comment_id"]),
                author_display_name=cast(str | None, row["author_display_name"]),
                text=cast(str | None, row["text"]),
                published_at=cast(datetime | None, row["published_at"]),
                like_count=cast(int | None, row["current_like_count"]),
                reply_count=cast(int | None, row["current_reply_count"]),
            )
            for row in rows
        )

    def latest_comment_coverage(self, content_id: UUID) -> CommentCoverageResponse | None:
        row = (
            self._session.execute(
                select(comment_coverage_observations_table)
                .where(comment_coverage_observations_table.c.content_id == content_id)
                .order_by(
                    comment_coverage_observations_table.c.observed_at.desc(),
                    comment_coverage_observations_table.c.id.desc(),
                )
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return CommentCoverageResponse(
            coverage=cast(str, row["coverage"]),
            reported_total=cast(int | None, row["reported_total"]),
            collected_count=cast(int, row["collected_count"]),
            observed_at=cast(datetime, row["observed_at"]),
        )

    def latest_supplement_status(self, content_id: UUID) -> ContentSupplementStatusResponse | None:
        """返回该 Content 最近一次 Batch Supplement Scope 状态。"""

        run = collection_runs_table
        scope = collection_scopes_table
        updated_at = func.coalesce(
            scope.c.finished_at,
            scope.c.started_at,
            run.c.finished_at,
            run.c.started_at,
            run.c.created_at,
        ).label("updated_at")
        row = (
            self._session.execute(
                select(
                    run.c.id.label("run_id"),
                    scope.c.status,
                    scope.c.stop_reason,
                    updated_at,
                )
                .select_from(scope.join(run, run.c.id == scope.c.run_id))
                .where(
                    run.c.import_batch_id.is_not(None),
                    scope.c.source_type == "content",
                    scope.c.source_value == str(content_id),
                    scope.c.operation_group == "content_enrichment",
                )
                .order_by(run.c.created_at.desc(), run.c.id.desc(), scope.c.id.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return ContentSupplementStatusResponse(
            run_id=cast(UUID, row["run_id"]),
            status=cast(CollectionRuntimeStatus, row["status"]),
            stop_reason=cast(str | None, row["stop_reason"]),
            updated_at=cast(datetime, row["updated_at"]),
        )

    def list_source_records(self, content_id: UUID) -> tuple[ContentSourceResponse, ...]:
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        scope = collection_scopes_table
        rows = self._session.execute(
            select(
                request.c.provider,
                attempt.c.id.label("provider_attempt_id"),
                version.c.raw_artifact_id,
                request.c.import_batch_id,
                scope.c.run_id.label("collection_run_id"),
                version.c.version_no,
            )
            .select_from(
                version.join(attempt, attempt.c.id == version.c.provider_attempt_id)
                .join(request, request.c.id == attempt.c.provider_request_id)
                .outerjoin(scope, scope.c.id == request.c.scope_id)
            )
            .where(version.c.content_id == content_id)
            .order_by(version.c.version_no.desc())
        ).mappings()
        return tuple(
            ContentSourceResponse(
                provider_name=cast(str, row["provider"]),
                provider_attempt_id=cast(UUID, row["provider_attempt_id"]),
                raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
                import_batch_id=cast(UUID | None, row["import_batch_id"]),
                collection_run_id=cast(UUID | None, row["collection_run_id"]),
            )
            for row in rows
        )

    def _base_statement(
        self,
        filters: ContentFilterSnapshot,
        *,
        targets_only: bool = False,
        include_irrelevant: bool = False,
    ) -> tuple[Any, dict[str, Any]]:
        """构造当前业务投影；作者关联为一对一，不扩大内容行数。"""
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        scope = collection_scopes_table
        review = _latest_relevance_review_subquery()
        manual = analysis_content_manual_overrides_table
        analysis = _latest_analysis_subquery(self._analysis_identity)
        latest_run = _latest_analysis_run_subquery()
        sort_at = func.coalesce(content.c.published_at, content.c.last_seen_at).label("sort_at")
        has_any_analysis = exists(
            select(analysis_content_results_table.c.id).where(
                analysis_content_results_table.c.content_id == content.c.id
            )
        )
        current_analysis = and_(
            analysis.c.content_id == content.c.id,
            analysis.c.content_version == content.c.current_version,
            analysis.c.rank == 1,
        )
        current_review = and_(
            review.c.content_id == content.c.id,
            review.c.content_version == content.c.current_version,
            review.c.rank == 1,
        )
        current_manual = and_(
            manual.c.content_id == content.c.id,
            manual.c.content_version == content.c.current_version,
        )
        current_latest_run = and_(
            latest_run.c.content_id == content.c.id,
            latest_run.c.content_version == content.c.current_version,
            latest_run.c.rank == 1,
        )
        effective_relevance = case(
            (review.c.decision == "relevant", literal("relevant")),
            (review.c.decision == "irrelevant", literal("irrelevant")),
            else_=analysis.c.relevance,
        )
        relevance_source = case(
            (review.c.decision.in_(("relevant", "irrelevant")), literal("manual_review")),
            (analysis.c.relevance.is_not(None), literal("ai")),
            else_=literal(None),
        )
        effective_voice_type = case(
            (manual.c.voice_type_locked.is_(True), manual.c.voice_type),
            else_=analysis.c.voice_type,
        )
        effective_sentiment = case(
            (manual.c.sentiment_locked.is_(True), manual.c.sentiment),
            else_=analysis.c.sentiment,
        )
        source_join = (
            content.join(
                version,
                and_(
                    version.c.content_id == content.c.id,
                    version.c.version_no == content.c.current_version,
                ),
            )
            .join(attempt, attempt.c.id == version.c.provider_attempt_id)
            .join(request, request.c.id == attempt.c.provider_request_id)
            .outerjoin(scope, scope.c.id == request.c.scope_id)
            .outerjoin(analysis, current_analysis)
            .outerjoin(latest_run, current_latest_run)
            .outerjoin(review, current_review)
            .outerjoin(manual, current_manual)
        )
        columns: dict[str, Any] = {"sort_at": sort_at}
        if targets_only:
            selected: tuple[Any, ...] = (content.c.id, content.c.current_version, sort_at)
        else:
            source_join = source_join.outerjoin(
                accounts_table, accounts_table.c.id == content.c.author_account_id
            )
            snapshot_follower_count = case(
                (
                    func.jsonb_typeof(version.c.author_snapshot["follower_count"]) == "number",
                    version.c.author_snapshot["follower_count"].astext.cast(BigInteger),
                ),
                else_=None,
            )
            # 稳定账号 Current 优先；无稳定账号或当前值缺失时回退当前 Content Version 快照。
            author_follower_count = func.coalesce(
                accounts_table.c.current_follower_count,
                snapshot_follower_count,
            )
            columns["author_follower_count"] = author_follower_count
            selected = (
                content.c.id,
                content.c.current_version,
                sort_at,
                content.c.platform,
                content.c.external_content_id,
                content.c.content_type,
                content.c.title,
                content.c.text,
                version.c.author_snapshot["display_name"].astext.label("author_display_name"),
                author_follower_count.label("author_follower_count"),
                content.c.published_at,
                content.c.last_seen_at,
                content.c.canonical_url,
                content.c.share_url,
                content.c.current_like_count,
                content.c.current_comment_count,
                content.c.current_favorite_count,
                content.c.current_share_count,
                content.c.current_repost_count,
                content.c.current_view_count,
                content.c.current_play_count,
                analysis.c.id.label("analysis_result_id"),
                analysis.c.relevance,
                effective_voice_type.label("voice_type"),
                effective_sentiment.label("sentiment"),
                manual.c.labels.label("manual_labels"),
                manual.c.voice_type_locked,
                manual.c.sentiment_locked,
                manual.c.labels_locked,
                analysis.c.analyzed_at,
                analysis.c.model_provider,
                analysis.c.model,
                latest_run.c.run_id.label("latest_run_id"),
                latest_run.c.run_status.label("latest_run_status"),
                effective_relevance.label("effective_relevance"),
                relevance_source.label("relevance_source"),
                has_any_analysis.label("has_any_analysis"),
                request.c.provider.label("provider_name"),
                attempt.c.id.label("provider_attempt_id"),
                version.c.raw_artifact_id,
                request.c.import_batch_id,
                scope.c.run_id.label("collection_run_id"),
            )
        statement = (
            select(*selected)
            .select_from(source_join)
            .where(content_has_active_source(content.c.id))
        )
        statement = _apply_filters(
            statement,
            filters=filters,
            analysis=analysis,
            manual=manual,
            effective_voice_type=effective_voice_type,
            effective_sentiment=effective_sentiment,
            effective_relevance=effective_relevance,
            has_any_analysis=has_any_analysis,
            version=version,
            include_irrelevant=include_irrelevant,
        )
        return statement, columns

    def _records(self, rows: tuple[RowMapping, ...]) -> tuple[ContentReadRecord, ...]:
        """批量补充内容关系，并保留作者粉丝数的未知值。"""
        content_ids = tuple(cast(UUID, row["id"]) for row in rows)
        result_ids = tuple(
            cast(UUID, row["analysis_result_id"])
            for row in rows
            if row["analysis_result_id"] is not None
        )
        labels: dict[UUID, list[tuple[int, str, str]]] = defaultdict(list)
        if result_ids:
            label_rows = self._session.execute(
                select(analysis_content_label_pairs_table).where(
                    analysis_content_label_pairs_table.c.analysis_result_id.in_(result_ids)
                )
            ).mappings()
            for label in label_rows:
                labels[cast(UUID, label["analysis_result_id"])].append(
                    (
                        cast(int, label["ordinal"]),
                        cast(str, label["primary_label"]),
                        cast(str, label["secondary_label"]),
                    )
                )

        brands: dict[
            UUID,
            dict[
                UUID,
                tuple[str, str, BrandRole, list[ContentBrandEvidenceRead]],
            ],
        ] = defaultdict(dict)
        if content_ids:
            brand_rows = self._session.execute(
                select(
                    content_brand_evidence_table,
                    vehicle_brands_table.c.code.label("brand_code"),
                    vehicle_brands_table.c.display_name.label("brand_display_name"),
                    vehicle_brands_table.c.role.label("brand_role"),
                )
                .join(
                    vehicle_brands_table,
                    vehicle_brands_table.c.id == content_brand_evidence_table.c.brand_id,
                )
                .join(
                    contents_table,
                    contents_table.c.id == content_brand_evidence_table.c.content_id,
                )
                .where(
                    content_brand_evidence_table.c.content_id.in_(content_ids),
                    content_brand_evidence_table.c.content_version
                    == contents_table.c.current_version,
                    content_brand_evidence_table.c.is_active.is_(True),
                )
                .order_by(
                    content_brand_evidence_table.c.content_id,
                    vehicle_brands_table.c.code,
                    vehicle_brands_table.c.id,
                    content_brand_evidence_table.c.created_at,
                    content_brand_evidence_table.c.id,
                )
            ).mappings()
            for brand_row in brand_rows:
                content_id = cast(UUID, brand_row["content_id"])
                brand_id = cast(UUID, brand_row["brand_id"])
                existing_brand = brands[content_id].setdefault(
                    brand_id,
                    (
                        cast(str, brand_row["brand_code"]),
                        cast(str, brand_row["brand_display_name"]),
                        cast(BrandRole, brand_row["brand_role"]),
                        [],
                    ),
                )
                existing_brand[3].append(
                    ContentBrandEvidenceRead(
                        source=cast(str, brand_row["source"]),
                        matched_text=cast(str | None, brand_row["matched_text"]),
                        source_field=cast(str | None, brand_row["source_field"]),
                        derived_vehicle_model_id=cast(
                            UUID | None, brand_row["derived_vehicle_model_id"]
                        ),
                        catalog_version=cast(int, brand_row["catalog_version"]),
                        confidence=cast(float | None, brand_row["confidence"]),
                        is_manual_locked=cast(bool, brand_row["is_manual_locked"]),
                    )
                )

        vehicles: dict[
            UUID,
            dict[
                UUID,
                tuple[
                    str,
                    str,
                    list[ContentVehicleEvidenceRead],
                    str | None,
                    str | None,
                    ContentBrandReferenceRead | None,
                ],
            ],
        ] = defaultdict(dict)
        if content_ids:
            effective_vehicle = vehicle_models_table.alias("effective_content_vehicle")
            effective_brand = vehicle_brands_table.alias("effective_content_vehicle_brand")
            effective_brand_id = case(
                (effective_vehicle.c.id.is_not(None), effective_vehicle.c.brand_id),
                else_=vehicle_models_table.c.brand_id,
            )
            vehicle_rows = self._session.execute(
                select(
                    content_vehicle_evidence_table,
                    func.coalesce(
                        effective_vehicle.c.id,
                        vehicle_models_table.c.id,
                    ).label("effective_vehicle_model_id"),
                    func.coalesce(
                        effective_vehicle.c.code,
                        vehicle_models_table.c.code,
                    ).label("effective_vehicle_code"),
                    func.coalesce(
                        effective_vehicle.c.display_name,
                        vehicle_models_table.c.display_name,
                    ).label("effective_vehicle_display_name"),
                    case(
                        (effective_vehicle.c.id.is_not(None), effective_vehicle.c.series_name),
                        else_=vehicle_models_table.c.series_name,
                    ).label("effective_vehicle_series_name"),
                    case(
                        (effective_vehicle.c.id.is_not(None), effective_vehicle.c.category_name),
                        else_=vehicle_models_table.c.category_name,
                    ).label("effective_vehicle_category_name"),
                    effective_brand.c.id.label("effective_brand_id"),
                    effective_brand.c.code.label("effective_brand_code"),
                    effective_brand.c.display_name.label("effective_brand_display_name"),
                    effective_brand.c.role.label("effective_brand_role"),
                )
                .join(
                    vehicle_models_table,
                    vehicle_models_table.c.id == content_vehicle_evidence_table.c.vehicle_model_id,
                )
                .outerjoin(
                    effective_vehicle,
                    effective_vehicle.c.id == vehicle_models_table.c.merged_into_id,
                )
                .outerjoin(effective_brand, effective_brand.c.id == effective_brand_id)
                .join(
                    contents_table,
                    contents_table.c.id == content_vehicle_evidence_table.c.content_id,
                )
                .where(
                    content_vehicle_evidence_table.c.content_id.in_(content_ids),
                    content_vehicle_evidence_table.c.content_version
                    == contents_table.c.current_version,
                    content_vehicle_evidence_table.c.is_active.is_(True),
                )
                .order_by(
                    content_vehicle_evidence_table.c.content_id,
                    func.coalesce(effective_vehicle.c.code, vehicle_models_table.c.code),
                    content_vehicle_evidence_table.c.created_at,
                )
            ).mappings()
            for vehicle_row in vehicle_rows:
                content_id = cast(UUID, vehicle_row["content_id"])
                model_id = cast(UUID, vehicle_row["effective_vehicle_model_id"])
                vehicle_brand_id = cast(UUID | None, vehicle_row["effective_brand_id"])
                vehicle_brand = (
                    ContentBrandReferenceRead(
                        id=vehicle_brand_id,
                        code=cast(str, vehicle_row["effective_brand_code"]),
                        display_name=cast(str, vehicle_row["effective_brand_display_name"]),
                        role=cast(BrandRole, vehicle_row["effective_brand_role"]),
                    )
                    if vehicle_brand_id is not None
                    else None
                )
                existing = vehicles[content_id].setdefault(
                    model_id,
                    (
                        cast(str, vehicle_row["effective_vehicle_code"]),
                        cast(str, vehicle_row["effective_vehicle_display_name"]),
                        [],
                        cast(str | None, vehicle_row["effective_vehicle_series_name"]),
                        cast(str | None, vehicle_row["effective_vehicle_category_name"]),
                        vehicle_brand,
                    ),
                )
                existing[2].append(
                    ContentVehicleEvidenceRead(
                        source=cast(str, vehicle_row["source"]),
                        matched_text=cast(str | None, vehicle_row["matched_text"]),
                        source_field=cast(str | None, vehicle_row["source_field"]),
                        catalog_version=cast(int, vehicle_row["catalog_version"]),
                        confidence=cast(float | None, vehicle_row["confidence"]),
                        is_manual_locked=cast(bool, vehicle_row["is_manual_locked"]),
                    )
                )

        availability_by_content: dict[UUID, ContentAvailabilityRead] = {}
        if content_ids:
            availability = content_availability_observations_table
            latest_availability = select(
                *availability.c,
                func.row_number()
                .over(
                    partition_by=availability.c.content_id,
                    order_by=(availability.c.observed_at.desc(), availability.c.id.desc()),
                )
                .label("rank"),
            ).subquery("latest_content_availability")
            availability_rows = self._session.execute(
                select(latest_availability).where(
                    latest_availability.c.content_id.in_(content_ids),
                    latest_availability.c.rank == 1,
                )
            ).mappings()
            for availability_row in availability_rows:
                availability_by_content[cast(UUID, availability_row["content_id"])] = (
                    ContentAvailabilityRead(
                        status=cast(str, availability_row["status"]),
                        reason_code=cast(str, availability_row["reason_code"]),
                        evidence_kind=cast(str, availability_row["evidence_kind"]),
                        observed_at=cast(datetime, availability_row["observed_at"]),
                    )
                )

        records: list[ContentReadRecord] = []
        for row in rows:
            result_id = cast(UUID | None, row["analysis_result_id"])
            analysis = self._analysis_read(row, result_id, labels)
            content_id = cast(UUID, row["id"])
            records.append(
                ContentReadRecord(
                    id=content_id,
                    current_version=cast(int, row["current_version"]),
                    sort_at=cast(datetime, row["sort_at"]),
                    platform=require_platform_name(cast(str, row["platform"])),
                    external_content_id=cast(str, row["external_content_id"]),
                    content_type=cast(str, row["content_type"]),
                    title=cast(str | None, row["title"]),
                    text=cast(str | None, row["text"]),
                    author_display_name=cast(str | None, row["author_display_name"]),
                    published_at=cast(datetime | None, row["published_at"]),
                    last_seen_at=cast(datetime, row["last_seen_at"]),
                    canonical_url=cast(str | None, row["canonical_url"]),
                    share_url=cast(str | None, row["share_url"]),
                    metrics={
                        "like_count": cast(int | None, row["current_like_count"]),
                        "comment_count": cast(int | None, row["current_comment_count"]),
                        "favorite_count": cast(int | None, row["current_favorite_count"]),
                        "share_count": cast(int | None, row["current_share_count"]),
                        "repost_count": cast(int | None, row["current_repost_count"]),
                        "view_count": cast(int | None, row["current_view_count"]),
                        "play_count": cast(int | None, row["current_play_count"]),
                    },
                    analysis=analysis,
                    effective_relevance=cast(str | None, row["effective_relevance"]),
                    relevance_source=cast(str | None, row["relevance_source"]),
                    source=ContentSourceRead(
                        provider_name=cast(str, row["provider_name"]),
                        provider_attempt_id=cast(UUID, row["provider_attempt_id"]),
                        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
                        import_batch_id=cast(UUID | None, row["import_batch_id"]),
                        collection_run_id=cast(UUID | None, row["collection_run_id"]),
                    ),
                    brands=tuple(
                        ContentBrandRead(
                            id=brand_id,
                            code=value[0],
                            display_name=value[1],
                            role=value[2],
                            evidences=tuple(value[3]),
                        )
                        for brand_id, value in brands[content_id].items()
                    ),
                    vehicles=tuple(
                        ContentVehicleRead(
                            vehicle_model_id=model_id,
                            code=value[0],
                            display_name=value[1],
                            evidences=tuple(value[2]),
                            series_name=value[3],
                            category_name=value[4],
                            brand=value[5],
                        )
                        for model_id, value in vehicles[content_id].items()
                    ),
                    competition_scope=competition_scope_for_brand_roles(
                        value[2] for value in brands[content_id].values()
                    ),
                    availability=availability_by_content.get(content_id),
                    author_follower_count=cast(int | None, row["author_follower_count"]),
                )
            )
        return tuple(records)

    @staticmethod
    def _analysis_read(
        row: RowMapping,
        result_id: UUID | None,
        labels: dict[UUID, list[tuple[int, str, str]]],
    ) -> ContentAnalysisRead:
        """把 AI 原始结果与当前内容版本的人工维度锁合成为读取投影。"""

        if result_id is None:
            return ContentAnalysisRead(
                result_id=None,
                status="stale" if bool(row["has_any_analysis"]) else "pending",
                relevance=None,
                voice_type=None,
                sentiment=None,
                labels=(),
                analyzed_at=None,
                model_provider=None,
                model=None,
                latest_run_id=cast(UUID | None, row["latest_run_id"]),
                latest_run_status=cast(str | None, row["latest_run_status"]),
                manual_locked_dimensions=(),
            )
        if bool(row["labels_locked"]):
            ordered = tuple(
                (
                    item["primary_label"],
                    item["secondary_label"],
                )
                for item in cast(list[dict[str, str]], row["manual_labels"])
            )
        else:
            ordered = tuple(
                (primary, secondary)
                for _, primary, secondary in sorted(labels[result_id], key=lambda item: item[0])
            )
        locked_dimensions = tuple(
            dimension
            for dimension in ("voice_type", "sentiment", "labels")
            if bool(row[f"{dimension}_locked"])
        )
        return ContentAnalysisRead(
            result_id=result_id,
            status="completed",
            relevance=cast(str, row["relevance"]),
            voice_type=cast(str, row["voice_type"]),
            sentiment=cast(str | None, row["sentiment"]),
            labels=ordered,
            analyzed_at=cast(datetime, row["analyzed_at"]),
            model_provider=cast(str, row["model_provider"]),
            model=cast(str, row["model"]),
            latest_run_id=cast(UUID | None, row["latest_run_id"]),
            latest_run_status=cast(str | None, row["latest_run_status"]),
            manual_locked_dimensions=locked_dimensions,
        )


def _latest_analysis_subquery(
    identity: AnalysisConfigurationIdentity | None,
) -> Any:
    del identity
    result = analysis_content_results_table
    run = analysis_content_runs_table
    statement = select(
        result.c.id,
        result.c.content_id,
        result.c.content_version,
        result.c.relevance,
        result.c.voice_type,
        result.c.sentiment,
        result.c.analyzed_at,
        result.c.model_provider,
        result.c.model,
        func.row_number()
        .over(
            partition_by=(result.c.content_id, result.c.content_version),
            order_by=(run.c.sequence_no.desc(), result.c.id.desc()),
        )
        .label("rank"),
    ).select_from(result.join(run, run.c.id == result.c.analysis_run_id))
    return statement.subquery("latest_content_analysis")


def _latest_analysis_run_subquery() -> Any:
    target = analysis_content_run_targets_table
    run = analysis_content_runs_table
    return (
        select(
            target.c.content_id,
            target.c.content_version,
            run.c.id.label("run_id"),
            run.c.status.label("run_status"),
            func.row_number()
            .over(
                partition_by=(target.c.content_id, target.c.content_version),
                order_by=run.c.sequence_no.desc(),
            )
            .label("rank"),
        )
        .select_from(target.join(run, run.c.id == target.c.run_id))
        .subquery("latest_content_analysis_run")
    )


def _latest_relevance_review_subquery() -> Any:
    review = analysis_content_relevance_reviews_table
    return select(
        review.c.id,
        review.c.content_id,
        review.c.content_version,
        review.c.decision,
        func.row_number()
        .over(
            partition_by=(review.c.content_id, review.c.content_version),
            order_by=(review.c.review_no.desc(), review.c.reviewed_at.desc(), review.c.id.desc()),
        )
        .label("rank"),
    ).subquery("latest_content_relevance_review")


def _apply_filters(
    statement: Any,
    *,
    filters: ContentFilterSnapshot,
    analysis: Any,
    manual: Any,
    effective_voice_type: Any,
    effective_sentiment: Any,
    effective_relevance: Any,
    has_any_analysis: Any,
    version: Any,
    include_irrelevant: bool,
) -> Any:
    content = contents_table
    if filters.relevance is None:
        if not include_irrelevant:
            statement = statement.where(
                or_(effective_relevance.is_(None), effective_relevance != "irrelevant")
            )
    else:
        statement = statement.where(effective_relevance == filters.relevance)
    if filters.voice_type is not None:
        statement = statement.where(effective_voice_type == filters.voice_type)
    if filters.search is not None:
        pattern = f"%{_escape_like(filters.search)}%"
        statement = statement.where(
            or_(
                content.c.title.ilike(pattern, escape="\\"),
                content.c.text.ilike(pattern, escape="\\"),
                content.c.external_content_id.ilike(pattern, escape="\\"),
                version.c.author_snapshot["display_name"].astext.ilike(pattern, escape="\\"),
            )
        )
    if filters.platforms:
        statement = statement.where(content.c.platform.in_(filters.platforms))
    if filters.content_types:
        statement = statement.where(content.c.content_type.in_(filters.content_types))
    if filters.brand_ids:
        statement = statement.where(
            exists(
                select(content_brand_evidence_table.c.id).where(
                    content_brand_evidence_table.c.content_id == content.c.id,
                    content_brand_evidence_table.c.content_version == content.c.current_version,
                    content_brand_evidence_table.c.brand_id.in_(filters.brand_ids),
                    content_brand_evidence_table.c.is_active.is_(True),
                )
            )
        )
    if filters.competition_scopes:
        competition_evidence = content_brand_evidence_table.alias(
            "content_competition_evidence"
        )
        competition_brand = vehicle_brands_table.alias("content_competition_brand")
        competition_source = competition_evidence.join(
            competition_brand,
            competition_brand.c.id == competition_evidence.c.brand_id,
        )
        role_count = (
            select(func.count(func.distinct(competition_brand.c.role)))
            .select_from(competition_source)
            .where(
                competition_evidence.c.content_id == content.c.id,
                competition_evidence.c.content_version == content.c.current_version,
                competition_evidence.c.is_active.is_(True),
            )
            .correlate(content)
            .scalar_subquery()
        )

        def has_role(role: BrandRole) -> Any:
            return exists(
                select(literal(1))
                .select_from(competition_source)
                .where(
                    competition_evidence.c.content_id == content.c.id,
                    competition_evidence.c.content_version == content.c.current_version,
                    competition_evidence.c.is_active.is_(True),
                    competition_brand.c.role == role,
                )
            )

        scope_predicates: list[Any] = []
        if "none_detected" in filters.competition_scopes:
            scope_predicates.append(role_count == 0)
        if "mixed" in filters.competition_scopes:
            scope_predicates.append(role_count > 1)
        if "owned_only" in filters.competition_scopes:
            scope_predicates.append(and_(role_count == 1, has_role("owned")))
        if "competitor_only" in filters.competition_scopes:
            scope_predicates.append(and_(role_count == 1, has_role("competitor")))
        if "other_only" in filters.competition_scopes:
            scope_predicates.append(and_(role_count == 1, has_role("other")))
        statement = statement.where(or_(*scope_predicates))
    if filters.vehicle_model_ids:
        filter_vehicle = vehicle_models_table.alias("content_vehicle_filter_model")
        statement = statement.where(
            exists(
                select(content_vehicle_evidence_table.c.id)
                .select_from(
                    content_vehicle_evidence_table.join(
                        filter_vehicle,
                        filter_vehicle.c.id == content_vehicle_evidence_table.c.vehicle_model_id,
                    )
                )
                .where(
                    content_vehicle_evidence_table.c.content_id == content.c.id,
                    content_vehicle_evidence_table.c.content_version == content.c.current_version,
                    or_(
                        content_vehicle_evidence_table.c.vehicle_model_id.in_(
                            filters.vehicle_model_ids
                        ),
                        filter_vehicle.c.merged_into_id.in_(filters.vehicle_model_ids),
                    ),
                    content_vehicle_evidence_table.c.is_active.is_(True),
                )
            )
        )
    if filters.published_from is not None:
        statement = statement.where(content.c.published_at >= filters.published_from)
    if filters.published_to is not None:
        statement = statement.where(content.c.published_at <= filters.published_to)
    if filters.source_identifier is not None:
        source_version = content_versions_table.alias("source_filter_version")
        source_attempt = provider_request_attempts_table.alias("source_filter_attempt")
        source_request = provider_requests_table.alias("source_filter_request")
        source_scope = collection_scopes_table.alias("source_filter_scope")
        source_lineage = (
            source_version.join(
                source_attempt,
                source_attempt.c.id == source_version.c.provider_attempt_id,
            )
            .join(
                source_request,
                source_request.c.id == source_attempt.c.provider_request_id,
            )
            .outerjoin(source_scope, source_scope.c.id == source_request.c.scope_id)
        )
        historical_outcome = processing_import_batch_items_table.alias(
            "source_filter_historical_outcome"
        )
        historical_item = historical_import_campaign_items_table.alias(
            "source_filter_historical_item"
        )
        statement = statement.where(
            or_(
                exists(
                    select(literal(1))
                    .select_from(source_lineage)
                    .where(
                        source_version.c.content_id == content.c.id,
                        or_(
                            source_request.c.import_batch_id == filters.source_identifier,
                            source_scope.c.run_id == filters.source_identifier,
                        ),
                    )
                ),
                exists(
                    select(literal(1))
                    .select_from(
                        historical_outcome.join(
                            historical_item,
                            historical_item.c.id == historical_outcome.c.campaign_item_id,
                        )
                    )
                    .where(
                        historical_outcome.c.content_id == content.c.id,
                        historical_item.c.campaign_id == filters.source_identifier,
                    )
                ),
            )
        )
    if filters.analysis_status == "completed":
        statement = statement.where(analysis.c.id.is_not(None))
    elif filters.analysis_status == "stale":
        statement = statement.where(analysis.c.id.is_(None), has_any_analysis)
    elif filters.analysis_status == "pending":
        statement = statement.where(~has_any_analysis)
    if filters.sentiment is not None:
        statement = statement.where(effective_sentiment == filters.sentiment)
    if filters.primary_label is not None or filters.secondary_label is not None:
        pair = analysis_content_label_pairs_table
        label_conditions = [pair.c.analysis_result_id == analysis.c.id]
        if filters.primary_label is not None:
            label_conditions.append(pair.c.primary_label == filters.primary_label)
        if filters.secondary_label is not None:
            label_conditions.append(pair.c.secondary_label == filters.secondary_label)
        manual_label: dict[str, str] = {}
        if filters.primary_label is not None:
            manual_label["primary_label"] = filters.primary_label
        if filters.secondary_label is not None:
            manual_label["secondary_label"] = filters.secondary_label
        ai_label_match = exists(select(literal(1)).where(*label_conditions))
        statement = statement.where(
            or_(
                and_(
                    manual.c.labels_locked.is_(True),
                    manual.c.labels.contains([manual_label]),
                ),
                and_(
                    or_(
                        manual.c.labels_locked.is_(False),
                        manual.c.labels_locked.is_(None),
                    ),
                    ai_label_match,
                ),
            )
        )
    return statement


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = ["PostgresContentQueryRepository"]
