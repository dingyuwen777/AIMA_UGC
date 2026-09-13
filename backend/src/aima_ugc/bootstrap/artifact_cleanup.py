"""Artifact 保留期限补齐、到期字节与媒体缓存容量清理。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.content_media_cache import (
    PostgresContentMediaCacheRepository,
)
from aima_ugc.platform.logging import log_event, log_exception_event
from aima_ugc.platform.storage import ArtifactStateConflict
from aima_ugc.platform.storage.retention import (
    MEDIA_CACHE_MAX_BYTES,
    MEDIA_CACHE_TARGET_BYTES,
    ORPHAN_RETENTION,
)
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_CAPACITY_CLEANUP_LIMIT = 10000


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
    """补齐历史 TTL、删除到期 Artifact，并按 30/24 GiB 水位回收媒体缓存。

    数据库事务只负责状态认领/收敛；实体文件删除始终在事务外执行，避免长 I/O
    持锁。`delete_pending` 会在后续 housekeeping 中继续重试。
    """

    observed_at = beijing_now() if now is None else now
    if observed_at.utcoffset() is None:
        raise ValueError("Artifact cleanup now 必须包含时区")
    if limit < 1:
        raise ValueError("Artifact cleanup limit 必须大于 0")
    orphan_before = observed_at - ORPHAN_RETENTION

    scan_session = runtime.database.new_session()
    try:
        with scan_session.begin():
            repository = PostgresArtifactMetadataRepository(scan_session)
            backfilled = repository.backfill_retention_deadlines()
            candidates = repository.list_cleanup_candidates(
                now=observed_at,
                orphan_before=orphan_before,
                limit=limit,
            )
    finally:
        scan_session.close()

    deleted = 0
    failed = 0
    skipped_backend = 0
    scanned = len(candidates)
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
                    candidate.id,
                    now=observed_at,
                    orphan_before=orphan_before,
                )
        except ArtifactStateConflict:
            continue
        finally:
            claim_session.close()
        if claimed.storage_status == "deleted":
            continue

        deleted_delta, failed_delta = _delete_claimed_artifact(
            runtime,
            artifact_id=claimed.id,
            storage_key=claimed.storage_key,
            kind=claimed.kind,
            deleted_at=observed_at,
        )
        deleted += deleted_delta
        failed += failed_delta

    media_repository = PostgresContentMediaCacheRepository(runtime.database.new_session)
    media_usage = media_repository.usage_bytes()
    if media_usage > MEDIA_CACHE_MAX_BYTES:
        bytes_to_free = media_usage - MEDIA_CACHE_TARGET_BYTES
        capacity_candidates = media_repository.list_oldest_capacity_candidates(
            bytes_to_free=bytes_to_free,
            limit=_CAPACITY_CLEANUP_LIMIT,
        )
        scanned += len(capacity_candidates)
        log_event(
            runtime.logger,
            logging.INFO,
            "artifact.cleanup.media_cache_capacity_started",
            "媒体缓存超过容量高水位，开始按最旧优先回收。",
            usage_bytes=media_usage,
            max_bytes=MEDIA_CACHE_MAX_BYTES,
            target_bytes=MEDIA_CACHE_TARGET_BYTES,
            candidate_count=len(capacity_candidates),
        )
        for candidate in capacity_candidates:
            if not media_repository.claim_capacity_delete(candidate.artifact_id):
                continue
            deleted_delta, failed_delta = _delete_claimed_artifact(
                runtime,
                artifact_id=candidate.artifact_id,
                storage_key=candidate.storage_key,
                kind="content-media-cache",
                deleted_at=observed_at,
            )
            deleted += deleted_delta
            failed += failed_delta

    return ArtifactCleanupResult(
        backfilled=backfilled,
        scanned=scanned,
        deleted=deleted,
        failed=failed,
        skipped_backend=skipped_backend,
    )


def _delete_claimed_artifact(
    runtime: PlatformRuntime,
    *,
    artifact_id: UUID,
    storage_key: str,
    kind: str,
    deleted_at: datetime,
) -> tuple[int, int]:
    """删除一个已认领的 Artifact 字节，并以短事务收敛数据库状态。"""

    try:
        runtime.artifact_store.delete(storage_key)
    except (OSError, ValueError) as exc:
        log_exception_event(
            runtime.logger,
            logging.WARNING,
            "artifact.cleanup.delete_failed",
            "Artifact 实体删除失败，将保留 delete_pending 供后续重试",
            exc,
            artifact_id=str(artifact_id),
            kind=kind,
        )
        return 0, 1

    finish_session = runtime.database.new_session()
    try:
        with finish_session.begin():
            PostgresArtifactMetadataRepository(finish_session).mark_deleted(
                artifact_id,
                deleted_at=deleted_at,
            )
        return 1, 0
    except ArtifactStateConflict:
        check_session = runtime.database.new_session()
        try:
            with check_session.begin():
                current = PostgresArtifactMetadataRepository(check_session).get(artifact_id)
            return (0, 0) if current is not None and current.storage_status == "deleted" else (0, 1)
        finally:
            check_session.close()
    finally:
        finish_session.close()


__all__ = ["ArtifactCleanupResult", "run_artifact_cleanup_once"]
