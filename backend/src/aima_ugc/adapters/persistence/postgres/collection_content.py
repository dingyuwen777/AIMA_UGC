"""Collection live runtime 的 Content 决策读取与 Fenced Ingestion。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.collection import PreviousContentStateV1
from aima_ugc.modules.collection.candidate_tables import collection_candidates_table
from aima_ugc.modules.collection.candidates import (
    CandidateIngestionService,
    CandidateKind,
    IngestionStatus,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import accounts_table, comments_table, contents_table
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .candidates import PostgresCandidateRepository
from .content import PostgresIngestionResult
from .content_complete import PostgresCompleteContentRepository
from .jobs import PostgresJobRepository

_CONTENT_DIRECT_FIELDS = {
    "title": "title",
    "text": "text",
    "canonical_url": "canonical_url",
    "share_url": "share_url",
    "published_at": "published_at",
    "source_updated_at": "source_updated_at",
    "status": "status",
}
_CONTENT_DECISION_METRICS = (
    "like_count",
    "share_count",
    "repost_count",
    "favorite_count",
    "view_count",
    "play_count",
    "danmaku_count",
    "coin_count",
    "download_count",
)


@dataclass(frozen=True, slots=True)
class CollectionContentDecisionState:
    """Decision Service 所需的已存在 Content 最小读取结果。"""

    previous: PreviousContentStateV1
    business_changed: bool


class PostgresCollectionContentStateReader:
    """读取 Content Owner 当前值，并按稀疏 Canonical Observation 判断非评论变化。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def evaluate(self, observation: CanonicalContentV1) -> CollectionContentDecisionState | None:
        session = self._session_factory()
        try:
            with session.begin():
                row = (
                    session.execute(
                        select(
                            contents_table,
                            accounts_table.c.external_account_id.label(
                                "author_external_account_id"
                            ),
                        )
                        .outerjoin(
                            accounts_table,
                            contents_table.c.author_account_id == accounts_table.c.id,
                        )
                        .where(
                            contents_table.c.platform == observation.platform,
                            contents_table.c.external_content_id == observation.external_content_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    return None
                return CollectionContentDecisionState(
                    previous=PreviousContentStateV1(
                        comment_count=row["current_comment_count"],
                    ),
                    business_changed=_business_changed(row, observation),
                )
        finally:
            session.close()

    def known_root_comment_ids(self, content_id: UUID) -> frozenset[str]:
        """一次读取目标内容当前已知一级评论 ID。"""
        session = self._session_factory()
        try:
            with session.begin():
                values = session.scalars(
                    select(comments_table.c.external_comment_id).where(
                        comments_table.c.content_id == content_id,
                        comments_table.c.parent_comment_id.is_(None),
                    )
                ).all()
                return frozenset(str(value) for value in values if value)
        finally:
            session.close()


class PostgresFencedCollectionIngestionWriter:
    """在同一短事务校验 Job Fence/Attempt/Raw 来源后写 Candidate 与 Content Owner。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def discover_candidate(
        self,
        *,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        item_kind: CandidateKind,
        item_locator: str,
        discovered_at: datetime,
        fence: JobExecutionFence,
    ) -> UUID:
        """Mapper 前建立逐项发现事实；external identity 可在映射前未知。"""
        session = self._session_factory()
        try:
            with session.begin():
                _lock_matching_attempt(
                    session,
                    attempt_id=provider_attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    fence=fence,
                )
                candidate = CandidateIngestionService(
                    PostgresCandidateRepository(session)
                ).discover(
                    provider_request_attempt_id=provider_attempt_id,
                    item_kind=item_kind,
                    external_item_id=None,
                    item_locator=item_locator,
                    discovered_at=discovered_at,
                )
                return candidate.id
        finally:
            session.close()

    def record_candidate_failure(
        self,
        *,
        candidate_id: UUID,
        provider_attempt_id: UUID,
        fence: JobExecutionFence,
        result: IngestionStatus,
        error_code: str,
    ) -> None:
        if result not in {"invalid", "unsupported", "failed"}:
            raise ValueError("Candidate failure 结果必须是 invalid/unsupported/failed")
        session = self._session_factory()
        try:
            with session.begin():
                _lock_matching_attempt(
                    session,
                    attempt_id=provider_attempt_id,
                    raw_artifact_id=None,
                    fence=fence,
                )
                _require_candidate_attempt(
                    session,
                    candidate_id=candidate_id,
                    attempt_id=provider_attempt_id,
                )
                CandidateIngestionService(PostgresCandidateRepository(session)).record_ingestion(
                    candidate_id=candidate_id,
                    canonical=None,
                    target_id=None,
                    result=result,
                    error_code=error_code,
                    error_detail=None,
                )
        finally:
            session.close()

    def record_candidate_filtered(
        self,
        *,
        candidate_id: UUID,
        canonical: CanonicalContentV1,
        fence: JobExecutionFence,
    ) -> None:
        """保留已成功映射但未通过全局 Relevance 的 Candidate 终态。"""

        attempt_id = _provider_attempt_id(canonical)
        raw_artifact_id = _raw_artifact_id(canonical)
        session = self._session_factory()
        try:
            with session.begin():
                _lock_matching_attempt(
                    session,
                    attempt_id=attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    fence=fence,
                )
                _require_candidate_attempt(
                    session,
                    candidate_id=candidate_id,
                    attempt_id=attempt_id,
                )
                CandidateIngestionService(PostgresCandidateRepository(session)).record_ingestion(
                    candidate_id=candidate_id,
                    canonical=canonical,
                    target_id=None,
                    result="filtered",
                    error_code=None,
                    error_detail=None,
                )
        finally:
            session.close()

    def ingest_content(
        self,
        *,
        canonical: CanonicalContentV1,
        fence: JobExecutionFence,
        candidate_id: UUID | None = None,
    ) -> PostgresIngestionResult:
        attempt_id = _provider_attempt_id(canonical)
        raw_artifact_id = _raw_artifact_id(canonical)
        item_locator = _item_locator(canonical)
        session = self._session_factory()
        try:
            with session.begin():
                _lock_matching_attempt(
                    session,
                    attempt_id=attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    fence=fence,
                )
                candidate_service = CandidateIngestionService(PostgresCandidateRepository(session))
                if candidate_id is None:
                    candidate = candidate_service.discover(
                        provider_request_attempt_id=attempt_id,
                        item_kind="content",
                        external_item_id=canonical.external_content_id,
                        item_locator=item_locator,
                        discovered_at=canonical.observed_at,
                    )
                    candidate_id = candidate.id
                else:
                    _require_candidate_attempt(
                        session,
                        candidate_id=candidate_id,
                        attempt_id=attempt_id,
                    )
                content_service = ContentIngestionService(
                    PostgresCompleteContentRepository(session)
                )
                result = content_service.ingest_content(canonical)
                candidate_service.record_ingestion(
                    candidate_id=candidate_id,
                    canonical=canonical,
                    target_id=result.target_id,
                    result="ingested",
                )
                return result
        finally:
            session.close()

    def ingest_comment(
        self,
        *,
        canonical: CanonicalCommentV1,
        fence: JobExecutionFence,
        candidate_id: UUID | None = None,
    ) -> PostgresIngestionResult:
        """校验当前 Job Fence 后复用完整 Comment Owner 与 Candidate 账本。"""
        attempt_id = _provider_attempt_id(canonical)
        raw_artifact_id = _raw_artifact_id(canonical)
        item_locator = _item_locator(canonical)
        session = self._session_factory()
        try:
            with session.begin():
                _lock_matching_attempt(
                    session,
                    attempt_id=attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    fence=fence,
                )
                candidate_service = CandidateIngestionService(PostgresCandidateRepository(session))
                if candidate_id is None:
                    candidate = candidate_service.discover(
                        provider_request_attempt_id=attempt_id,
                        item_kind="comment",
                        external_item_id=canonical.external_comment_id,
                        item_locator=item_locator,
                        discovered_at=canonical.observed_at,
                    )
                    candidate_id = candidate.id
                else:
                    _require_candidate_attempt(
                        session,
                        candidate_id=candidate_id,
                        attempt_id=attempt_id,
                    )
                content_service = ContentIngestionService(
                    PostgresCompleteContentRepository(session)
                )
                result = content_service.ingest_comment(canonical)
                candidate_service.record_ingestion(
                    candidate_id=candidate_id,
                    canonical=canonical,
                    target_id=result.target_id,
                    result="ingested",
                )
                return result
        finally:
            session.close()

    def record_comment_coverage(
        self,
        *,
        content_id: UUID,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        platform: str,
        fence: JobExecutionFence,
        coverage: str,
        reported_total: int | None,
        collected_count: int,
        sample_mode: str,
        sort_mode: str,
        target_count: int | None,
        stop_reason: str,
        observed_at: datetime,
    ) -> UUID:
        """校验 Job/Attempt/Raw/Content 平台来源后保存内容级 Coverage。"""
        session = self._session_factory()
        try:
            with session.begin():
                attempt_platform = _lock_matching_attempt(
                    session,
                    attempt_id=provider_attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    fence=fence,
                )
                content_platform = session.scalar(
                    select(contents_table.c.platform).where(contents_table.c.id == content_id)
                )
                if content_platform is None:
                    raise LookupError("Comment Coverage Content 不存在")
                if content_platform != attempt_platform or content_platform != platform:
                    raise ValueError("Comment Coverage Content/Attempt 平台不一致")
                return PostgresCompleteContentRepository(session).record_comment_coverage(
                    content_id=content_id,
                    provider_attempt_id=provider_attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    coverage=coverage,
                    reported_total=reported_total,
                    collected_count=collected_count,
                    sample_mode=sample_mode,
                    sort_mode=sort_mode,
                    target_count=target_count,
                    stop_reason=stop_reason,
                    observed_at=observed_at,
                )
        finally:
            session.close()

    def record_thread_coverage(
        self,
        *,
        content_id: UUID,
        root_comment_id: str,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        platform: str,
        fence: JobExecutionFence,
        coverage: str,
        reported_total: int | None,
        captured_count: int,
        target_count: int | None,
        stop_reason: str,
        observed_at: datetime,
    ) -> UUID:
        session = self._session_factory()
        try:
            with session.begin():
                attempt_platform = _lock_matching_attempt(
                    session,
                    attempt_id=provider_attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    fence=fence,
                )
                content_platform = session.scalar(
                    select(contents_table.c.platform).where(contents_table.c.id == content_id)
                )
                if content_platform is None:
                    raise LookupError("Thread Coverage Content 不存在")
                if content_platform != platform or attempt_platform != platform:
                    raise ValueError("Thread Coverage Content/Attempt 平台不一致")
                return PostgresCompleteContentRepository(session).record_thread_coverage(
                    content_id=content_id,
                    root_comment_id=root_comment_id,
                    provider_attempt_id=provider_attempt_id,
                    raw_artifact_id=raw_artifact_id,
                    coverage=coverage,
                    reported_total=reported_total,
                    captured_count=captured_count,
                    target_count=target_count,
                    stop_reason=stop_reason,
                    observed_at=observed_at,
                )
        finally:
            session.close()


def _lock_matching_attempt(
    session: Session,
    *,
    attempt_id: UUID,
    fence: JobExecutionFence,
    raw_artifact_id: UUID | None,
) -> str:
    PostgresJobRepository(session).lock_current_execution(fence)
    ownership = session.execute(
        select(
            collection_runs_table.c.job_id,
            collection_scopes_table.c.platform,
            provider_request_attempts_table.c.raw_artifact_id,
        )
        .select_from(
            provider_request_attempts_table.join(
                provider_requests_table,
                provider_request_attempts_table.c.provider_request_id
                == provider_requests_table.c.id,
            )
            .join(
                collection_scopes_table,
                provider_requests_table.c.scope_id == collection_scopes_table.c.id,
            )
            .join(
                collection_runs_table,
                collection_scopes_table.c.run_id == collection_runs_table.c.id,
            )
        )
        .where(provider_request_attempts_table.c.id == attempt_id)
    ).one_or_none()
    if ownership is None or ownership.job_id != fence.job_id:
        raise LeaseLostError("Provider Attempt 不属于当前 Job Fence")
    if raw_artifact_id is not None and ownership.raw_artifact_id != raw_artifact_id:
        raise ValueError("Provider Attempt 与 Canonical Raw Artifact 来源不一致")
    return str(ownership.platform)


def _require_candidate_attempt(
    session: Session,
    *,
    candidate_id: UUID,
    attempt_id: UUID,
) -> None:
    persisted = session.scalar(
        select(collection_candidates_table.c.provider_request_attempt_id).where(
            collection_candidates_table.c.id == candidate_id
        )
    )
    if persisted != attempt_id:
        raise ValueError("Candidate 与 Provider Attempt 来源不一致")


def _provider_attempt_id(observation: CanonicalContentV1 | CanonicalCommentV1) -> UUID:
    value = observation.source.provider_attempt_id
    if value is None:
        raise ValueError("Collection live ingestion 要求 provider_attempt_id")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("Collection live ingestion 的 provider_attempt_id 不是 UUID") from exc


def _raw_artifact_id(observation: CanonicalContentV1 | CanonicalCommentV1) -> UUID:
    value = observation.source.raw_artifact_id
    if value is None:
        raise ValueError("Collection live ingestion 要求 raw_artifact_id")
    return value


def _item_locator(observation: CanonicalContentV1 | CanonicalCommentV1) -> str:
    value = observation.source.item_locator
    if value is None or not value.strip():
        raise ValueError("Collection live ingestion 要求非空 item_locator")
    return value.strip()


def _business_changed(row: RowMapping, observation: CanonicalContentV1) -> bool:
    if row["content_type"] != observation.content_type:
        return True

    direct_values = {
        "title": observation.title,
        "text": observation.text,
        "canonical_url": str(observation.canonical_url) if observation.canonical_url else None,
        "share_url": str(observation.share_url) if observation.share_url else None,
        "published_at": observation.published_at,
        "source_updated_at": observation.source_updated_at,
        "status": observation.status,
    }
    for observed_path, column_name in _CONTENT_DIRECT_FIELDS.items():
        if (
            observed_path in observation.observed_fields
            and row[column_name] != direct_values[observed_path]
        ):
            return True

    if "author.external_account_id" in observation.observed_fields:
        external_account_id = (
            observation.author.external_account_id if observation.author is not None else None
        )
        if row["author_external_account_id"] != external_account_id:
            return True

    for name in _CONTENT_DECISION_METRICS:
        if f"metrics.{name}" not in observation.observed_fields:
            continue
        if row[f"current_{name}"] != getattr(observation.metrics, name):
            return True
    return False


__all__ = [
    "CollectionContentDecisionState",
    "PostgresFencedCollectionIngestionWriter",
]
