"""Stage 8D Analysis Request、Result 与有序标签 PostgreSQL Owner Adapter。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, TypeAdapter
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.analysis.persistence import AnalysisContentResult, AnalysisWorkItem
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_request_items_table,
    analysis_content_requests_table,
    analysis_content_results_table,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.query import ContentTarget
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.platform.jobs import JobExecutionFence

_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class AnalysisRequestNotFound(LookupError):
    pass


class PostgresAnalysisRepository:
    """Analysis 表唯一写入口；所有业务可见提交验证当前 Job Fence。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_request(
        self,
        *,
        request_id: UUID,
        job_id: UUID,
        scope: str,
        filter_snapshot: dict[str, object],
        targets: tuple[ContentTarget, ...],
    ) -> None:
        if not targets:
            raise ValueError("Analysis Request 至少需要一个目标")
        self._session.execute(
            insert(analysis_content_requests_table).values(
                id=request_id,
                job_id=job_id,
                scope=scope,
                filter_snapshot=filter_snapshot,
                target_count=len(targets),
                created_at=datetime.now(UTC),
            )
        )
        self._session.execute(
            insert(analysis_content_request_items_table),
            [
                {
                    "request_id": request_id,
                    "content_id": target.content_id,
                    "content_version": target.content_version,
                    "ordinal": ordinal,
                    "status": "pending",
                }
                for ordinal, target in enumerate(targets)
            ],
        )

    def load_pending(self, request_id: UUID, *, limit: int) -> tuple[AnalysisWorkItem, ...]:
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        request = analysis_content_requests_table
        item = analysis_content_request_items_table
        content = contents_table
        version = content_versions_table
        attempt = provider_request_attempts_table
        provider_request = provider_requests_table
        rows = tuple(
            self._session.execute(
                select(
                    request.c.id.label("request_id"),
                    item.c.ordinal,
                    item.c.content_id,
                    item.c.content_version,
                    content.c.current_version,
                    content.c.platform,
                    content.c.external_content_id,
                    version.c.content_type,
                    version.c.title,
                    version.c.text,
                    version.c.canonical_url,
                    version.c.share_url,
                    version.c.author_snapshot,
                    version.c.published_at,
                    version.c.source_updated_at,
                    version.c.status.label("content_status"),
                    version.c.observed_at,
                    version.c.provider_attempt_id,
                    version.c.raw_artifact_id,
                    provider_request.c.provider,
                    provider_request.c.operation,
                    provider_request.c.id.label("provider_request_id"),
                )
                .select_from(
                    request.join(item, item.c.request_id == request.c.id)
                    .join(content, content.c.id == item.c.content_id)
                    .join(
                        version,
                        (version.c.content_id == item.c.content_id)
                        & (version.c.version_no == item.c.content_version),
                    )
                    .join(attempt, attempt.c.id == version.c.provider_attempt_id)
                    .join(
                        provider_request,
                        provider_request.c.id == attempt.c.provider_request_id,
                    )
                )
                .where(
                    request.c.id == request_id,
                    item.c.status == "pending",
                )
                .order_by(item.c.ordinal)
                .limit(limit)
            ).mappings()
        )
        if not rows:
            request_exists = self._session.scalar(
                select(request.c.id).where(request.c.id == request_id)
            )
            if request_exists is None:
                raise AnalysisRequestNotFound
            return ()

        work: list[AnalysisWorkItem] = []
        for row in rows:
            if row["current_version"] != row["content_version"]:
                self._session.execute(
                    update(item)
                    .where(
                        item.c.request_id == request_id,
                        item.c.content_id == row["content_id"],
                        item.c.status == "pending",
                    )
                    .values(status="stale", error_code="content_version_changed")
                )
                continue
            work.append(_row_to_work_item(row))
        return tuple(work)

    def persist_success(
        self,
        *,
        fence: JobExecutionFence,
        work_item: AnalysisWorkItem,
        analysis: ContentLabelAnalysisV3,
    ) -> AnalysisContentResult | None:
        job = PostgresJobRepository(self._session).lock_current_execution(fence)
        request_job_id = self._session.scalar(
            select(analysis_content_requests_table.c.job_id).where(
                analysis_content_requests_table.c.id == work_item.request_id
            )
        )
        if request_job_id is None:
            raise AnalysisRequestNotFound
        if request_job_id != job.id:
            raise ValueError("Analysis Request 与当前 Job 不匹配")
        current_version = self._session.scalar(
            select(contents_table.c.current_version).where(
                contents_table.c.id == work_item.content_id
            )
        )
        if current_version != work_item.content_version:
            self._session.execute(
                update(analysis_content_request_items_table)
                .where(
                    analysis_content_request_items_table.c.request_id == work_item.request_id,
                    analysis_content_request_items_table.c.content_id == work_item.content_id,
                    analysis_content_request_items_table.c.status == "pending",
                )
                .values(status="stale", error_code="content_version_changed")
            )
            return None

        result = AnalysisContentResult.from_analysis(
            result_id=uuid4(),
            content_id=work_item.content_id,
            content_version=work_item.content_version,
            job_id=job.id,
            analysis=analysis,
        )
        created_id = self._session.scalar(
            pg_insert(analysis_content_results_table)
            .values(
                id=result.id,
                content_id=result.content_id,
                content_version=result.content_version,
                job_id=result.job_id,
                schema_version=result.schema_version,
                relevance=result.relevance,
                voice_type=result.voice_type,
                sentiment=result.sentiment,
                prompt_version=result.prompt_version,
                prompt_sha256=result.prompt_sha256,
                taxonomy_sha256=result.taxonomy_sha256,
                model_provider=result.model_provider,
                model=result.model,
                input_hash=result.input_hash,
                analyzed_at=result.analyzed_at,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(constraint="uq_analysis_content_results_identity")
            .returning(analysis_content_results_table.c.id)
        )
        if created_id is not None:
            self._session.execute(
                insert(analysis_content_label_pairs_table),
                [
                    {
                        "analysis_result_id": created_id,
                        "ordinal": label.ordinal,
                        "primary_label": label.primary_label,
                        "secondary_label": label.secondary_label,
                    }
                    for label in result.labels
                ],
            )
            persisted_id = cast(UUID, created_id)
        else:
            persisted_id = cast(
                UUID,
                self._session.scalar(
                    select(analysis_content_results_table.c.id).where(
                        analysis_content_results_table.c.content_id == result.content_id,
                        analysis_content_results_table.c.content_version == result.content_version,
                        analysis_content_results_table.c.input_hash == result.input_hash,
                        analysis_content_results_table.c.prompt_sha256 == result.prompt_sha256,
                        analysis_content_results_table.c.taxonomy_sha256 == result.taxonomy_sha256,
                        analysis_content_results_table.c.model_provider == result.model_provider,
                        analysis_content_results_table.c.model == result.model,
                    )
                ),
            )
            _assert_same_analysis(self._session, persisted_id, analysis)

        self._session.execute(
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id == work_item.request_id,
                analysis_content_request_items_table.c.content_id == work_item.content_id,
            )
            .values(
                status="succeeded",
                analysis_result_id=persisted_id,
                error_code=None,
            )
        )
        return AnalysisContentResult.from_analysis(
            result_id=persisted_id,
            content_id=work_item.content_id,
            content_version=work_item.content_version,
            job_id=job.id,
            analysis=analysis,
        )

    def mark_failed(
        self,
        *,
        fence: JobExecutionFence,
        request_id: UUID,
        content_id: UUID,
        error_code: str,
    ) -> None:
        PostgresJobRepository(self._session).lock_current_execution(fence)
        self._session.execute(
            update(analysis_content_request_items_table)
            .where(
                analysis_content_request_items_table.c.request_id == request_id,
                analysis_content_request_items_table.c.content_id == content_id,
                analysis_content_request_items_table.c.status == "pending",
            )
            .values(status="failed", error_code=error_code[:200])
        )

    def stats(self, request_id: UUID) -> dict[str, int]:
        statuses = self._session.execute(
            select(
                analysis_content_request_items_table.c.status,
                analysis_content_request_items_table.c.content_id,
            ).where(analysis_content_request_items_table.c.request_id == request_id)
        )
        counts = {"pending": 0, "succeeded": 0, "failed": 0, "stale": 0}
        for status, _ in statuses:
            counts[cast(str, status)] += 1
        return counts


def _row_to_work_item(row: RowMapping) -> AnalysisWorkItem:
    author_snapshot = row["author_snapshot"]
    display_name = _snapshot_text(author_snapshot, "display_name")
    bio = _snapshot_text(author_snapshot, "bio")
    verification_label = _snapshot_text(author_snapshot, "verification_label")
    observed_fields = ["content_type", "title", "text"]
    author = None
    if any(value is not None for value in (display_name, bio, verification_label)):
        author = CanonicalAuthorV1(
            display_name=display_name,
            bio=bio,
            verification_label=verification_label,
        )
        if display_name is not None:
            observed_fields.append("author.display_name")
        if bio is not None:
            observed_fields.append("author.bio")
        if verification_label is not None:
            observed_fields.append("author.verification_label")
    content = CanonicalContentV1(
        platform=cast(str, row["platform"]),
        external_content_id=cast(str, row["external_content_id"]),
        content_type=cast(str, row["content_type"]),
        title=cast(str | None, row["title"]),
        text=cast(str | None, row["text"]),
        canonical_url=_http_url(row["canonical_url"]),
        share_url=_http_url(row["share_url"]),
        author=author,
        published_at=row["published_at"],
        source_updated_at=row["source_updated_at"],
        observed_at=cast(datetime, row["observed_at"]),
        observed_fields=observed_fields,
        metrics=CanonicalMetricsV1(),
        status=cast(str | None, row["content_status"]),
        source=CanonicalSourceV1(
            provider_name=cast(str, row["provider"]),
            operation=cast(str, row["operation"]),
            provider_request_id=str(row["provider_request_id"]),
            provider_attempt_id=str(row["provider_attempt_id"]),
            raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
            observed_at=cast(datetime, row["observed_at"]),
        ),
    )
    return AnalysisWorkItem(
        request_id=cast(UUID, row["request_id"]),
        ordinal=cast(int, row["ordinal"]),
        content_id=cast(UUID, row["content_id"]),
        content_version=cast(int, row["content_version"]),
        content=content,
    )


def _assert_same_analysis(
    session: Session,
    result_id: UUID,
    analysis: ContentLabelAnalysisV3,
) -> None:
    persisted_result = session.execute(
        select(
            analysis_content_results_table.c.schema_version,
            analysis_content_results_table.c.relevance,
            analysis_content_results_table.c.voice_type,
            analysis_content_results_table.c.sentiment,
        ).where(analysis_content_results_table.c.id == result_id)
    ).one()
    expected_result = (
        analysis.schema_version,
        analysis.relevance,
        analysis.voice_type,
        analysis.sentiment,
    )
    if tuple(persisted_result) != expected_result:
        raise ValueError("Analysis 幂等身份对应的相关性/发声类型/情感不一致")

    rows = session.execute(
        select(
            analysis_content_label_pairs_table.c.primary_label,
            analysis_content_label_pairs_table.c.secondary_label,
        )
        .where(analysis_content_label_pairs_table.c.analysis_result_id == result_id)
        .order_by(analysis_content_label_pairs_table.c.ordinal)
    )
    persisted = tuple((cast(str, row[0]), cast(str, row[1])) for row in rows)
    expected = tuple((item.primary_label, item.secondary_label) for item in analysis.labels)
    if persisted != expected:
        raise ValueError("Analysis 幂等身份对应的标签集合不一致")


def _snapshot_text(snapshot: object, key: str) -> str | None:
    if not isinstance(snapshot, dict) or snapshot.get(key) is None:
        return None
    return str(snapshot[key])


def _http_url(value: object) -> AnyHttpUrl | None:
    return _HTTP_URL_ADAPTER.validate_python(value) if value is not None else None


__all__ = ["AnalysisRequestNotFound", "PostgresAnalysisRepository"]
