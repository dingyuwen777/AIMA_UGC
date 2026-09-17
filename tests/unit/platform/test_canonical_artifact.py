from __future__ import annotations

import gzip
import tracemalloc
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService
from aima_ugc.platform.storage.canonical import (
    CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE,
    CANONICAL_CONTENT_ARTIFACT_KIND,
    CanonicalArtifactIntegrityError,
    CanonicalArtifactParent,
    CanonicalArtifactReader,
    CanonicalArtifactWriter,
)

_OBSERVED_AT = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)


class _Metadata:
    """记录 Artifact 生命周期，供共享 Writer/Reader 行为测试使用。"""

    def __init__(self) -> None:
        self.records: dict[UUID, ArtifactRecord] = {}
        self.parents: dict[UUID, CanonicalArtifactParent] = {}

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
        current = self.records[artifact_id]
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
        updated = replace(current, storage_status="linked", linked_at=linked_at)
        self.records[artifact_id] = updated
        return updated

    def link_canonical(
        self,
        artifact_id: UUID,
        *,
        parent: CanonicalArtifactParent,
        linked_at: datetime,
    ) -> ArtifactRecord:
        current = self.records[artifact_id]
        assert current.storage_status == "stored"
        assert artifact_id not in self.parents
        self.parents[artifact_id] = parent
        updated = replace(current, storage_status="linked", linked_at=linked_at)
        self.records[artifact_id] = updated
        return updated

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        current = self.records[artifact_id]
        updated = replace(current, storage_status="error")
        self.records[artifact_id] = updated
        return updated


def _content(
    content_id: str,
    *,
    text: str | None,
    title: str | None = None,
) -> CanonicalContentV1:
    """构造同时覆盖 Unicode、大文本与空可选字段的合法 Canonical。"""

    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=content_id,
        content_type="image",
        title=title,
        text=text,
        observed_at=_OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="excel",
            operation="import",
            source_type="file",
            source_value="爱玛年度数据.xlsx",
            item_locator=f"row:{content_id}",
            observed_at=_OBSERVED_AT,
        ),
        observed_fields=["content_type", "title", "text"],
    )


def _runtime(tmp_path: Path) -> tuple[_Metadata, LocalArtifactStore, ArtifactService]:
    """建立不跨越真实文件系统边界的最小 Artifact 运行环境。"""

    metadata = _Metadata()
    store = LocalArtifactStore(tmp_path / "artifacts")
    artifacts = ArtifactService(metadata=metadata, store=store)
    return metadata, store, artifacts


def _store_linked_payload(
    *,
    artifacts: ArtifactService,
    payload: bytes,
) -> ArtifactRecord:
    """把故障载荷按真实 Artifact 生命周期保存，供 Reader fail-closed 验证。"""

    artifact = artifacts.store_bytes(
        kind=CANONICAL_CONTENT_ARTIFACT_KIND,
        content_type=CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE,
        retention_class="canonical",
        data=payload,
        encoding="gzip",
        storage_key=f"canonical-content.v1/{uuid4()}.jsonl.gz",
    )
    return artifacts.link_canonical(
        artifact.id,
        parent=CanonicalArtifactParent(processing_import_batch_id=uuid4()),
    )


def test_canonical_parent_requires_exactly_one_real_parent() -> None:
    with pytest.raises(ValueError, match="恰好一个"):
        CanonicalArtifactParent()
    with pytest.raises(ValueError, match="恰好一个"):
        CanonicalArtifactParent(
            processing_import_batch_id=uuid4(),
            provider_attempt_id=uuid4(),
        )


def test_writer_store_reader_round_trip_preserves_current_contract(tmp_path: Path) -> None:
    metadata, store, artifacts = _runtime(tmp_path)
    records = (
        _content("note-1", title="爱玛\U0001f6f5", text="中文正文"),
        _content("note-2", title=None, text="长文本" * 131_072),
        _content("note-3", title=None, text=None),
    )
    writer = CanonicalArtifactWriter(artifacts=artifacts, temporary_directory=tmp_path)

    artifact = writer.write(
        iter(records),
        parent=CanonicalArtifactParent(processing_import_batch_id=uuid4()),
        retention_class="canonical",
        max_bytes=4 * 1024 * 1024,
    )

    assert artifact.storage_status == "linked"
    assert artifact.kind == CANONICAL_CONTENT_ARTIFACT_KIND
    assert artifact.content_type == CANONICAL_CONTENT_ARTIFACT_CONTENT_TYPE
    assert artifact.encoding == "gzip"
    assert artifact.storage_key.endswith(".jsonl.gz")
    assert metadata.parents[artifact.id].processing_import_batch_id is not None
    assert tuple(CanonicalArtifactReader(store=store).read(artifact)) == records


def test_writer_output_is_reproducible_for_semantically_equal_records(tmp_path: Path) -> None:
    _, store, artifacts = _runtime(tmp_path)
    record = _content("note-1", title="爱玛", text="同一份输入")
    writer = CanonicalArtifactWriter(artifacts=artifacts, temporary_directory=tmp_path)

    first = writer.write(
        [record],
        parent=CanonicalArtifactParent(collection_scope_id=uuid4()),
        retention_class="canonical",
        max_bytes=1024 * 1024,
    )
    second = writer.write(
        [record.model_copy(deep=True)],
        parent=CanonicalArtifactParent(provider_attempt_id=uuid4()),
        retention_class="canonical",
        max_bytes=1024 * 1024,
    )

    assert store.read(first.storage_key) == store.read(second.storage_key)
    assert first.sha256 == second.sha256
    assert first.byte_size == second.byte_size


def test_writer_memory_is_bounded_by_a_record_not_the_dataset(tmp_path: Path) -> None:
    _, _, artifacts = _runtime(tmp_path)
    base = _content("note-0", title=None, text="爱玛" * 32_768)
    records = (
        base.model_copy(update={"external_content_id": f"note-{index}"}) for index in range(256)
    )
    writer = CanonicalArtifactWriter(artifacts=artifacts, temporary_directory=tmp_path)

    tracemalloc.start()
    try:
        writer.write(
            records,
            parent=CanonicalArtifactParent(historical_import_campaign_item_id=uuid4()),
            retention_class="canonical",
            max_bytes=4 * 1024 * 1024,
        )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < 8 * 1024 * 1024


def test_reader_rejects_integrity_mismatch_before_yielding(tmp_path: Path) -> None:
    _, store, artifacts = _runtime(tmp_path)
    artifact = CanonicalArtifactWriter(
        artifacts=artifacts,
        temporary_directory=tmp_path,
    ).write(
        [_content("note-1", title=None, text="正文")],
        parent=CanonicalArtifactParent(collection_scope_id=uuid4()),
        retention_class="canonical",
        max_bytes=1024 * 1024,
    )
    mismatched = replace(artifact, sha256="0" * 64)
    yielded: list[CanonicalContentV1] = []

    with pytest.raises(CanonicalArtifactIntegrityError, match="SHA-256"):
        for record in CanonicalArtifactReader(store=store).read(mismatched):
            yielded.append(record)

    assert yielded == []


def test_reader_rejects_byte_size_mismatch_before_yielding(tmp_path: Path) -> None:
    _, store, artifacts = _runtime(tmp_path)
    artifact = CanonicalArtifactWriter(
        artifacts=artifacts,
        temporary_directory=tmp_path,
    ).write(
        [_content("note-1", title=None, text="正文")],
        parent=CanonicalArtifactParent(collection_scope_id=uuid4()),
        retention_class="canonical",
        max_bytes=1024 * 1024,
    )
    assert artifact.byte_size is not None
    mismatched = replace(artifact, byte_size=artifact.byte_size + 1)
    yielded: list[CanonicalContentV1] = []

    with pytest.raises(CanonicalArtifactIntegrityError, match="字节大小"):
        for record in CanonicalArtifactReader(store=store).read(mismatched):
            yielded.append(record)

    assert yielded == []


def test_reader_preflights_truncated_gzip_before_yielding_valid_prefix(tmp_path: Path) -> None:
    _, store, artifacts = _runtime(tmp_path)
    plain = (
        b"\n".join(
            [
                _content("note-1", title=None, text="第一条").model_dump_json().encode(),
                _content("note-2", title=None, text="第二条").model_dump_json().encode(),
            ]
        )
        + b"\n"
    )
    artifact = _store_linked_payload(
        artifacts=artifacts,
        payload=gzip.compress(plain, mtime=0)[:-4],
    )
    yielded: list[CanonicalContentV1] = []

    with pytest.raises(CanonicalArtifactIntegrityError, match="gzip"):
        for record in CanonicalArtifactReader(store=store).read(artifact):
            yielded.append(record)

    assert yielded == []


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"not-gzip", "gzip"),
        (gzip.compress(b"{invalid-json}\n", mtime=0), "JSON"),
        (gzip.compress(b'{"schema_version":"content.v1"}\n', mtime=0), "Contract"),
    ],
)
def test_reader_rejects_invalid_payload_before_yielding(
    tmp_path: Path,
    payload: bytes,
    message: str,
) -> None:
    _, store, artifacts = _runtime(tmp_path)
    artifact = _store_linked_payload(artifacts=artifacts, payload=payload)
    yielded: list[CanonicalContentV1] = []

    with pytest.raises(CanonicalArtifactIntegrityError, match=message):
        for record in CanonicalArtifactReader(store=store).read(artifact):
            yielded.append(record)

    assert yielded == []
