import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.manual_ingestion import (
    PostgresProcessingImportBatchRepository,
)
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.artifact_cleanup import run_artifact_cleanup_once
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactRecord
from aima_ugc.platform.storage.retention import IMPORT_SOURCE_RETENTION


def _store_record(
    repository: PostgresArtifactMetadataRepository,
    *,
    kind: str,
    created_at: datetime,
    expires_at: datetime | None,
) -> ArtifactRecord:
    artifact_id = uuid4()
    pending = ArtifactRecord(
        id=artifact_id,
        kind=kind,
        storage_backend="local",
        storage_key=f"{kind}/{artifact_id}",
        content_type="application/octet-stream",
        encoding=None,
        retention_class="test",
        storage_status="pending",
        created_at=created_at,
        expires_at=expires_at,
    )
    repository.create_pending(pending)
    return repository.mark_stored(
        artifact_id,
        sha256="a" * 64,
        byte_size=4,
        stored_at=created_at,
    )


def test_provider_raw_is_not_a_one_day_orphan() -> None:
    runtime = DatabaseRuntime(load_settings())
    now = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    session = runtime.new_session()
    try:
        with session.begin():
            repository = PostgresArtifactMetadataRepository(session)
            provider_raw = _store_record(
                repository,
                kind="provider-raw",
                created_at=now - timedelta(days=2),
                expires_at=now + timedelta(days=28),
            )
            import_orphan = _store_record(
                repository,
                kind="file-import.raw",
                created_at=now - timedelta(days=2),
                expires_at=None,
            )

        with session.begin():
            candidates = PostgresArtifactMetadataRepository(session).list_cleanup_candidates(
                now=now,
                orphan_before=now - timedelta(days=1),
                limit=100,
            )

        candidate_ids = {item.id for item in candidates}
        assert import_orphan.id in candidate_ids
        assert provider_raw.id not in candidate_ids
    finally:
        session.close()
        runtime.dispose()


def test_retention_repository_converges_expired_artifact_to_deleted() -> None:
    runtime = DatabaseRuntime(load_settings())
    now = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    session = runtime.new_session()
    try:
        with session.begin():
            repository = PostgresArtifactMetadataRepository(session)
            expired = _store_record(
                repository,
                kind="content-export.xlsx",
                created_at=now - timedelta(days=8),
                expires_at=now - timedelta(days=1),
            )

        with session.begin():
            repository = PostgresArtifactMetadataRepository(session)
            candidates = repository.list_cleanup_candidates(
                now=now,
                orphan_before=now - timedelta(days=1),
                limit=100,
            )
            assert expired.id in {item.id for item in candidates}
            claimed = repository.mark_delete_pending(expired.id)
            assert claimed.storage_status == "delete_pending"

        with session.begin():
            deleted = PostgresArtifactMetadataRepository(session).mark_deleted(
                expired.id,
                deleted_at=now,
            )
            assert deleted.storage_status == "deleted"
            assert deleted.deleted_at == now
    finally:
        session.close()
        runtime.dispose()


def test_import_source_waits_for_terminal_job_and_uses_cancel_time() -> None:
    runtime = DatabaseRuntime(load_settings())
    created_at = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    batch_id = uuid4()
    session = runtime.new_session()
    try:
        with session.begin():
            artifacts = PostgresArtifactMetadataRepository(session)
            source = _store_record(
                artifacts,
                kind="file-import.raw",
                created_at=created_at,
                expires_at=None,
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="ingestion.import-excel.v1",
                payload_version="1",
                payload={},
                internal_idempotency_key=f"retention-test:{batch_id}",
                request_id="retention-test",
                priority=0,
                max_attempts=1,
                timeout_seconds=60,
            )
            PostgresProcessingImportBatchRepository(session).create(
                batch_id=batch_id,
                input_artifact_id=source.id,
                job_id=job.id,
            )
            artifacts.mark_linked(source.id, linked_at=created_at)

        with session.begin():
            repository = PostgresArtifactMetadataRepository(session)
            repository.backfill_retention_deadlines()
            active = repository.get(source.id)
            assert active is not None
            assert active.expires_at is None

        with session.begin():
            cancelled = PostgresJobRepository(session).request_cancel(job.id)
            assert cancelled.status == "cancelled"
            assert cancelled.finished_at is not None

        with session.begin():
            repository = PostgresArtifactMetadataRepository(session)
            repository.backfill_retention_deadlines()
            terminal = repository.get(source.id)
            assert terminal is not None
            assert terminal.expires_at == cancelled.finished_at + IMPORT_SOURCE_RETENTION
    finally:
        session.close()
        runtime.dispose()


def test_cleanup_once_deletes_expired_local_bytes_and_marks_metadata(tmp_path) -> None:
    settings = load_settings()
    database = DatabaseRuntime(settings)
    store = LocalArtifactStore(tmp_path / "artifacts")
    runtime = PlatformRuntime(
        service="artifact-retention-test",
        settings=settings,
        database=database,
        artifact_store=store,
        logger=logging.getLogger("artifact-retention-test"),
    )
    now = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    session = database.new_session()
    try:
        with session.begin():
            repository = PostgresArtifactMetadataRepository(session)
            expired = _store_record(
                repository,
                kind="content-export.xlsx",
                created_at=now - timedelta(days=8),
                expires_at=now - timedelta(days=1),
            )
            repository.mark_linked(expired.id, linked_at=now - timedelta(days=8))

        store.put(expired.storage_key, b"xlsx")
        assert store.exists(expired.storage_key)

        result = run_artifact_cleanup_once(runtime, now=now, limit=100)
        assert result.deleted >= 1
        assert not store.exists(expired.storage_key)

        with session.begin():
            deleted = PostgresArtifactMetadataRepository(session).get(expired.id)
            assert deleted is not None
            assert deleted.storage_status == "deleted"
            assert deleted.deleted_at == now
    finally:
        session.close()
        database.dispose()
