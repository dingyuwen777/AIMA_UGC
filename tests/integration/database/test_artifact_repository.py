from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.artifact_metadata import PostgresArtifactMetadataRepository
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactRecord


def test_artifact_repository_state_flow() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    artifact_id = uuid4()
    record = ArtifactRecord(
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
    try:
        repository = PostgresArtifactMetadataRepository(session)
        with session.begin():
            repository.create_pending(record)
        with session.begin():
            stored = repository.mark_stored(
                artifact_id,
                sha256="a" * 64,
                byte_size=128,
                stored_at=datetime.now(UTC),
            )
        with session.begin():
            linked = repository.mark_linked(artifact_id, linked_at=datetime.now(UTC))
        assert stored.storage_status == "stored"
        assert linked.storage_status == "linked"
    finally:
        session.close()
        runtime.dispose()
