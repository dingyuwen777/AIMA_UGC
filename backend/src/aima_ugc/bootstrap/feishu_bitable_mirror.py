"""飞书独立 Base 与报告内嵌 Base 的持续双向镜像。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Thread
from uuid import UUID, uuid4

from aima_ugc.adapters.feishu import (
    FeishuAPIError,
    FeishuBitableClient,
    FeishuConfig,
    FeishuSyncError,
    FeishuSyncSummary,
)
from aima_ugc.adapters.persistence.postgres.feishu_bitable_mirrors import (
    FeishuBitableMirrorRecord,
    PostgresFeishuBitableMirrorRepository,
)
from aima_ugc.platform.jobs.models import LeaseLostError
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.security import read_secret_file
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

logger = logging.getLogger(__name__)
_MIRROR_INTERVAL_SECONDS = 5
_MAX_FAILURE_BACKOFF_SECONDS = 60
_MIRROR_LEASE_SECONDS = 180
_MIRROR_LEASE_HEARTBEAT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class FeishuBitableMirrorTickResult:
    scanned: int
    succeeded: int
    failed: int
    changed: int


class _MirrorLeaseHeartbeat:
    """在远端长同步期间续租，并在 fencing 失败后阻断后续请求。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        mirror: FeishuBitableMirrorRecord,
        *,
        lease_seconds: int,
        interval_seconds: int,
    ) -> None:
        self._runtime = runtime
        self._mirror = mirror
        self._lease_seconds = lease_seconds
        self._interval_seconds = interval_seconds
        self._stop = Event()
        self._lost = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        self._thread = Thread(
            target=self._run,
            name=f"feishu-mirror-lease-{self._mirror.id}",
            daemon=True,
        )
        self._thread.start()

    def guard(self) -> None:
        if self._lost.is_set():
            raise LeaseLostError("飞书镜像同步 Lease 已丢失")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._interval_seconds, 1) + 1)

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self._renew()
            except Exception as exc:  # noqa: BLE001 - 续租失败必须立即 fencing
                self._lost.set()
                log_event(
                    logger,
                    logging.WARNING,
                    "feishu.bitable_mirror.lease_lost",
                    "镜像同步 Lease 续租失败，已阻断后续飞书请求。",
                    mirror_id=str(self._mirror.id),
                    error_type=type(exc).__name__,
                )
                return

    def _renew(self) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresFeishuBitableMirrorRepository(session).renew_claim(
                    self._mirror.id,
                    claim_token=self._mirror.claim_token or "",
                    lease_seconds=self._lease_seconds,
                )
        finally:
            session.close()


def register_feishu_bitable_mirror(
    runtime: PlatformRuntime,
    summary: FeishuSyncSummary,
    *,
    publication_job_id: UUID | None,
) -> FeishuBitableMirrorRecord:
    required = {
        "document_token": summary.mirror_document_token,
        "document_url": summary.mirror_document_url,
        "external_app_token": summary.target_app_token,
        "external_table_id": summary.target_table_id,
        "embedded_app_token": summary.mirror_app_token,
        "embedded_table_id": summary.mirror_table_id,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("飞书双向镜像注册信息不完整: " + ", ".join(missing))
    session = runtime.database.new_session()
    try:
        with session.begin():
            return PostgresFeishuBitableMirrorRepository(session).register(
                publication_job_id=publication_job_id,
                document_token=str(required["document_token"]),
                document_url=str(required["document_url"]),
                external_app_token=str(required["external_app_token"]),
                external_table_id=str(required["external_table_id"]),
                embedded_app_token=str(required["embedded_app_token"]),
                embedded_table_id=str(required["embedded_table_id"]),
            )
    finally:
        session.close()


class PostgresFeishuBitableMirrorService:
    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._worker_id = f"feishu-mirror-{uuid4().hex}"

    def run_once(self, *, limit: int = 20) -> FeishuBitableMirrorTickResult:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                mirrors = PostgresFeishuBitableMirrorRepository(session).claim_due(
                    worker_id=self._worker_id,
                    limit=limit,
                    lease_seconds=_MIRROR_LEASE_SECONDS,
                )
        finally:
            session.close()
        if not mirrors:
            return FeishuBitableMirrorTickResult(0, 0, 0, 0)

        config = FeishuConfig.from_settings(self._runtime.settings)
        app_secret = read_secret_file(
            self._runtime.settings.external_secret_root / config.app_secret_file,
            root=self._runtime.settings.external_secret_root,
        ).get_secret_value()
        succeeded = 0
        failed = 0
        changed = 0
        for mirror in mirrors:
            heartbeat = _MirrorLeaseHeartbeat(
                self._runtime,
                mirror,
                lease_seconds=_MIRROR_LEASE_SECONDS,
                interval_seconds=_MIRROR_LEASE_HEARTBEAT_SECONDS,
            )
            heartbeat.start()
            try:
                try:
                    heartbeat.guard()
                    with FeishuBitableClient(
                        config=config,
                        app_secret=app_secret,
                        upsert_key_fields=("声音内容/连接",),
                        before_request=heartbeat.guard,
                    ) as client:
                        last_synced_at_ms = (
                            0
                            if mirror.last_synced_at is None
                            else int(mirror.last_synced_at.timestamp() * 1000)
                        )
                        result = client.mirror_records_bidirectionally(
                            external_app_token=mirror.external_app_token,
                            external_table_id=mirror.external_table_id,
                            embedded_app_token=mirror.embedded_app_token,
                            embedded_table_id=mirror.embedded_table_id,
                            known_key_hashes=mirror.known_key_hashes,
                            last_synced_at_ms=last_synced_at_ms,
                        )
                    heartbeat.guard()
                except LeaseLostError:
                    failed += 1
                    log_event(
                        logger,
                        logging.WARNING,
                        "feishu.bitable_mirror.claim_lost",
                        "镜像同步 Lease 已丢失，已停止后续飞书写入。",
                        mirror_id=str(mirror.id),
                    )
                    continue
                except (FeishuAPIError, FeishuSyncError, OSError, ValueError) as exc:
                    failed += 1
                    try:
                        self._mark_failed(mirror, type(exc).__name__)
                    except LeaseLostError:
                        log_event(
                            logger,
                            logging.WARNING,
                            "feishu.bitable_mirror.claim_lost",
                            "镜像失败结果未写回，因为同步 Lease 已被其他 Worker 接管。",
                            mirror_id=str(mirror.id),
                        )
                    log_event(
                        logger,
                        logging.ERROR,
                        "feishu.bitable_mirror.failed",
                        "飞书双向镜像同步失败，将自动重试。",
                        mirror_id=str(mirror.id),
                        document_token_suffix=mirror.document_token[-6:],
                        error_type=type(exc).__name__,
                    )
                    continue

                mutation_count = (
                    result.external_created_count
                    + result.external_updated_count
                    + result.external_deleted_count
                    + result.embedded_created_count
                    + result.embedded_updated_count
                    + result.embedded_deleted_count
                )
                try:
                    self._mark_succeeded(mirror, result.known_key_hashes)
                except LeaseLostError:
                    log_event(
                        logger,
                        logging.WARNING,
                        "feishu.bitable_mirror.claim_lost",
                        "镜像成功结果未写回，因为同步 Lease 已被其他 Worker 接管。",
                        mirror_id=str(mirror.id),
                    )
                    continue
                changed += mutation_count
                succeeded += 1
                if mutation_count:
                    log_event(
                        logger,
                        logging.INFO,
                        "feishu.bitable_mirror.synchronized",
                        "飞书独立表与报告内嵌表已完成双向同步。",
                        mirror_id=str(mirror.id),
                        mutation_count=mutation_count,
                        verified_count=result.verified_count,
                        excluded_fields=list(result.excluded_fields),
                    )
            finally:
                heartbeat.stop()
        return FeishuBitableMirrorTickResult(len(mirrors), succeeded, failed, changed)

    def _mark_succeeded(
        self,
        mirror: FeishuBitableMirrorRecord,
        known_key_hashes: tuple[str, ...],
    ) -> None:
        now = beijing_now()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresFeishuBitableMirrorRepository(session).mark_succeeded(
                    mirror.id,
                    known_key_hashes=known_key_hashes,
                    synced_at=now,
                    next_sync_at=now + timedelta(seconds=_MIRROR_INTERVAL_SECONDS),
                    claim_token=mirror.claim_token or "",
                )
        finally:
            session.close()

    def _mark_failed(self, mirror: FeishuBitableMirrorRecord, error_code: str) -> None:
        delay = min(
            _MAX_FAILURE_BACKOFF_SECONDS,
            _MIRROR_INTERVAL_SECONDS * (2 ** min(mirror.consecutive_failures, 4)),
        )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresFeishuBitableMirrorRepository(session).mark_failed(
                    mirror.id,
                    error_code=error_code,
                    next_sync_at=beijing_now() + timedelta(seconds=delay),
                    claim_token=mirror.claim_token or "",
                )
        finally:
            session.close()


__all__ = [
    "FeishuBitableMirrorTickResult",
    "PostgresFeishuBitableMirrorService",
    "register_feishu_bitable_mirror",
]
