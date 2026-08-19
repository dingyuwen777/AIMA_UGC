"""Stage 6 小红书 Raw 回放的 PostgreSQL 来源读取与摄取适配。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.candidates import PostgresCandidateRepository
from aima_ugc.adapters.persistence.postgres.content import PostgresIngestionResult
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XhsMappingContext,
    map_comment,
    map_content,
)
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import extract_search_items
from aima_ugc.contracts.provider import RawEnvelopeV1
from aima_ugc.modules.collection.candidates import CandidateIngestionService
from aima_ugc.modules.collection.tables import (
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.collection.xhs_replay import XhsReplaySource, XhsReplaySummary
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.platform.storage import ArtifactRecord
from aima_ugc.platform.storage.models import ArtifactStatus
from aima_ugc.platform.storage.tables import artifacts_table

SessionFactory = Callable[[], Session]


class PostgresXhsReplaySourceReader:
    """只读数据库来源链，拒绝非 completed/linked Raw。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def load(self, provider_attempt_id: UUID) -> XhsReplaySource:
        session = self._session_factory()
        try:
            row = (
                session.execute(
                    select(
                        provider_request_attempts_table.c.id.label("attempt_id"),
                        provider_request_attempts_table.c.dispatch_status,
                        provider_requests_table.c.id.label("request_id"),
                        provider_requests_table.c.provider,
                        provider_requests_table.c.operation,
                        collection_scopes_table.c.platform,
                        collection_scopes_table.c.source_type,
                        collection_scopes_table.c.source_value,
                        *artifacts_table.c,
                    )
                    .join(
                        provider_requests_table,
                        provider_requests_table.c.id
                        == provider_request_attempts_table.c.provider_request_id,
                    )
                    .join(
                        collection_scopes_table,
                        collection_scopes_table.c.id == provider_requests_table.c.scope_id,
                    )
                    .join(
                        artifacts_table,
                        artifacts_table.c.id == provider_request_attempts_table.c.raw_artifact_id,
                    )
                    .where(provider_request_attempts_table.c.id == provider_attempt_id)
                )
                .mappings()
                .one()
            )
            if row["dispatch_status"] != "completed":
                raise ValueError("Raw Replay 只接受 completed Provider Attempt")
            if row["storage_status"] != "linked":
                raise ValueError("Raw Replay 只接受 linked Raw Artifact")
            return XhsReplaySource(
                provider_attempt_id=cast(UUID, row["attempt_id"]),
                provider_request_id=cast(UUID, row["request_id"]),
                provider=cast(str, row["provider"]),
                platform=cast(str, row["platform"]),
                operation=cast(str, row["operation"]),
                source_type=cast(str, row["source_type"]),
                source_value=cast(str, row["source_value"]),
                artifact=_artifact_from_row(row),
            )
        finally:
            session.close()


class PostgresXhsReplayIngestionWriter:
    """在一个短事务内把已校验 Raw 转成 Candidate/Canonical/完整业务事实。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def ingest(self, source: XhsReplaySource, envelope: RawEnvelopeV1) -> XhsReplaySummary:
        body = envelope.response.body if envelope.response is not None else None
        if not isinstance(body, dict):
            raise ValueError("XHS Raw Replay 要求响应 body 为 JSON Object")
        session = self._session_factory()
        try:
            with session.begin():
                candidates = CandidateIngestionService(PostgresCandidateRepository(session))
                content: ContentIngestionService[PostgresIngestionResult] = ContentIngestionService(
                    PostgresCompleteContentRepository(session)
                )
                context = XhsMappingContext(
                    provider_request_id=str(source.provider_request_id),
                    provider_attempt_id=str(source.provider_attempt_id),
                    raw_artifact_id=source.artifact.id,
                    operation=source.operation,
                    source_type=source.source_type,
                    source_value=source.source_value,
                    observed_at=envelope.completed_at,
                    root_comment_id=_root_comment_id(source.operation, envelope),
                )
                if source.operation == "search_notes":
                    count = _ingest_search_items(
                        body=cast(dict[str, Any], body),
                        source=source,
                        context=context,
                        candidates=candidates,
                        content=content,
                    )
                    return XhsReplaySummary(content_count=count)
                if source.operation in {"get_image_note_detail", "get_video_note_detail"}:
                    raw_item = _find_content_item(cast(dict[str, Any], body))
                    external_id = _external_id(raw_item)
                    candidate = candidates.discover(
                        provider_request_attempt_id=source.provider_attempt_id,
                        item_kind="content",
                        external_item_id=external_id,
                        item_locator=f"note:{external_id}",
                        discovered_at=envelope.completed_at,
                    )
                    canonical = map_content(raw_item, context, item_locator=candidate.item_locator)
                    result = content.ingest_content(canonical)
                    candidates.record_ingestion(
                        candidate_id=candidate.id,
                        canonical=canonical,
                        target_id=result.target_id,
                        result="ingested",
                    )
                    return XhsReplaySummary(content_count=1)
                if source.operation in {"get_note_comments", "get_note_sub_comments"}:
                    count = _ingest_comments(
                        body=cast(dict[str, Any], body),
                        source=source,
                        context=context,
                        candidates=candidates,
                        content=content,
                        is_root=source.operation == "get_note_comments",
                        observed_at=envelope.completed_at,
                    )
                    return XhsReplaySummary(comment_count=count)
                raise ValueError(f"Stage 6 不支持的 XHS Raw Replay Operation: {source.operation}")
        finally:
            session.close()


def _ingest_search_items(
    *,
    body: dict[str, Any],
    source: XhsReplaySource,
    context: XhsMappingContext,
    candidates: CandidateIngestionService,
    content: ContentIngestionService[PostgresIngestionResult],
) -> int:
    count = 0
    for raw_item in extract_search_items(body):
        external_id = _external_id(raw_item)
        locator = f"note:{external_id}"
        candidate = candidates.discover(
            provider_request_attempt_id=source.provider_attempt_id,
            item_kind="content",
            external_item_id=external_id,
            item_locator=locator,
            discovered_at=context.observed_at,
        )
        canonical = map_content(raw_item, context, item_locator=locator)
        result = content.ingest_content(canonical)
        candidates.record_ingestion(
            candidate_id=candidate.id,
            canonical=canonical,
            target_id=result.target_id,
            result="ingested",
        )
        count += 1
    return count


def _ingest_comments(
    *,
    body: dict[str, Any],
    source: XhsReplaySource,
    context: XhsMappingContext,
    candidates: CandidateIngestionService,
    content: ContentIngestionService[PostgresIngestionResult],
    is_root: bool,
    observed_at: datetime,
) -> int:
    count = 0
    for raw_comment in _find_comment_items(body):
        external_id = _external_id(raw_comment)
        locator = f"comment:{external_id}"
        candidate = candidates.discover(
            provider_request_attempt_id=source.provider_attempt_id,
            item_kind="comment",
            external_item_id=external_id,
            item_locator=locator,
            discovered_at=observed_at,
        )
        canonical = map_comment(
            raw_comment,
            context,
            item_locator=locator,
            is_root=is_root,
        )
        result = content.ingest_comment(canonical)
        candidates.record_ingestion(
            candidate_id=candidate.id,
            canonical=canonical,
            target_id=result.target_id,
            result="ingested",
        )
        count += 1
    return count


def _root_comment_id(operation: str, envelope: RawEnvelopeV1) -> str | None:
    if operation != "get_note_sub_comments":
        return None
    value = envelope.request.params.get("comment_id")
    return str(value) if value is not None else None


def _find_content_item(body: dict[str, Any]) -> dict[str, Any]:
    current: object = body
    for _ in range(6):
        if not isinstance(current, dict):
            break
        note = current.get("note")
        if isinstance(note, dict):
            return cast(dict[str, Any], note)
        if any(key in current for key in ("id", "note_id")):
            return cast(dict[str, Any], current)
        current = current.get("data")
    raise ValueError("详情 Raw 中未找到可映射的笔记对象")


def _find_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    current: object = body
    for _ in range(6):
        if not isinstance(current, dict):
            break
        comments = current.get("comments")
        if isinstance(comments, list):
            return tuple(cast(dict[str, Any], item) for item in comments if isinstance(item, dict))
        current = current.get("data")
    return ()


def _external_id(raw: dict[str, Any]) -> str:
    note = raw.get("note")
    if isinstance(note, dict):
        raw = cast(dict[str, Any], note)
    value = raw.get("id") or raw.get("note_id") or raw.get("comment_id")
    if value is None or not str(value).strip():
        raise ValueError("Raw Item 缺少稳定外部 ID")
    return str(value)


def _artifact_from_row(row: RowMapping) -> ArtifactRecord:
    return ArtifactRecord(
        id=cast(UUID, row["id"]),
        kind=cast(str, row["kind"]),
        storage_backend=cast(str, row["storage_backend"]),
        storage_key=cast(str, row["storage_key"]),
        content_type=cast(str, row["content_type"]),
        encoding=cast(str | None, row["encoding"]),
        sha256=cast(str | None, row["sha256"]),
        byte_size=cast(int | None, row["byte_size"]),
        retention_class=cast(str, row["retention_class"]),
        storage_status=cast(ArtifactStatus, row["storage_status"]),
        created_at=cast(datetime, row["created_at"]),
        stored_at=cast(datetime | None, row["stored_at"]),
        linked_at=cast(datetime | None, row["linked_at"]),
        expires_at=cast(datetime | None, row["expires_at"]),
        deleted_at=cast(datetime | None, row["deleted_at"]),
    )
