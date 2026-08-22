"""Raw Envelope 经正式 ArtifactService/LocalArtifactStore 的集成验证。"""

import gzip
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.provider import ProviderRequestV1, RawEnvelopeV1
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportRequest,
    ProviderTransportResponse,
    RawArtifactIntegrityError,
    RawArtifactService,
)
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService


class FakeArtifactMetadata:
    def __init__(self) -> None:
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
        updated = replace(
            self.records[artifact_id],
            storage_status="stored",
            sha256=sha256,
            byte_size=byte_size,
            stored_at=stored_at,
        )
        self.records[artifact_id] = updated
        return updated

    def mark_linked(self, artifact_id: UUID, *, linked_at: datetime) -> ArtifactRecord:
        updated = replace(
            self.records[artifact_id],
            storage_status="linked",
            linked_at=linked_at,
        )
        self.records[artifact_id] = updated
        return updated

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        updated = replace(self.records[artifact_id], storage_status="error")
        self.records[artifact_id] = updated
        return updated


def _isolated_artifact_root() -> Path:
    root = Path(".runtime") / "stage5a-tests" / uuid4().hex
    root.mkdir(parents=True)
    return root


def test_raw_artifact_is_redacted_immutable_and_replayable() -> None:
    requested_at = datetime(2026, 8, 14, 3, 59, tzinfo=UTC)
    completed_at = requested_at + timedelta(seconds=1)
    moments = iter([requested_at, completed_at])
    run_id = uuid4()
    scope_id = uuid4()
    attempt_id = uuid4()
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=run_id,
        scope_id=scope_id,
        provider="fake_provider",
        platform="xiaohongshu",
        operation="keyword_search",
        request_params={"keyword": "爱玛"},
        pagination_input={"page": 1},
    )
    transport = FakeProviderTransport(
        [
            ProviderTransportResponse(
                status_code=200,
                body={
                    "items": [{"id": "note-1", "provider_private": "kept-in-raw"}],
                    "access_token": "must-not-survive",
                    "nested": {"cookie": "also-secret"},
                },
            )
        ]
    )
    dispatch = ProviderClient(
        transport=transport,
        clock=lambda: next(moments),
    ).dispatch(
        request=request,
        attempt_id=attempt_id,
        attempt_no=1,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
            params={"keyword": "爱玛"},
        ),
    )
    metadata = FakeArtifactMetadata()
    store = LocalArtifactStore(_isolated_artifact_root())
    service = RawArtifactService(
        artifacts=ArtifactService(metadata=metadata, store=store),
        store=store,
    )

    captured = service.capture(request=request, dispatch=dispatch)

    expected_suffix = (
        f"raw/fake_provider/xiaohongshu/2026/08/14/{run_id}/{scope_id}/{attempt_id}.json.gz"
    )
    assert captured.artifact.storage_key == expected_suffix
    assert captured.artifact.storage_status == "stored"
    assert captured.attempt.raw_artifact_id == captured.artifact.id
    assert captured.artifact.linked_at is None

    compressed = store.read(captured.artifact.storage_key)
    assert captured.artifact.sha256 == hashlib.sha256(compressed).hexdigest()
    plain = gzip.decompress(compressed)
    assert b"must-not-survive" not in plain
    assert b"also-secret" not in plain
    assert b"kept-in-raw" in plain
    envelope = RawEnvelopeV1.model_validate_json(plain)
    assert envelope.response is not None
    assert envelope.response.body["access_token"] == "[REDACTED]"
    assert service.replay(captured.artifact) == envelope

    original = compressed
    with pytest.raises(FileExistsError):
        service.capture(request=request, dispatch=dispatch)
    assert store.read(captured.artifact.storage_key) == original


def test_raw_replay_rejects_tampered_bytes() -> None:
    metadata = FakeArtifactMetadata()
    store = LocalArtifactStore(_isolated_artifact_root())
    service = RawArtifactService(
        artifacts=ArtifactService(metadata=metadata, store=store),
        store=store,
    )
    requested_at = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    moments = iter([requested_at, requested_at + timedelta(seconds=1)])
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake_provider",
        platform="xiaohongshu",
        operation="keyword_search",
        request_params={"keyword": "爱玛"},
    )
    dispatch = ProviderClient(
        transport=FakeProviderTransport([ProviderTransportResponse(status_code=200, body={})]),
        clock=lambda: next(moments),
    ).dispatch(
        request=request,
        attempt_id=uuid4(),
        attempt_no=1,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )
    captured = service.capture(request=request, dispatch=dispatch)
    target = store.root.joinpath(*captured.artifact.storage_key.split("/"))
    target.write_bytes(b"tampered")

    with pytest.raises(RawArtifactIntegrityError, match="SHA-256"):
        service.replay(captured.artifact)


def test_raw_replay_converts_truncated_gzip_to_integrity_error() -> None:
    metadata = FakeArtifactMetadata()
    store = LocalArtifactStore(_isolated_artifact_root())
    service = RawArtifactService(
        artifacts=ArtifactService(metadata=metadata, store=store),
        store=store,
    )
    requested_at = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    moments = iter([requested_at, requested_at + timedelta(seconds=1)])
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake_provider",
        platform="xiaohongshu",
        operation="keyword_search",
        request_params={"keyword": "爱玛"},
    )
    dispatch = ProviderClient(
        transport=FakeProviderTransport([ProviderTransportResponse(status_code=200, body={})]),
        clock=lambda: next(moments),
    ).dispatch(
        request=request,
        attempt_id=uuid4(),
        attempt_no=1,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )
    captured = service.capture(request=request, dispatch=dispatch)
    target = store.root.joinpath(*captured.artifact.storage_key.split("/"))
    truncated = b"\x1f\x8b"
    target.write_bytes(truncated)
    matching_metadata = replace(
        captured.artifact,
        sha256=hashlib.sha256(truncated).hexdigest(),
        byte_size=len(truncated),
    )

    with pytest.raises(RawArtifactIntegrityError, match="gzip"):
        service.replay(matching_metadata)


def test_raw_replay_converts_missing_file_to_integrity_error() -> None:
    store = LocalArtifactStore(_isolated_artifact_root())
    service = RawArtifactService(
        artifacts=ArtifactService(metadata=FakeArtifactMetadata(), store=store),
        store=store,
    )
    stored_at = datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    missing = ArtifactRecord(
        id=uuid4(),
        kind="provider-raw",
        storage_backend="local",
        storage_key="raw/missing.json.gz",
        content_type="application/json",
        encoding="gzip",
        retention_class="raw",
        storage_status="stored",
        created_at=stored_at,
        sha256="0" * 64,
        byte_size=1,
        stored_at=stored_at,
    )

    with pytest.raises(RawArtifactIntegrityError, match="文件不存在"):
        service.replay(missing)
