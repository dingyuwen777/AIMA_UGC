"""Collection live runtime 的 Content 决策读取与 Fenced Ingestion。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.contracts.collection import PreviousContentStateV1
from aima_ugc.modules.collection.candidates import CandidateIngestionService
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .candidates import PostgresCandidateRepository
from .content import PostgresContentRepository, PostgresIngestionResult
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
                            accounts_table.c.external_account_id.label("author_external_account_id"),
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


class PostgresFencedCollectionIngestionWriter:
    """在同一短事务校验 Job Fence/Attempt 来源后复用 Candidate 与 Content Owner 写入口。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def ingest_content(
        self,
        *,
        canonical: CanonicalContentV1,
        fence: JobExecutionFence,
    ) -> PostgresIngestionResult:
        attempt_id = _provider_attempt_id(canonical)
        item_locator = _item_locator(canonical)
        session = self._session_factory()
        try:
            with session.begin():
                _lock_matching_attempt(session, attempt_id=attempt_id, fence=fence)
                candidate_service = CandidateIngestionService(PostgresCandidateRepository(session))
                content_service = ContentIngestionService(PostgresContentRepository(session))
                candidate = candidate_service.discover(
                    provider_request_attempt_id=attempt_id,
                    item_kind="content",
                    external_item_id=canonical.external_content_id,
                    item_locator=item_locator,
                    discovered_at=canonical.observed_at,
                )
                result = content_service.ingest_content(canonical)
                candidate_service.record_ingestion(
                    candidate_id=candidate.id,
                    canonical=canonical,
                    target_id=result.target_id,
                    result="ingested",
                )
                return result
        finally:
            session.close()


def _lock_matching_attempt(
    session: Session,
    *,
    attempt_id: UUID,
    fence: JobExecutionFence,
) -> None:
    PostgresJobRepository(session).lock_current_execution(fence)
    job_id = session.scalar(
        select(collection_runs_table.c.job_id)
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
    )
    if job_id != fence.job_id:
        raise LeaseLostError("Provider Attempt 不属于当前 Job Fence")


def _provider_attempt_id(observation: CanonicalContentV1) -> UUID:
    value = observation.source.provider_attempt_id
    if value is None:
        raise ValueError("Collection live ingestion 要求 provider_attempt_id")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("Collection live ingestion 的 provider_attempt_id 不是 UUID") from exc


def _item_locator(observation: CanonicalContentV1) -> str:
    value = observation.source.item_locator
    if value is None or not value.strip():
        raise ValueError("Collection live ingestion 要求非空 item_locator")
    return value.strip()


def _business_changed(row: object, observation: CanonicalContentV1) -> bool:
    current = row
    if current["content_type"] != observation.content_type:  # type: ignore[index]
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
            and current[column_name] != direct_values[observed_path]  # type: ignore[index]
        ):
            return True

    if observation.author is not None and observation.author.external_account_id is not None:
        if current["author_external_account_id"] != observation.author.external_account_id:  # type: ignore[index]
            return True

    for name in _CONTENT_DECISION_METRICS:
        if f"metrics.{name}" not in observation.observed_fields:
            continue
        if current[f"current_{name}"] != getattr(observation.metrics, name):  # type: ignore[index]
            return True
    return False


__all__ = [
    "CollectionContentDecisionState",
    "PostgresCollectionContentStateReader",
    "PostgresFencedCollectionIngestionWriter",
]
