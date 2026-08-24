from dataclasses import replace
from datetime import datetime
from uuid import UUID

import pytest
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService, ArtifactStateConflict


class _AmbiguousMetadata:
    def __init__(self, *, stored_committed_before_error: bool) -> None:
        self.stored_committed_before_error = stored_committed_before_error
        self.records: dict[UUID, ArtifactRecord] = {}

    def create_pending(self, record: ArtifactRecord) -> None:
        self.records[record.id] = record

    def mark_stored(
        self,
        artifact_id: UUID,
        *,
        sha256: str,
        byte_size: int,
        stored_at: datetime,
    ) -> ArtifactRecord:
        if self.stored_committed_before_error:
            self.records[artifact_id] = replace(
                self.records[artifact_id],
                storage_status="stored",
                sha256=sha256,
                byte_size=byte_size,
                stored_at=stored_at,
            )
        raise RuntimeError("artifact confirm failed")

    def mark_linked(self, artifact_id: UUID, *, linked_at: datetime) -> ArtifactRecord:
        raise AssertionError((artifact_id, linked_at))

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        current = self.records[artifact_id]
        if current.storage_status != "pending":
            raise ArtifactStateConflict("Artifact 不是 pending")
        updated = replace(current, storage_status="error")
        self.records[artifact_id] = updated
        return updated


def _stored_files(store: LocalArtifactStore) -> list[object]:
    return [path for path in store.root.rglob("*") if path.is_file()]


def test_confirm_failure_reclaims_bytes_when_pending_cas_proves_no_commit(tmp_path) -> None:
    metadata = _AmbiguousMetadata(stored_committed_before_error=False)
    store = LocalArtifactStore(tmp_path / "artifacts")
    service = ArtifactService(metadata=metadata, store=store)

    with pytest.raises(RuntimeError, match="artifact confirm failed"):
        service.store_bytes(
            kind="content-export.xlsx",
            content_type="application/octet-stream",
            retention_class="export",
            data=b"xlsx",
        )

    record = next(iter(metadata.records.values()))
    assert record.storage_status == "error"
    assert _stored_files(store) == []


def test_confirm_unknown_result_preserves_bytes_when_metadata_may_be_stored(tmp_path) -> None:
    metadata = _AmbiguousMetadata(stored_committed_before_error=True)
    store = LocalArtifactStore(tmp_path / "artifacts")
    service = ArtifactService(metadata=metadata, store=store)

    with pytest.raises(RuntimeError, match="artifact confirm failed"):
        service.store_bytes(
            kind="content-export.xlsx",
            content_type="application/octet-stream",
            retention_class="export",
            data=b"xlsx",
        )

    record = next(iter(metadata.records.values()))
    assert record.storage_status == "stored"
    assert len(_stored_files(store)) == 1
