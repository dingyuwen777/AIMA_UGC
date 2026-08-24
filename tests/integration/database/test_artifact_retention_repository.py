from datetime import UTC, datetime, timedelta
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactRecord


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


def test_retention_repository_keeps_provider_raw_out_of_one_day_orphan_cleanup() -> None:
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
