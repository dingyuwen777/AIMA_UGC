"""Provider Raw 成功落盘后的稳定结构化事件回归。"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportRequest,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService


class _Metadata:
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
        stored = replace(
            self.records[artifact_id],
            storage_status="stored",
            sha256=sha256,
            byte_size=byte_size,
            stored_at=stored_at,
        )
        self.records[artifact_id] = stored
        return stored

    def mark_linked(self, artifact_id: UUID, *, linked_at: datetime) -> ArtifactRecord:
        linked = replace(
            self.records[artifact_id],
            storage_status="linked",
            linked_at=linked_at,
        )
        self.records[artifact_id] = linked
        return linked

    def mark_error(self, artifact_id: UUID) -> ArtifactRecord:
        errored = replace(self.records[artifact_id], storage_status="error")
        self.records[artifact_id] = errored
        return errored


def test_raw_capture_emits_stored_event_without_raw_or_request_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    started_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    completed_at = started_at + timedelta(milliseconds=200)
    run_id = uuid4()
    scope_id = uuid4()
    attempt_id = uuid4()
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=run_id,
        scope_id=scope_id,
        provider="fake_provider",
        platform="xhs",
        operation="keyword_search",
        request_params={"keyword": "敏感业务输入不得进入日志"},
    )
    moments = iter([started_at, completed_at])
    dispatch = ProviderClient(
        transport=FakeProviderTransport(
            [ProviderTransportResponse(status_code=200, body={"secret_text": "do-not-log"})]
        ),
        clock=lambda: next(moments),
    ).dispatch(
        request=request,
        attempt_id=attempt_id,
        attempt_no=1,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )
    root = Path(".runtime") / "raw-log-tests" / uuid4().hex
    root.mkdir(parents=True)
    store = LocalArtifactStore(root)
    service = RawArtifactService(
        artifacts=ArtifactService(metadata=_Metadata(), store=store),
        store=store,
    )

    with caplog.at_level(
        logging.INFO, logger="aima_ugc.modules.collection.providers.raw_artifact"
    ):
        captured = service.capture(request=request, dispatch=dispatch)

    records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "raw.artifact.stored"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.artifact_id == str(captured.artifact.id)
    assert record.provider_request_id == str(request.request_id)
    assert record.provider_attempt_id == str(attempt_id)
    assert record.run_id == str(run_id)
    assert record.scope_id == str(scope_id)
    assert record.platform == "xhs"
    assert record.operation == "keyword_search"
    assert record.status == "stored"
    assert record.byte_size == captured.artifact.byte_size
    assert "request_params" not in record.__dict__
    assert "response" not in record.__dict__
    assert "body" not in record.__dict__
