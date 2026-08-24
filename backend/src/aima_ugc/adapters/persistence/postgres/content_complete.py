"""完整 PostgreSQL Content Owner：核心 Current/History + Canonical 子实体。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Table, delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.modules.collection.tables import provider_request_attempts_table
from aima_ugc.modules.content.extended_tables import (
    comment_locations_table,
    comment_media_table,
    comment_mentions_table,
    comment_thread_coverage_observations_table,
    content_external_ids_table,
    content_locations_table,
    content_media_table,
    content_mentions_table,
    content_topics_table,
)
from aima_ugc.modules.content.tables import (
    comment_versions_table,
    comments_table,
    content_versions_table,
    contents_table,
)

from .content import PostgresContentRepository, PostgresIngestionResult

_CONTENT_COLLECTION_FIELDS = {
    "alternate_ids": content_external_ids_table,
    "media": content_media_table,
    "topics": content_topics_table,
    "mentions": content_mentions_table,
    "locations": content_locations_table,
}
_COMMENT_COLLECTION_FIELDS = {
    "media": comment_media_table,
    "mentions": comment_mentions_table,
    "locations": comment_locations_table,
}


class PostgresCompleteContentRepository:
    """调用方拥有事务；核心与子实体在同一 Session 原子提交。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._core = PostgresContentRepository(session)

    def ingest_content(self, observation: CanonicalContentV1) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        _require_attempt_raw_pair(self._session, attempt_id=attempt_id, raw_id=raw_id)
        result = self._core.ingest_content(observation)
        result = self._apply_content_null_author(observation, result, attempt_id, raw_id)
        self._sync_content_extensions(
            result.target_id,
            observation,
            attempt_id=attempt_id,
            raw_id=raw_id,
        )
        return result

    def ingest_comment(self, observation: CanonicalCommentV1) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        _require_attempt_raw_pair(self._session, attempt_id=attempt_id, raw_id=raw_id)
        result = self._core.ingest_comment(observation)
        result = self._apply_comment_null_author(observation, result, attempt_id, raw_id)
        self._sync_comment_extensions(
            result.target_id,
            observation,
            attempt_id=attempt_id,
            raw_id=raw_id,
        )
        return result

    def record_comment_coverage(self, **kwargs: Any) -> UUID:
        return self._core.record_comment_coverage(**kwargs)

    def record_thread_coverage(
        self,
        *,
        content_id: UUID,
        root_comment_id: str,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        coverage: str,
        reported_total: int | None,
        captured_count: int,
        target_count: int | None,
        stop_reason: str,
        observed_at: datetime,
    ) -> UUID:
        if coverage not in {"complete", "partial", "not_requested", "unavailable"}:
            raise ValueError("Thread Coverage 状态非法")
        if not root_comment_id.strip():
            raise ValueError("Thread Coverage root_comment_id 不能为空")
        if reported_total is not None and reported_total < 0:
            raise ValueError("Thread Coverage reported_total 不能为负数")
        if captured_count < 0:
            raise ValueError("Thread Coverage captured_count 不能为负数")
        if target_count is not None and target_count < 0:
            raise ValueError("Thread Coverage target_count 不能为负数")
        if observed_at.utcoffset() is None:
            raise ValueError("Thread Coverage observed_at 必须包含时区")
        if not stop_reason.strip():
            raise ValueError("Thread Coverage stop_reason 不能为空")
        if coverage in {"not_requested", "unavailable"} and captured_count != 0:
            raise ValueError("未请求/不可用 Thread Coverage 不能包含已采集回复")
        if (
            coverage == "complete"
            and reported_total is not None
            and captured_count < reported_total
        ):
            raise ValueError("complete Thread Coverage 的采集数不能小于 Provider 报告总数")
        statement = pg_insert(comment_thread_coverage_observations_table).values(
            id=uuid4(),
            content_id=content_id,
            root_comment_id=root_comment_id.strip(),
            provider_attempt_id=provider_attempt_id,
            raw_artifact_id=raw_artifact_id,
            coverage=coverage,
            reported_total=reported_total,
            captured_count=captured_count,
            target_count=target_count,
            stop_reason=stop_reason.strip(),
            observed_at=observed_at,
        )
        row_id = self._session.execute(
            statement.on_conflict_do_update(
                constraint="uq_comment_thread_coverage_source",
                set_={
                    "coverage": statement.excluded.coverage,
                    "reported_total": statement.excluded.reported_total,
                    "captured_count": statement.excluded.captured_count,
                    "target_count": statement.excluded.target_count,
                    "stop_reason": statement.excluded.stop_reason,
                    "observed_at": statement.excluded.observed_at,
                },
            ).returning(comment_thread_coverage_observations_table.c.id)
        ).scalar_one()
        return cast(UUID, row_id)

    def _sync_content_extensions(
        self,
        content_id: UUID,
        observation: CanonicalContentV1,
        *,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        for field_name, table in _CONTENT_COLLECTION_FIELDS.items():
            if field_name not in observation.observed_fields:
                continue
            if field_name == "alternate_ids":
                # 父级 freshness 只记录最近观察时刻，不阻止较旧来源补充此前缺失的 id_type。
                _claim_collection_freshness(
                    self._session,
                    parent_table=contents_table,
                    parent_id=content_id,
                    field_name=field_name,
                    observed_at=observation.observed_at,
                )
                rows = _content_extension_rows(
                    field_name,
                    content_id,
                    observation,
                    attempt_id=attempt_id,
                    raw_id=raw_id,
                )
                for row in rows:
                    statement = pg_insert(table).values(**row)
                    self._session.execute(
                        statement.on_conflict_do_update(
                            index_elements=[table.c.content_id, table.c.id_type],
                            set_={
                                "external_id": statement.excluded.external_id,
                                "provider_attempt_id": statement.excluded.provider_attempt_id,
                                "raw_artifact_id": statement.excluded.raw_artifact_id,
                                "observed_at": statement.excluded.observed_at,
                            },
                            where=table.c.observed_at <= statement.excluded.observed_at,
                        )
                    )
                continue
            if not _claim_collection_freshness(
                self._session,
                parent_table=contents_table,
                parent_id=content_id,
                field_name=field_name,
                observed_at=observation.observed_at,
            ):
                continue
            self._session.execute(delete(table).where(table.c.content_id == content_id))
            rows = _content_extension_rows(
                field_name,
                content_id,
                observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            if rows:
                self._session.execute(insert(table).values(rows))

    def _sync_comment_extensions(
        self,
        comment_id: UUID,
        observation: CanonicalCommentV1,
        *,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        for field_name, table in _COMMENT_COLLECTION_FIELDS.items():
            if field_name not in observation.observed_fields:
                continue
            if not _claim_collection_freshness(
                self._session,
                parent_table=comments_table,
                parent_id=comment_id,
                field_name=field_name,
                observed_at=observation.observed_at,
            ):
                continue
            self._session.execute(delete(table).where(table.c.comment_id == comment_id))
            rows = _comment_extension_rows(
                field_name,
                comment_id,
                observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            if rows:
                self._session.execute(insert(table).values(rows))

    def _apply_content_null_author(
        self,
        observation: CanonicalContentV1,
        result: PostgresIngestionResult,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> PostgresIngestionResult:
        if "author.external_account_id" not in observation.observed_fields:
            return result
        if observation.author is not None and observation.author.external_account_id is not None:
            return result
        row = _lock_parent(self._session, contents_table, result.target_id)
        accepted, freshness = _accept_field_freshness(
            row,
            "author.external_account_id",
            observation.observed_at,
        )
        if not accepted:
            return result
        changed = row["author_account_id"] is not None
        version_no = int(row["current_version"])
        if changed and not result.version_created:
            version_no += 1
        self._session.execute(
            update(contents_table)
            .where(contents_table.c.id == result.target_id)
            .values(
                author_account_id=None,
                field_observed_at=freshness,
                current_version=version_no,
                updated_at=max(row["updated_at"], observation.observed_at),
            )
        )
        if changed and not result.version_created:
            self._session.execute(
                insert(content_versions_table).values(
                    id=uuid4(),
                    content_id=result.target_id,
                    version_no=version_no,
                    content_type=row["content_type"],
                    title=row["title"],
                    text=row["text"],
                    canonical_url=row["canonical_url"],
                    share_url=row["share_url"],
                    author_snapshot=None,
                    published_at=row["published_at"],
                    source_updated_at=row["source_updated_at"],
                    status=row["status"],
                    provider_attempt_id=attempt_id,
                    raw_artifact_id=raw_id,
                    observed_at=observation.observed_at,
                )
            )
            return PostgresIngestionResult(
                result.target_id,
                version_no,
                True,
                result.metric_recorded,
            )
        return result

    def _apply_comment_null_author(
        self,
        observation: CanonicalCommentV1,
        result: PostgresIngestionResult,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> PostgresIngestionResult:
        if "author.external_account_id" not in observation.observed_fields:
            return result
        if observation.author is not None and observation.author.external_account_id is not None:
            return result
        row = _lock_parent(self._session, comments_table, result.target_id)
        accepted, freshness = _accept_field_freshness(
            row,
            "author.external_account_id",
            observation.observed_at,
        )
        if not accepted:
            return result
        changed = row["author_account_id"] is not None
        version_no = int(row["current_version"])
        if changed and not result.version_created:
            version_no += 1
        self._session.execute(
            update(comments_table)
            .where(comments_table.c.id == result.target_id)
            .values(
                author_account_id=None,
                field_observed_at=freshness,
                current_version=version_no,
                updated_at=max(row["updated_at"], observation.observed_at),
            )
        )
        if changed and not result.version_created:
            self._session.execute(
                insert(comment_versions_table).values(
                    id=uuid4(),
                    comment_id=result.target_id,
                    version_no=version_no,
                    root_comment_id=row["root_comment_id"],
                    parent_comment_id=row["parent_comment_id"],
                    text=row["text"],
                    author_snapshot=None,
                    published_at=row["published_at"],
                    source_updated_at=row["source_updated_at"],
                    status=row["status"],
                    is_by_content_author=row["is_by_content_author"],
                    provider_attempt_id=attempt_id,
                    raw_artifact_id=raw_id,
                    observed_at=observation.observed_at,
                )
            )
            return PostgresIngestionResult(
                result.target_id,
                version_no,
                True,
                result.metric_recorded,
            )
        return result


def _source_ids(
    observation: CanonicalContentV1 | CanonicalCommentV1,
) -> tuple[UUID, UUID]:
    attempt = observation.source.provider_attempt_id
    raw_id = observation.source.raw_artifact_id
    if attempt is None or raw_id is None:
        raise ValueError("完整 PostgreSQL Content 摄取要求 Attempt 与 Raw 来源")
    return UUID(attempt), raw_id


def _require_attempt_raw_pair(session: Session, *, attempt_id: UUID, raw_id: UUID) -> None:
    persisted = session.scalar(
        select(provider_request_attempts_table.c.raw_artifact_id).where(
            provider_request_attempts_table.c.id == attempt_id
        )
    )
    if persisted != raw_id:
        raise ValueError("Canonical Provider Attempt 与 Raw Artifact 来源不一致")


def _lock_parent(session: Session, table: Table, parent_id: UUID) -> dict[str, Any]:
    return dict(
        session.execute(select(table).where(table.c.id == parent_id).with_for_update())
        .mappings()
        .one()
    )


def _accept_field_freshness(
    row: dict[str, Any],
    field_name: str,
    observed_at: datetime,
) -> tuple[bool, dict[str, str]]:
    raw = row.get("field_observed_at") or {}
    if not isinstance(raw, dict):
        raise ValueError("Current field_observed_at 必须是对象")
    freshness = {str(key): str(value) for key, value in raw.items()}
    previous_raw = freshness.get(field_name)
    if previous_raw is not None:
        previous_at = datetime.fromisoformat(previous_raw)
        if previous_at.utcoffset() is None:
            raise ValueError("Current field_observed_at 必须包含时区")
        if observed_at < previous_at:
            return False, freshness
    freshness[field_name] = observed_at.isoformat()
    return True, freshness


def _claim_collection_freshness(
    session: Session,
    *,
    parent_table: Table,
    parent_id: UUID,
    field_name: str,
    observed_at: datetime,
) -> bool:
    row = _lock_parent(session, parent_table, parent_id)
    accepted, freshness = _accept_field_freshness(row, field_name, observed_at)
    if not accepted:
        return False
    session.execute(
        update(parent_table)
        .where(parent_table.c.id == parent_id)
        .values(
            field_observed_at=freshness,
            updated_at=max(row["updated_at"], observed_at),
        )
    )
    return True


def _source_values(attempt_id: UUID, raw_id: UUID, observed_at: datetime) -> dict[str, object]:
    return {
        "provider_attempt_id": attempt_id,
        "raw_artifact_id": raw_id,
        "observed_at": observed_at,
    }


def _content_extension_rows(
    field_name: str,
    content_id: UUID,
    observation: CanonicalContentV1,
    *,
    attempt_id: UUID,
    raw_id: UUID,
) -> list[dict[str, object]]:
    source = _source_values(attempt_id, raw_id, observation.observed_at)
    if field_name == "alternate_ids":
        return [
            {
                "content_id": content_id,
                "id_type": id_type,
                "external_id": external_id,
                **source,
            }
            for id_type, external_id in sorted(observation.alternate_ids.items())
        ]
    if field_name == "media":
        return [
            {"content_id": content_id, **_media_values(item, index), **source}
            for index, item in enumerate(observation.media)
        ]
    if field_name == "topics":
        return [
            {
                "content_id": content_id,
                "position": index,
                "name": item.name,
                "external_topic_id": item.external_topic_id,
                "url": str(item.url) if item.url is not None else None,
                **source,
            }
            for index, item in enumerate(observation.topics)
        ]
    if field_name == "mentions":
        return [
            {"content_id": content_id, **_mention_values(item, index), **source}
            for index, item in enumerate(observation.mentions)
        ]
    if field_name == "locations":
        return [
            {"content_id": content_id, **_location_values(item, index), **source}
            for index, item in enumerate(observation.locations)
        ]
    raise ValueError(f"未知 Content 扩展字段: {field_name}")


def _comment_extension_rows(
    field_name: str,
    comment_id: UUID,
    observation: CanonicalCommentV1,
    *,
    attempt_id: UUID,
    raw_id: UUID,
) -> list[dict[str, object]]:
    source = _source_values(attempt_id, raw_id, observation.observed_at)
    if field_name == "media":
        return [
            {"comment_id": comment_id, **_media_values(item, index), **source}
            for index, item in enumerate(observation.media)
        ]
    if field_name == "mentions":
        return [
            {"comment_id": comment_id, **_mention_values(item, index), **source}
            for index, item in enumerate(observation.mentions)
        ]
    if field_name == "locations":
        return [
            {"comment_id": comment_id, **_location_values(item, index), **source}
            for index, item in enumerate(observation.locations)
        ]
    raise ValueError(f"未知 Comment 扩展字段: {field_name}")


def _media_values(item, fallback_position: int) -> dict[str, object]:  # type: ignore[no-untyped-def]
    position = item.position if item.position is not None else fallback_position
    return {
        "position": position,
        "media_type": item.media_type,
        "external_media_id": item.external_media_id,
        "url": str(item.url) if item.url is not None else None,
        "preview_url": str(item.preview_url) if item.preview_url is not None else None,
        "width": item.width,
        "height": item.height,
        "duration_ms": item.duration_ms,
        "mime_type": item.mime_type,
        "alt_text": item.alt_text,
    }


def _mention_values(item, position: int) -> dict[str, object]:  # type: ignore[no-untyped-def]
    account = item.account
    return {
        "position": position,
        "external_account_id": account.external_account_id,
        "handle": account.handle,
        "display_name": account.display_name,
        "profile_url": str(account.profile_url) if account.profile_url is not None else None,
        "avatar_url": str(account.avatar_url) if account.avatar_url is not None else None,
        "bio": account.bio,
        "verified": account.verified,
        "verification_label": account.verification_label,
        "region": account.region,
        "follower_count": account.follower_count,
        "following_count": account.following_count,
        "content_count": account.content_count,
        "total_like_count": account.total_like_count,
        "alternate_ids": dict(account.alternate_ids),
        "display_text": item.display_text,
    }


def _location_values(item, position: int) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "position": position,
        "location_type": item.location_type,
        "label": item.label,
        "country": item.country,
        "region": item.region,
        "city": item.city,
        "latitude": item.latitude,
        "longitude": item.longitude,
    }


__all__ = ["PostgresCompleteContentRepository"]
