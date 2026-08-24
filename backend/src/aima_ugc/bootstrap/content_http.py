"""Stage 8D 声音广场 HTTP Application Service。"""

from __future__ import annotations

import hashlib
import json
from typing import cast
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.analysis import PostgresAnalysisRepository
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.relevance_reviews import (
    PostgresContentRelevanceReviewRepository,
)
from aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType
from aima_ugc.contracts.http import (
    ContentAnalysisCreatedResponse,
    ContentAnalysisJobResultResponse,
    ContentAnalysisResponse,
    ContentAnalysisStatus,
    ContentAnalysisSubmitRequest,
    ContentDetailResponse,
    ContentFilterSnapshot,
    ContentLabelPairResponse,
    ContentListItemResponse,
    ContentListQuery,
    ContentListResponse,
    ContentMetricsResponse,
    ContentRelevanceSource,
    ContentSourceResponse,
    JobStatusResponse,
)
from aima_ugc.contracts.relevance_review import (
    ContentRelevanceReviewRequest,
    ContentRelevanceReviewResponse,
)
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    ContentAnalysisJobPayload,
)
from aima_ugc.modules.content.content_cursor import ContentCursorCodec, ContentCursorPosition
from aima_ugc.modules.content.http import (
    ContentCursorUnavailable,
    ContentResourceNotFound,
    ContentSelectionEmpty,
)
from aima_ugc.modules.content.query import ContentReadQuery, ContentReadRecord
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.security import SecretFileError, read_secret_file

from .analysis_identity import current_analysis_identity
from .runtime import PlatformRuntime


class PostgresContentHttpService:
    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        cursor_signing_secret: bytes | None = None,
    ) -> None:
        self._runtime = runtime
        self._cursor_signing_secret = cursor_signing_secret

    def list_contents(self, query: ContentListQuery) -> ContentListResponse:
        codec = self._cursor_codec()
        filters = _filters(query)
        query_hash = _query_hash(filters)
        position = codec.decode(query.cursor, query_hash=query_hash) if query.cursor else None
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                rows = PostgresContentQueryRepository(
                    session,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                ).list_contents(
                    query=ContentReadQuery(
                        filters=filters,
                        position=position,
                        limit=query.limit + 1,
                    )
                )
        finally:
            session.close()
        has_more = len(rows) > query.limit
        page = rows[: query.limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = codec.encode(
                ContentCursorPosition(sort_at=last.sort_at, content_id=last.id),
                query_hash=query_hash,
            )
        return ContentListResponse(
            items=tuple(_item_response(item) for item in page),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def get_content(self, content_id: UUID) -> ContentDetailResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresContentQueryRepository(
                    session,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                )
                record = repository.get_content(content_id)
                if record is None:
                    raise ContentResourceNotFound
                item = _item_response(record)
                return ContentDetailResponse(
                    **item.model_dump(),
                    media=repository.list_media(content_id),
                    comments=repository.list_comments(content_id),
                    comment_coverage=repository.latest_comment_coverage(content_id),
                    supplement_status=repository.latest_supplement_status(content_id),
                    source_records=repository.list_source_records(content_id),
                )
        finally:
            session.close()

    def create_analysis(
        self,
        request: ContentAnalysisSubmitRequest,
        *,
        request_id: str,
    ) -> ContentAnalysisCreatedResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                query_repository = PostgresContentQueryRepository(
                    session,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                )
                target_request = request.targets
                targets = (
                    query_repository.freeze_targets(
                        filters=target_request.filters or ContentFilterSnapshot()
                    )
                    if target_request.scope == "query"
                    else query_repository.freeze_targets(content_ids=target_request.content_ids)
                )
                if not targets:
                    raise ContentSelectionEmpty
                analysis_request_id = uuid4()
                job = PostgresJobRepository(session).enqueue(
                    job_type=CONTENT_ANALYSIS_JOB_TYPE,
                    payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
                    payload=ContentAnalysisJobPayload(request_id=analysis_request_id).model_dump(
                        mode="json"
                    ),
                    internal_idempotency_key=f"content-analysis:{analysis_request_id}",
                    request_id=request_id,
                    priority=0,
                    max_attempts=CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
                    timeout_seconds=CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
                )
                PostgresAnalysisRepository(session).create_request(
                    request_id=analysis_request_id,
                    job_id=job.id,
                    scope=target_request.scope,
                    filter_snapshot=(
                        (target_request.filters or ContentFilterSnapshot()).model_dump(mode="json")
                        if target_request.scope == "query"
                        else {"content_ids": [str(item) for item in target_request.content_ids]}
                    ),
                    targets=targets,
                )
                return ContentAnalysisCreatedResponse(
                    request_id=analysis_request_id,
                    job_id=job.id,
                    target_count=len(targets),
                )
        finally:
            session.close()

    def review_relevance(
        self,
        request: ContentRelevanceReviewRequest,
        *,
        request_id: str,
    ) -> ContentRelevanceReviewResponse:
        """保存双向人工相关性覆盖或撤销事件，保留 AI 原始结果。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                summary = PostgresContentRelevanceReviewRepository(session).review_relevance(
                    content_ids=request.content_ids,
                    decision=request.decision,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                    request_id=request_id,
                )
                return ContentRelevanceReviewResponse(
                    requested_count=summary.requested_count,
                    changed_count=summary.changed_count,
                    unchanged_count=summary.unchanged_count,
                )
        finally:
            session.close()

    def get_analysis_job(self, job_id: UUID) -> JobStatusResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).get(job_id)
                if job is None or job.job_type != CONTENT_ANALYSIS_JOB_TYPE:
                    raise ContentResourceNotFound
                return _analysis_job_response(job)
        finally:
            session.close()

    def _cursor_codec(self) -> ContentCursorCodec:
        secret = self._cursor_signing_secret
        if secret is None:
            try:
                secret = (
                    read_secret_file(
                        self._runtime.settings.content_cursor_signing_key_file,
                        root=self._runtime.settings.secret_dir,
                    )
                    .get_secret_value()
                    .encode("utf-8")
                )
            except SecretFileError as exc:
                raise ContentCursorUnavailable from exc
        try:
            return ContentCursorCodec(secret=secret)
        except ValueError as exc:
            raise ContentCursorUnavailable from exc


def _filters(query: ContentListQuery) -> ContentFilterSnapshot:
    return ContentFilterSnapshot.model_validate(query.model_dump(exclude={"cursor", "limit"}))


def _query_hash(filters: ContentFilterSnapshot) -> str:
    payload = filters.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _item_response(record: ContentReadRecord) -> ContentListItemResponse:
    return ContentListItemResponse(
        id=record.id,
        platform=record.platform,
        external_content_id=record.external_content_id,
        content_type=record.content_type,
        title=record.title,
        text=record.text,
        author_display_name=record.author_display_name,
        published_at=record.published_at,
        last_seen_at=record.last_seen_at,
        content_url=record.canonical_url or record.share_url,
        metrics=ContentMetricsResponse.model_validate(record.metrics),
        analysis=ContentAnalysisResponse(
            status=cast(ContentAnalysisStatus, record.analysis.status),
            relevance=cast(ContentRelevance | None, record.analysis.relevance),
            voice_type=cast(ContentVoiceType | None, record.analysis.voice_type),
            sentiment=record.analysis.sentiment,
            labels=tuple(
                ContentLabelPairResponse(primary_label=primary, secondary_label=secondary)
                for primary, secondary in record.analysis.labels
            ),
            analyzed_at=record.analysis.analyzed_at,
            model_provider=record.analysis.model_provider,
            model=record.analysis.model,
        ),
        effective_relevance=cast(ContentRelevance | None, record.effective_relevance),
        relevance_source=cast(ContentRelevanceSource | None, record.relevance_source),
        source=ContentSourceResponse(
            provider_name=record.source.provider_name,
            provider_attempt_id=record.source.provider_attempt_id,
            raw_artifact_id=record.source.raw_artifact_id,
            import_batch_id=record.source.import_batch_id,
            collection_run_id=record.source.collection_run_id,
        ),
    )


def _analysis_job_response(job: JobRecord) -> JobStatusResponse:
    result = (
        ContentAnalysisJobResultResponse.model_validate(job.result)
        if isinstance(job.result, dict)
        else None
    )
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        progress=job.progress,
        error_code=job.error_code,
        result=result,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


__all__ = ["PostgresContentHttpService"]
