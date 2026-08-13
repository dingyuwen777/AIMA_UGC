from dataclasses import replace
from datetime import datetime
from uuid import UUID

from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService


class FakeArtifactMetadata:
    def __init__(self) -> None:
        self.records: dict[UUID, ArtifactRecord] = {}

    def create_pending(self, record: ArtifactRecord) -> None:
        assert record.storage_status == "pending"
        self.records[record.id] = record

    def mark_stored(
        self,
        artifact_id: UUID,
        *,
        sha256: str,
        byte_size: int,
        stored_at: datetime,
    ) -> ArtifactRecord:
        current = self.records[artifact_id]
        assert current.storage_status == "pending"
        updated = replace(
            current,
            storage_status="stored",
            sha256=sha256,
            byte_size=byte_size,
            stored_at=stored_at,
        )
        self.records[artifact_id] = updated
        return updated

    def mark_linked(self, artifact_id: UUID, *, linked_at: datetime) -> ArtifactRecord:
        current = self.records[artifact_id]
        assert current.storage_status == "stored"
        updated = replace(current, storage_status="linked", linked_at=linked_at)
        self.records[artifact_id] = updated
        return updated

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        current = self.records[artifact_id]
        updated = replace(current, storage_status="error")
        self.records[artifact_id] = updated
        return updated


def test_artifact_service_owns_pending_stored_linked_lifecycle(tmp_path) -> None:
    metadata = FakeArtifactMetadata()
    store = LocalArtifactStore(tmp_path / "artifacts")
    service = ArtifactService(metadata=metadata, store=store)

    stored = service.store_bytes(
        kind="raw",
        content_type="application/json",
        retention_class="raw-default",
        data=b'{"ok":true}',
        encoding="utf-8",
    )

    assert stored.storage_status == "stored"
    assert stored.storage_backend == "local"
    assert stored.sha256 is not None
    assert stored.byte_size == 11
    assert store.read(stored.storage_key) == b'{"ok":true}'

    linked = service.link(stored.id)
    assert linked.storage_status == "linked"
    assert linked.linked_at is not None
