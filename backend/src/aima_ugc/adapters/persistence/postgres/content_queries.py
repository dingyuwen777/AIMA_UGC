"""Stage 8D 声音广场 PostgreSQL 只读 Query Adapter。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, case, exists, false, func, literal, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

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
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_results_table,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.query import (
    ContentAnalysisRead,
    ContentReadQuery,
    ContentReadRecord,
    ContentSourceRead,
    ContentTarget,
)
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_coverage_observations_table,
    comments_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.ingestion.tables import register_ingestion_schema

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
        statement, columns = self._base_statement(query.filters)
        sort_at = columns["sort_at"]
        content = contents_table
        if query.position is not None:
            statement = statement.where(
                or_(
                    sort_at < query.position.sort_at,
                    and_(
                        sort_at == query.position.sort_at,
                        content.c.id < query.position.content_id,
                    ),
                )
            )
        rows = tuple(
            self._session.execute(
                statement.order_by(sort_at.desc(), content.c.id.desc()).limit(query.limit)
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
        content = contents_table
        if filters is not None:
            statement, columns = self._base_statement(filters, targets_only=True)
            rows = self._session.execute(
                statement.order_by(columns["sort_at"].desc(), content.c.id.desc())
            ).mappings()
            return tuple(
                ContentTarget(
                    content_id=cast(UUID, row["id"]),
                    content_version=cast(int, row["current_version"]),
                )
                for row in rows
            )

        rows = self._session.execute(
            select(content.c.id, content.c.current_version).where(content.c.id.in_(content_ids))
        ).mappings()
        by_id = {cast(UUID, row["id"]): cast(int, row["current_version"]) for row in rows}
        return tuple(
            ContentTarget(content_id=content_id, content_version=by_id[content_id])
            for content_id in content_ids
            if content_id in by_id
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
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        scope = collection_scopes_table
        review = analysis_content_relevance_reviews_table
        analysis = _latest_analysis_subquery(self._analysis_identity)
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
            review.c.decision == "relevant",
        )
        effective_relevance = case(
            (review.c.id.is_not(None), literal("relevant")),
            else_=analysis.c.relevance,
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
            .outerjoin(review, current_review)
        )
        if targets_only:
            selected: tuple[Any, ...] = (content.c.id, content.c.current_version, sort_at)
        else:
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
                analysis.c.voice_type,
                analysis.c.sentiment,
                analysis.c.analyzed_at,
                analysis.c.model_provider,
                analysis.c.model,
                has_any_analysis.label("has_any_analysis"),
                request.c.provider.label("provider_name"),
                attempt.c.id.label("provider_attempt_id"),
                version.c.raw_artifact_id,
                request.c.import_batch_id,
                scope.c.run_id.label("collection_run_id"),
            )
        statement = select(*selected).select_from(source_join)
        statement = _apply_filters(
            statement,
            filters=filters,
            analysis=analysis,
            effective_relevance=effective_relevance,
            has_any_analysis=has_any_analysis,
            version=version,
            include_irrelevant=include_irrelevant,
        )
        return statement, {"sort_at": sort_at}

    def _records(self, rows: tuple[RowMapping, ...]) -> tuple[ContentReadRecord, ...]:
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
        records: list[ContentReadRecord] = []
        for row in rows:
            result_id = cast(UUID | None, row["analysis_result_id"])
            if result_id is not None:
                ordered = tuple(
                    (primary, secondary)
                    for _, primary, secondary in sorted(labels[result_id], key=lambda item: item[0])
                )
                analysis = ContentAnalysisRead(
                    result_id=result_id,
                    status="completed",
                    relevance=cast(str, row["relevance"]),
                    voice_type=cast(str, row["voice_type"]),
                    sentiment=cast(str | None, row["sentiment"]),
                    labels=ordered,
                    analyzed_at=cast(datetime, row["analyzed_at"]),
                    model_provider=cast(str, row["model_provider"]),
                    model=cast(str, row["model"]),
                )
            else:
                analysis = ContentAnalysisRead(
                    result_id=None,
                    status="stale" if bool(row["has_any_analysis"]) else "pending",
                    relevance=None,
                    voice_type=None,
                    sentiment=None,
                    labels=(),
                    analyzed_at=None,
                    model_provider=None,
                    model=None,
                )
            records.append(
                ContentReadRecord(
                    id=cast(UUID, row["id"]),
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
                    source=ContentSourceRead(
                        provider_name=cast(str, row["provider_name"]),
                        provider_attempt_id=cast(UUID, row["provider_attempt_id"]),
                        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
                        import_batch_id=cast(UUID | None, row["import_batch_id"]),
                        collection_run_id=cast(UUID | None, row["collection_run_id"]),
                    ),
                )
            )
        return tuple(records)


def _latest_analysis_subquery(
    identity: AnalysisConfigurationIdentity | None,
) -> Any:
    result = analysis_content_results_table
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
            order_by=(result.c.analyzed_at.desc(), result.c.id.desc()),
        )
        .label("rank"),
    )
    if identity is None:
        statement = statement.where(false())
    else:
        statement = statement.where(
            result.c.prompt_version == identity.prompt_version,
            result.c.prompt_sha256 == identity.prompt_sha256,
            result.c.taxonomy_sha256 == identity.taxonomy_sha256,
            result.c.model_provider == identity.model_provider,
            result.c.model == identity.model,
        )
    return statement.subquery("latest_content_analysis")


def _apply_filters(
    statement: Any,
    *,
    filters: ContentFilterSnapshot,
    analysis: Any,
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
        statement = statement.where(analysis.c.voice_type == filters.voice_type)
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
        statement = statement.where(
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
            )
        )
    if filters.analysis_status == "completed":
        statement = statement.where(analysis.c.id.is_not(None))
    elif filters.analysis_status == "stale":
        statement = statement.where(analysis.c.id.is_(None), has_any_analysis)
    elif filters.analysis_status == "pending":
        statement = statement.where(~has_any_analysis)
    if filters.sentiment is not None:
        statement = statement.where(analysis.c.sentiment == filters.sentiment)
    if filters.primary_label is not None or filters.secondary_label is not None:
        pair = analysis_content_label_pairs_table
        label_conditions = [pair.c.analysis_result_id == analysis.c.id]
        if filters.primary_label is not None:
            label_conditions.append(pair.c.primary_label == filters.primary_label)
        if filters.secondary_label is not None:
            label_conditions.append(pair.c.secondary_label == filters.secondary_label)
        statement = statement.where(exists(select(literal(1)).where(*label_conditions)))
    return statement


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = ["PostgresContentQueryRepository"]
