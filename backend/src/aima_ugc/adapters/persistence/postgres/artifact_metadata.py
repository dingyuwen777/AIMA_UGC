"""Artifact 元数据 PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.platform.storage.models import ArtifactRecord, ArtifactStateConflict
from aima_ugc.platform.storage.tables import artifacts_table


def _artifact_from_row(row: RowMapping) -> ArtifactRecord:
    return ArtifactRecord(
        id=row["id"],
        kind=row["kind"],
        storage_backend=row["storage_backend"],
        storage_key=row["storage_key"],
        content_type=row["content_type"],
        encoding=row["encoding"],
        retention_class=row["retention_class"],
        storage_status=row["storage_status"],
        created_at=row["created_at"],
        sha256=row["sha256"],
        byte_size=row["byte_size"],
        stored_at=row["stored_at"],
        linked_at=row["linked_at"],
        expires_at=row["expires_at"],
        deleted_at=row["deleted_at"],
    )


class PostgresArtifactMetadataRepository:
    """Session-bound Owner Repository；状态转换使用条件更新防竞争。

    调用方为每个元数据阶段使用短事务；ArtifactStore 文件 I/O 不得位于
    同一数据库事务中。跨业务写入的 linked/UoW 协调留到后续阶段。
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(self, record: ArtifactRecord) -> None:
        if record.storage_status != "pending":
            raise ValueError("create_pending 只接受 pending Artifact")
        self._session.execute(
            insert(artifacts_table).values(
                id=record.id,
                kind=record.kind,
                storage_backend=record.storage_backend,
                storage_key=record.storage_key,
                content_type=record.content_type,
                encoding=record.encoding,
                sha256=record.sha256,
                byte_size=record.byte_size,
                retention_class=record.retention_class,
                storage_status=record.storage_status,
                created_at=record.created_at,
                stored_at=record.stored_at,
                linked_at=record.linked_at,
                expires_at=record.expires_at,
                deleted_at=record.deleted_at,
            )
        )

    def get_by_storage_key(self, storage_key: str) -> ArtifactRecord | None:
        row = (
            self._session.execute(
                select(artifacts_table).where(artifacts_table.c.storage_key == storage_key)
            )
            .mappings()
            .one_or_none()
        )
        return _artifact_from_row(row) if row is not None else None

    def get(self, artifact_id: UUID) -> ArtifactRecord | None:
        row = (
            self._session.execute(
                select(artifacts_table).where(artifacts_table.c.id == artifact_id)
            )
            .mappings()
            .one_or_none()
        )
        return _artifact_from_row(row) if row is not None else None

    def mark_stored(
        self,
        artifact_id: UUID,
        *,
        sha256: str,
        byte_size: int,
        stored_at: datetime,
    ) -> ArtifactRecord:
        row = (
            self._session.execute(
                update(artifacts_table)
                .where(
                    artifacts_table.c.id == artifact_id,
                    artifacts_table.c.storage_status == "pending",
                )
                .values(
                    storage_status="stored",
                    sha256=sha256,
                    byte_size=byte_size,
                    stored_at=stored_at,
                )
                .returning(artifacts_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ArtifactStateConflict("Artifact 不是 pending，不能标记为 stored")
        return _artifact_from_row(row)

    def mark_linked(self, artifact_id: UUID, *, linked_at: datetime) -> ArtifactRecord:
        row = (
            self._session.execute(
                update(artifacts_table)
                .where(
                    artifacts_table.c.id == artifact_id,
                    artifacts_table.c.storage_status == "stored",
                )
                .values(storage_status="linked", linked_at=linked_at)
                .returning(artifacts_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ArtifactStateConflict("Artifact 不是 stored，不能标记为 linked")
        return _artifact_from_row(row)

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        row = (
            self._session.execute(
                update(artifacts_table)
                .where(
                    artifacts_table.c.id == artifact_id,
                    artifacts_table.c.storage_status == "pending",
                )
                .values(storage_status="error")
                .returning(artifacts_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ArtifactStateConflict("Artifact 不是 pending，不能标记为 error")
        return _artifact_from_row(row)


class PostgresArtifactMetadataGateway:
    """ArtifactService 使用的分阶段 PostgreSQL 短事务入口。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_pending(self, record: ArtifactRecord) -> None:
        self._run(lambda repository: repository.create_pending(record))

    def mark_stored(
        self,
        artifact_id: UUID,
        *,
        sha256: str,
        byte_size: int,
        stored_at: datetime,
    ) -> ArtifactRecord:
        return self._run(
            lambda repository: repository.mark_stored(
                artifact_id,
                sha256=sha256,
                byte_size=byte_size,
                stored_at=stored_at,
            )
        )

    def mark_linked(self, artifact_id: UUID, *, linked_at: datetime) -> ArtifactRecord:
        return self._run(
            lambda repository: repository.mark_linked(artifact_id, linked_at=linked_at)
        )

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        return self._run(lambda repository: repository.mark_error(artifact_id))

    def _run[T](self, operation: Callable[[PostgresArtifactMetadataRepository], T]) -> T:
        session = self._session_factory()
        try:
            with session.begin():
                return operation(PostgresArtifactMetadataRepository(session))
        finally:
            session.close()
