"""Artifact 元数据 PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.reporting.tables import reporting_data_exports_table
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.models import ArtifactRecord, ArtifactStateConflict
from aima_ugc.platform.storage.retention import (
    EXPORT_RETENTION,
    IMPORT_SOURCE_RETENTION,
    PROVIDER_RAW_RETENTION,
)
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


def _affected_rows(result: object) -> int:
    """读取 DML rowcount，同时保持 SQLAlchemy Result 的静态类型边界。"""

    rowcount = getattr(result, "rowcount", 0)
    return rowcount if isinstance(rowcount, int) and rowcount > 0 else 0


def _cleanup_eligibility(*, now: datetime, orphan_before: datetime) -> ColumnElement[bool]:
    """按当前数据库事实判断 Artifact 是否仍可进入删除认领。

    候选扫描与删除认领之间可能有业务事务建立正式引用，因此真正的 UPDATE CAS
    必须复用同一判定，而不能把之前扫描到的候选列表当作删除授权。
    """

    import_referenced = exists(
        select(processing_import_batches_table.c.id).where(
            processing_import_batches_table.c.input_artifact_id == artifacts_table.c.id
        )
    )
    export_referenced = exists(
        select(reporting_data_exports_table.c.id).where(
            reporting_data_exports_table.c.artifact_id == artifacts_table.c.id
        )
    )
    historical_referenced = exists(
        select(historical_import_campaign_items_table.c.id).where(
            historical_import_campaign_items_table.c.artifact_id == artifacts_table.c.id
        )
    )
    expired = and_(
        artifacts_table.c.storage_status.in_(("stored", "linked")),
        artifacts_table.c.expires_at.is_not(None),
        artifacts_table.c.expires_at <= now,
    )
    orphaned = and_(
        artifacts_table.c.storage_status == "stored",
        artifacts_table.c.created_at <= orphan_before,
        or_(
            and_(artifacts_table.c.kind == "file-import.raw", ~import_referenced),
            and_(artifacts_table.c.kind == "content-export.xlsx", ~export_referenced),
            and_(
                artifacts_table.c.kind.in_(("historical-import.source", "historical-import.chunk")),
                ~historical_referenced,
            ),
        ),
    )
    return or_(expired, orphaned)


class PostgresArtifactMetadataRepository:
    """Session-bound Owner Repository；状态转换使用条件更新防竞争。

    调用方为每个元数据阶段使用短事务；ArtifactStore 文件 I/O 不得位于
    同一数据库事务中。删除同样先提交 delete_pending，再做文件 I/O，最后
    以短事务收敛到 deleted。
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

    def backfill_retention_deadlines(self) -> int:
        """幂等补齐历史 Artifact 的 expires_at，不改已经显式存在的截止时间。"""

        mutable_statuses = ("stored", "linked", "delete_pending")
        provider_result = self._session.execute(
            update(artifacts_table)
            .where(
                artifacts_table.c.kind == "provider-raw",
                artifacts_table.c.expires_at.is_(None),
                artifacts_table.c.storage_status.in_(mutable_statuses),
            )
            .values(
                expires_at=(
                    func.coalesce(artifacts_table.c.stored_at, artifacts_table.c.created_at)
                    + PROVIDER_RAW_RETENTION
                )
            )
        )

        export_completed_at = (
            select(reporting_data_exports_table.c.completed_at)
            .where(
                reporting_data_exports_table.c.artifact_id == artifacts_table.c.id,
                reporting_data_exports_table.c.completed_at.is_not(None),
            )
            .scalar_subquery()
        )
        export_result = self._session.execute(
            update(artifacts_table)
            .where(
                artifacts_table.c.kind == "content-export.xlsx",
                artifacts_table.c.expires_at.is_(None),
                artifacts_table.c.storage_status.in_(mutable_statuses),
                export_completed_at.is_not(None),
            )
            .values(expires_at=export_completed_at + EXPORT_RETENTION)
        )

        terminal_statuses = ("succeeded", "failed", "cancelled")
        batch_jobs = processing_import_batches_table.outerjoin(
            jobs_table,
            processing_import_batches_table.c.job_id == jobs_table.c.id,
        )
        terminal_at = (
            select(
                func.max(
                    func.coalesce(
                        processing_import_batches_table.c.finished_at,
                        jobs_table.c.finished_at,
                    )
                )
            )
            .select_from(batch_jobs)
            .where(
                processing_import_batches_table.c.input_artifact_id == artifacts_table.c.id,
                or_(
                    processing_import_batches_table.c.finished_at.is_not(None),
                    and_(
                        jobs_table.c.status.in_(terminal_statuses),
                        jobs_table.c.finished_at.is_not(None),
                    ),
                ),
            )
            .scalar_subquery()
        )
        unfinished_import = exists(
            select(processing_import_batches_table.c.id)
            .select_from(batch_jobs)
            .where(
                processing_import_batches_table.c.input_artifact_id == artifacts_table.c.id,
                processing_import_batches_table.c.finished_at.is_(None),
                or_(
                    processing_import_batches_table.c.job_id.is_(None),
                    ~jobs_table.c.status.in_(terminal_statuses),
                    jobs_table.c.finished_at.is_(None),
                ),
            )
        )
        import_result = self._session.execute(
            update(artifacts_table)
            .where(
                artifacts_table.c.kind == "file-import.raw",
                artifacts_table.c.expires_at.is_(None),
                artifacts_table.c.storage_status.in_(mutable_statuses),
                terminal_at.is_not(None),
                ~unfinished_import,
            )
            .values(expires_at=terminal_at + IMPORT_SOURCE_RETENTION)
        )
        return (
            _affected_rows(provider_result)
            + _affected_rows(export_result)
            + _affected_rows(import_result)
        )

    def list_cleanup_candidates(
        self,
        *,
        now: datetime,
        orphan_before: datetime,
        limit: int,
    ) -> tuple[ArtifactRecord, ...]:
        """返回到期或确定未引用的安全清理候选。

        Provider Raw 不进入 1 天孤儿规则，因为 dispatching Attempt 的 Recovery 会按
        确定性 storage_key 找回尚未 linked 的 Raw；它只按 30 天正式保留期清理。
        """

        if now.utcoffset() is None or orphan_before.utcoffset() is None:
            raise ValueError("Artifact cleanup 时间必须包含时区")
        if limit < 1:
            raise ValueError("Artifact cleanup limit 必须大于 0")

        rows = (
            self._session.execute(
                select(artifacts_table)
                .where(
                    or_(
                        artifacts_table.c.storage_status == "delete_pending",
                        _cleanup_eligibility(now=now, orphan_before=orphan_before),
                    )
                )
                .order_by(artifacts_table.c.created_at, artifacts_table.c.id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return tuple(_artifact_from_row(row) for row in rows)

    def mark_delete_pending(
        self,
        artifact_id: UUID,
        *,
        now: datetime,
        orphan_before: datetime,
    ) -> ArtifactRecord:
        """以当前数据库事实 CAS 认领删除；候选扫描本身不构成删除授权。"""

        if now.utcoffset() is None or orphan_before.utcoffset() is None:
            raise ValueError("Artifact cleanup 时间必须包含时区")

        row = (
            self._session.execute(
                update(artifacts_table)
                .where(
                    artifacts_table.c.id == artifact_id,
                    _cleanup_eligibility(now=now, orphan_before=orphan_before),
                )
                .values(storage_status="delete_pending")
                .returning(artifacts_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            return _artifact_from_row(row)
        current = self.get(artifact_id)
        if current is not None and current.storage_status in {"delete_pending", "deleted"}:
            return current
        raise ArtifactStateConflict("Artifact 当前状态或引用关系不能进入 delete_pending")

    def mark_deleted(self, artifact_id: UUID, *, deleted_at: datetime) -> ArtifactRecord:
        """实体字节删除成功后把 delete_pending 收敛为 deleted。"""

        row = (
            self._session.execute(
                update(artifacts_table)
                .where(
                    artifacts_table.c.id == artifact_id,
                    artifacts_table.c.storage_status == "delete_pending",
                )
                .values(storage_status="deleted", deleted_at=deleted_at)
                .returning(artifacts_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            return _artifact_from_row(row)
        current = self.get(artifact_id)
        if current is not None and current.storage_status == "deleted":
            return current
        raise ArtifactStateConflict("Artifact 不是 delete_pending，不能标记为 deleted")


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
