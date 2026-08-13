from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactRecord, ArtifactStateConflict


def _pending_record() -> ArtifactRecord:
    artifact_id = uuid4()
    return ArtifactRecord(
        id=artifact_id,
        kind="raw",
        storage_backend="local",
        storage_key=f"raw/{artifact_id}",
        content_type="application/json",
        encoding="gzip",
        retention_class="unresolved",
        storage_status="pending",
        created_at=datetime.now(UTC),
    )


def test_artifact_repository_state_flow() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    record = _pending_record()
    try:
        repository = PostgresArtifactMetadataRepository(session)
        with session.begin():
            repository.create_pending(record)
        with session.begin():
            stored = repository.mark_stored(
                record.id,
                sha256="a" * 64,
                byte_size=128,
                stored_at=datetime.now(UTC),
            )
        with session.begin():
            linked = repository.mark_linked(record.id, linked_at=datetime.now(UTC))
        assert stored.storage_status == "stored"
        assert linked.storage_status == "linked"
    finally:
        session.close()
        runtime.dispose()


def test_artifact_repository_rejects_invalid_transition() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    record = _pending_record()
    try:
        repository = PostgresArtifactMetadataRepository(session)
        with session.begin():
            repository.create_pending(record)
        with pytest.raises(ArtifactStateConflict):
            with session.begin():
                repository.mark_linked(record.id, linked_at=datetime.now(UTC))
    finally:
        session.close()
        runtime.dispose()
