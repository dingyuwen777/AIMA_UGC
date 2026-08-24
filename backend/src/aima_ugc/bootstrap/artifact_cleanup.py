"""Artifact 保留期限补齐与到期字节清理。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.platform.logging import log_event, log_exception_event
from aima_ugc.platform.storage import ArtifactStateConflict
from aima_ugc.platform.storage.retention import ORPHAN_RETENTION

from .runtime import PlatformRuntime


@dataclass(frozen=True, slots=True)
class ArtifactCleanupResult:
    """一次 housekeeping 的可观察结果。"""

    backfilled: int
    scanned: int
    deleted: int
    failed: int
    skipped_backend: int


def run_artifact_cleanup_once(
    runtime: PlatformRuntime,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> ArtifactCleanupResult:
    """补齐历史 TTL 并分阶段删除到期 Artifact 字节。

    数据库事务只负责状态认领/收敛；实体文件删除始终在事务外执行，避免长 I/O
    持锁。`delete_pending` 会在后续 housekeeping 中继续重试。
    """

    observed_at = datetime.now(UTC) if now is None else now
    if observed_at.utcoffset() is None:
        raise ValueError("Artifact cleanup now 必须包含时区")
    if limit < 1:
        raise ValueError("Artifact cleanup limit 必须大于 0")

    scan_session = runtime.database.new_session()
    try:
        with scan_session.begin():
            repository = PostgresArtifactMetadataRepository(scan_session)
            backfilled = repository.backfill_retention_deadlines()
            candidates = repository.list_cleanup_candidates(
                now=observed_at,
                orphan_before=observed_at - ORPHAN_RETENTION,
                limit=limit,
            )
    finally:
        scan_session.close()

    deleted = 0
    failed = 0
    skipped_backend = 0
    for candidate in candidates:
        if candidate.storage_backend != runtime.artifact_store.backend_name:
            skipped_backend += 1
            log_event(
                runtime.logger,
                logging.WARNING,
                "artifact.cleanup.backend_mismatch",
                "Artifact 后端与当前 Store 不匹配，跳过实体删除",
                artifact_id=str(candidate.id),
                storage_backend=candidate.storage_backend,
            )
            continue

        claim_session = runtime.database.new_session()
        try:
            with claim_session.begin():
                claimed = PostgresArtifactMetadataRepository(claim_session).mark_delete_pending(
                    candidate.id
                )
        except ArtifactStateConflict:
            # 另一 Scheduler/housekeeping 已经完成或改变状态时，本轮不重复处理。
            continue
        finally:
            claim_session.close()
        if claimed.storage_status == "deleted":
            continue

        try:
            runtime.artifact_store.delete(claimed.storage_key)
        except (OSError, ValueError) as exc:
            failed += 1
            log_exception_event(
                runtime.logger,
                logging.WARNING,
                "artifact.cleanup.delete_failed",
                "Artifact 实体删除失败，将保留 delete_pending 供后续重试",
                exc,
                artifact_id=str(claimed.id),
                kind=claimed.kind,
            )
            continue

        finish_session = runtime.database.new_session()
        try:
            with finish_session.begin():
                PostgresArtifactMetadataRepository(finish_session).mark_deleted(
                    claimed.id,
                    deleted_at=observed_at,
                )
            deleted += 1
        except ArtifactStateConflict:
            # 并发清理已经收敛到 deleted 时不把幂等竞争计为删除失败。
            check_session = runtime.database.new_session()
            try:
                with check_session.begin():
                    current = PostgresArtifactMetadataRepository(check_session).get(claimed.id)
                if current is None or current.storage_status != "deleted":
                    failed += 1
            finally:
                check_session.close()
        finally:
            finish_session.close()

    return ArtifactCleanupResult(
        backfilled=backfilled,
        scanned=len(candidates),
        deleted=deleted,
        failed=failed,
        skipped_backend=skipped_backend,
    )


__all__ = ["ArtifactCleanupResult", "run_artifact_cleanup_once"]
