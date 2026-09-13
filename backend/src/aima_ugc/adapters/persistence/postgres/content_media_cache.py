"""Content Media Cache 的 PostgreSQL 读写适配器。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.media_cache_tables import content_media_cache_entries_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.storage.tables import artifacts_table


@dataclass(frozen=True, slots=True)
class ContentMediaSource:
    """可缓存的一个 Content 媒体源。"""

    content_id: UUID
    position: int
    platform: str
    media_type: str
    source_url: str | None


@dataclass(frozen=True, slots=True)
class ContentMediaCacheBinding:
    """媒体位置当前缓存 Artifact 的只读快照。"""

    artifact_id: UUID
    source_url_hash: str
    storage_key: str
    content_type: str
    storage_status: str
    byte_size: int | None
    created_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class MediaCacheDeleteCandidate:
    """容量回收需要删除的缓存 Artifact。"""

    artifact_id: UUID
    storage_key: str
    byte_size: int


class PostgresContentMediaCacheRepository:
    """用短事务维护媒体源、缓存绑定与容量回收。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def get_source(self, content_id: UUID, position: int) -> ContentMediaSource | None:
        """读取指定位置的当前媒体源。"""

        return self._read(lambda session: self._source_query(session, content_id, position))

    def list_sources(self, content_id: UUID) -> tuple[ContentMediaSource, ...]:
        """读取一个 Content 的全部媒体源并保持 position 顺序。"""

        def load(session: Session) -> tuple[ContentMediaSource, ...]:
            rows = session.execute(
                select(
                    content_media_table.c.content_id,
                    content_media_table.c.position,
                    contents_table.c.platform,
                    content_media_table.c.media_type,
                    content_media_table.c.url,
                )
                .join(contents_table, contents_table.c.id == content_media_table.c.content_id)
                .where(content_media_table.c.content_id == content_id)
                .order_by(content_media_table.c.position)
            ).mappings()
            return tuple(_source_from_row(row) for row in rows)

        return self._read(load)

    def get_binding(self, content_id: UUID, position: int) -> ContentMediaCacheBinding | None:
        """读取当前位置绑定的 Artifact 与当前存储状态。"""

        def load(session: Session) -> ContentMediaCacheBinding | None:
            row = (
                session.execute(
                    select(
                        content_media_cache_entries_table.c.source_url_hash,
                        artifacts_table.c.id.label("artifact_id"),
                        artifacts_table.c.storage_key,
                        artifacts_table.c.content_type,
                        artifacts_table.c.storage_status,
                        artifacts_table.c.byte_size,
                        artifacts_table.c.created_at,
                        artifacts_table.c.expires_at,
                    )
                    .join(
                        artifacts_table,
                        artifacts_table.c.id == content_media_cache_entries_table.c.artifact_id,
                    )
                    .where(
                        content_media_cache_entries_table.c.content_id == content_id,
                        content_media_cache_entries_table.c.position == position,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return ContentMediaCacheBinding(
                artifact_id=cast(UUID, row["artifact_id"]),
                source_url_hash=cast(str, row["source_url_hash"]),
                storage_key=cast(str, row["storage_key"]),
                content_type=cast(str, row["content_type"]),
                storage_status=cast(str, row["storage_status"]),
                byte_size=cast(int | None, row["byte_size"]),
                created_at=cast(datetime, row["created_at"]),
                expires_at=cast(datetime | None, row["expires_at"]),
            )

        return self._read(load)

    def bind(
        self,
        *,
        content_id: UUID,
        position: int,
        source_url_hash: str,
        artifact_id: UUID,
        cached_at: datetime,
    ) -> None:
        """原子替换一个媒体位置的当前缓存绑定。"""

        if len(source_url_hash) != 64:
            raise ValueError("source_url_hash 必须是 SHA-256")
        statement = pg_insert(content_media_cache_entries_table).values(
            content_id=content_id,
            position=position,
            source_url_hash=source_url_hash,
            artifact_id=artifact_id,
            cached_at=cached_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=(
                content_media_cache_entries_table.c.content_id,
                content_media_cache_entries_table.c.position,
            ),
            set_={
                "source_url_hash": statement.excluded.source_url_hash,
                "artifact_id": statement.excluded.artifact_id,
                "cached_at": statement.excluded.cached_at,
            },
        )
        self._write(lambda session: session.execute(statement))

    def usage_bytes(self) -> int:
        """统计仍占用实体存储的媒体缓存字节。"""

        def load(session: Session) -> int:
            return cast(
                int,
                session.scalar(
                    select(func.coalesce(func.sum(artifacts_table.c.byte_size), 0)).where(
                        artifacts_table.c.kind == "content-media-cache",
                        artifacts_table.c.storage_status.in_(
                            ("stored", "linked", "delete_pending")
                        ),
                    )
                )
                or 0,
            )

        return self._read(load)

    def list_oldest_capacity_candidates(
        self,
        *,
        bytes_to_free: int,
        limit: int = 10000,
    ) -> tuple[MediaCacheDeleteCandidate, ...]:
        """按最旧优先返回足以接近容量目标的一批缓存 Artifact。"""

        if bytes_to_free <= 0:
            return ()

        def load(session: Session) -> tuple[MediaCacheDeleteCandidate, ...]:
            rows = session.execute(
                select(
                    artifacts_table.c.id,
                    artifacts_table.c.storage_key,
                    artifacts_table.c.byte_size,
                )
                .where(
                    artifacts_table.c.kind == "content-media-cache",
                    artifacts_table.c.storage_status.in_(("stored", "linked")),
                    artifacts_table.c.byte_size.is_not(None),
                )
                .order_by(artifacts_table.c.created_at, artifacts_table.c.id)
                .limit(limit)
            ).all()
            selected: list[MediaCacheDeleteCandidate] = []
            accumulated = 0
            for artifact_id, storage_key, byte_size in rows:
                size = int(byte_size or 0)
                selected.append(
                    MediaCacheDeleteCandidate(
                        artifact_id=cast(UUID, artifact_id),
                        storage_key=cast(str, storage_key),
                        byte_size=size,
                    )
                )
                accumulated += size
                if accumulated >= bytes_to_free:
                    break
            return tuple(selected)

        return self._read(load)

    def claim_capacity_delete(self, artifact_id: UUID) -> bool:
        """仅对仍活跃的 media-cache Artifact CAS 认领容量删除。"""

        def claim(session: Session) -> bool:
            result = session.execute(
                update(artifacts_table)
                .where(
                    artifacts_table.c.id == artifact_id,
                    artifacts_table.c.kind == "content-media-cache",
                    artifacts_table.c.storage_status.in_(("stored", "linked")),
                )
                .values(storage_status="delete_pending")
            )
            rowcount = getattr(result, "rowcount", 0)
            return bool(isinstance(rowcount, int) and rowcount > 0)

        return self._write(claim)

    @staticmethod
    def _source_query(
        session: Session,
        content_id: UUID,
        position: int,
    ) -> ContentMediaSource | None:
        row = (
            session.execute(
                select(
                    content_media_table.c.content_id,
                    content_media_table.c.position,
                    contents_table.c.platform,
                    content_media_table.c.media_type,
                    content_media_table.c.url,
                )
                .join(contents_table, contents_table.c.id == content_media_table.c.content_id)
                .where(
                    content_media_table.c.content_id == content_id,
                    content_media_table.c.position == position,
                )
            )
            .mappings()
            .one_or_none()
        )
        return _source_from_row(row) if row is not None else None

    def _read[T](self, operation: Callable[[Session], T]) -> T:
        session = self._session_factory()
        try:
            with session.begin():
                return operation(session)
        finally:
            session.close()

    def _write[T](self, operation: Callable[[Session], T]) -> T:
        return self._read(operation)


def _source_from_row(row: object) -> ContentMediaSource:
    mapping = cast(dict[str, object], row)
    return ContentMediaSource(
        content_id=cast(UUID, mapping["content_id"]),
        position=cast(int, mapping["position"]),
        platform=cast(str, mapping["platform"]),
        media_type=cast(str, mapping["media_type"]),
        source_url=cast(str | None, mapping["url"]),
    )


__all__ = [
    "ContentMediaCacheBinding",
    "ContentMediaSource",
    "MediaCacheDeleteCandidate",
    "PostgresContentMediaCacheRepository",
]
