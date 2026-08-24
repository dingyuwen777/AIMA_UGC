from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

import aima_ugc.bootstrap.api as api_module
import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    GlobalRelevanceConfigRequest,
    GlobalRelevanceConfigResponse,
    ImportBatchCreatedResponse,
    ImportBatchResponse,
    ImportStatsResponse,
    JobStatusResponse,
    KeywordPackCreateRequest,
    KeywordPackKeywordCreateRequest,
    KeywordPackResponse,
    KeywordResponse,
)
from aima_ugc.modules.ingestion.http import (
    ImportConflict,
    ImportResourceNotFound,
    InvalidImportFile,
    RelevanceConfigurationError,
)
from aima_ugc.modules.ingestion.xlsx_security import MAX_MULTIPART_BODY_BYTES
from fastapi.testclient import TestClient


class _FakeImportService:
    def __init__(self) -> None:
        self.batch_id = uuid4()
        self.job_id = uuid4()
        self.artifact_id = uuid4()
        self.pack_id = uuid4()
        self.created_file = b""
        self.created_keyword_pack_ids: tuple[UUID, ...] = ()
        self.invalid = False

    def create_import(
        self,
        *,
        filename: str,
        content_type: str | None,
        source: BytesIO,
        keyword_pack_ids: tuple[UUID, ...],
        request_id: str,
    ) -> ImportBatchCreatedResponse:
        del filename, content_type, request_id
        self.created_keyword_pack_ids = keyword_pack_ids
        if self.invalid:
            raise InvalidImportFile("坏文件")
        self.created_file = source.read()
        return ImportBatchCreatedResponse(batch_id=self.batch_id, job_id=self.job_id)

    def get_import_batch(self, batch_id: UUID) -> ImportBatchResponse:
        assert batch_id == self.batch_id
        return ImportBatchResponse(
            id=self.batch_id,
            input_artifact_id=self.artifact_id,
            status="queued",
            stage="queued",
            stats=ImportStatsResponse(),
            created_at=datetime(2026, 8, 20, tzinfo=UTC),
            job=self.get_job(self.job_id),
        )

    def get_job(self, job_id: UUID) -> JobStatusResponse:
        assert job_id == self.job_id
        return JobStatusResponse(
            id=self.job_id,
            job_type="ingestion.import-excel.v1",
            status="queued",
            attempt=0,
            max_attempts=10,
            progress=0,
            created_at=datetime(2026, 8, 20, tzinfo=UTC),
        )

    def create_keyword_pack(self, request: KeywordPackCreateRequest) -> KeywordPackResponse:
        return self._pack(request.name, request.description)

    def add_keyword(
        self, pack_id: UUID, request: KeywordPackKeywordCreateRequest
    ) -> KeywordPackResponse:
        assert pack_id == self.pack_id
        return self._pack(
            "全局相关性",
            "",
            keywords=(
                KeywordResponse(
                    id=uuid4(),
                    text=request.text,
                    enabled=request.enabled,
                    priority=request.priority,
                    note=request.note,
                ),
            ),
        )

    def get_keyword_pack(self, pack_id: UUID) -> KeywordPackResponse:
        assert pack_id == self.pack_id
        return self._pack("全局相关性", "")

    def set_global_relevance(
        self, request: GlobalRelevanceConfigRequest
    ) -> GlobalRelevanceConfigResponse:
        assert request.keyword_pack_id == self.pack_id
        return self.get_global_relevance()

    def get_global_relevance(self) -> GlobalRelevanceConfigResponse:
        return GlobalRelevanceConfigResponse(
            keyword_pack_id=self.pack_id,
            keyword_pack_version=1,
            version=1,
            effective_keywords=("爱玛",),
            updated_at=datetime(2026, 8, 20, tzinfo=UTC),
        )

    def _pack(
        self,
        name: str,
        description: str,
        *,
        keywords: tuple[KeywordResponse, ...] = (),
    ) -> KeywordPackResponse:
        return KeywordPackResponse(
            id=self.pack_id,
            name=name,
            description=description,
            enabled=True,
            version=1,
            keywords=keywords,
        )


def test_create_import_is_multipart_202_and_status_queries_are_stable() -> None:
    service = _FakeImportService()
    client = TestClient(create_app(import_service=service))

    created = client.post(
        "/api/v1/import-batches",
        files=[
            ("file", ("input.xlsx", b"xlsx", "application/octet-stream")),
            ("keyword_pack_ids", (None, str(service.pack_id))),
        ],
    )
    batch = client.get(f"/api/v1/import-batches/{service.batch_id}")
    job = client.get(f"/api/v1/jobs/{service.job_id}")

    assert created.status_code == 202
    assert created.json() == {
        "batch_id": str(service.batch_id),
        "job_id": str(service.job_id),
        "status": "queued",
    }
    assert service.created_file == b"xlsx"
    assert service.created_keyword_pack_ids == (service.pack_id,)
    assert batch.status_code == job.status_code == 200
    assert batch.json()["job"]["id"] == str(service.job_id)
    assert job.json()["max_attempts"] == 10


def test_invalid_import_and_validation_errors_use_request_id_error_contract() -> None:
    service = _FakeImportService()
    service.invalid = True
    client = TestClient(create_app(import_service=service), raise_server_exceptions=False)

    invalid = client.post(
        "/api/v1/import-batches",
        files=[
            ("file", ("bad.xlsx", b"bad", "application/octet-stream")),
            ("keyword_pack_ids", (None, str(service.pack_id))),
        ],
    )
    missing = client.post("/api/v1/import-batches")

    assert invalid.status_code == 422
    assert invalid.json()["request_id"] == invalid.headers["x-request-id"]
    assert invalid.json()["errors"][0]["code"] == "invalid_xlsx"
    assert missing.status_code == 422
    assert missing.json()["request_id"] == missing.headers["x-request-id"]
    assert missing.json()["errors"][0]["field"] == "body.file"


def test_declared_multipart_body_above_550_mib_is_rejected_before_service() -> None:
    client = TestClient(create_app(import_service=_FakeImportService()))

    response = client.post(
        "/api/v1/import-batches",
        headers={
            "content-length": str(MAX_MULTIPART_BODY_BYTES + 1),
            "content-type": "multipart/form-data; boundary=stage8b",
        },
        content=b"",
    )

    assert response.status_code == 413
    assert response.json()["errors"][0]["code"] == "multipart_body_too_large"


def test_streamed_multipart_body_without_content_length_uses_actual_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_module, "MAX_MULTIPART_BODY_BYTES", 100)
    client = TestClient(create_app(import_service=_FakeImportService()))

    response = client.post(
        "/api/v1/import-batches",
        headers={"content-type": "multipart/form-data; boundary=stage8b"},
        content=iter((b"x" * 120,)),
    )

    assert response.status_code == 413
    assert response.json()["errors"][0]["code"] == "multipart_body_too_large"


def test_keyword_and_global_relevance_contracts_are_http_visible() -> None:
    service = _FakeImportService()
    client = TestClient(create_app(import_service=service))

    pack = client.post("/api/v1/keyword-packs", json={"name": "全局相关性"})
    keyword = client.post(
        f"/api/v1/keyword-packs/{service.pack_id}/keywords",
        json={"text": "爱玛", "priority": 10},
    )
    configured = client.put(
        "/api/v1/relevance-config",
        json={"keyword_pack_id": str(service.pack_id)},
    )
    loaded = client.get("/api/v1/relevance-config")

    assert pack.status_code == keyword.status_code == 201
    assert keyword.json()["keywords"][0]["text"] == "爱玛"
    assert configured.status_code == loaded.status_code == 200
    assert loaded.json()["effective_keywords"] == ["爱玛"]


def test_keyword_contract_rejects_whitespace_only_values() -> None:
    client = TestClient(create_app(import_service=_FakeImportService()))

    pack = client.post("/api/v1/keyword-packs", json={"name": "   "})
    keyword = client.post(
        f"/api/v1/keyword-packs/{uuid4()}/keywords",
        json={"text": "\t"},
    )

    assert pack.status_code == keyword.status_code == 422
    assert pack.json()["errors"][0]["field"] == "body.name"
    assert keyword.json()["errors"][0]["field"] == "body.text"


def test_keyword_conflict_uses_stable_error_contract() -> None:
    class ConflictService(_FakeImportService):
        def create_keyword_pack(self, request: KeywordPackCreateRequest) -> KeywordPackResponse:
            del request
            raise ImportConflict

    response = TestClient(create_app(import_service=ConflictService())).post(
        "/api/v1/keyword-packs",
        json={"name": "已存在"},
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "resource_conflict"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_not_found_relevance_and_internal_failures_do_not_leak_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ErrorService(_FakeImportService):
        def get_job(self, job_id: UUID) -> JobStatusResponse:
            del job_id
            raise ImportResourceNotFound

        def get_global_relevance(self) -> GlobalRelevanceConfigResponse:
            raise RelevanceConfigurationError

        def get_keyword_pack(self, pack_id: UUID) -> KeywordPackResponse:
            del pack_id
            raise RuntimeError("postgresql://secret@host/internal")

    caplog.set_level("ERROR", logger="aima_ugc")
    client = TestClient(
        create_app(import_service=ErrorService()),
        raise_server_exceptions=False,
    )
    missing = client.get(f"/api/v1/jobs/{uuid4()}")
    relevance = client.get("/api/v1/relevance-config")
    internal = client.get(f"/api/v1/keyword-packs/{uuid4()}")

    assert missing.status_code == 404
    assert relevance.status_code == 409
    assert internal.status_code == 500
    assert missing.json()["errors"][0]["code"] == "resource_not_found"
    assert relevance.json()["errors"][0]["code"] == "relevance_config_unavailable"
    assert "secret" not in internal.text
    assert internal.json()["request_id"] == internal.headers["x-request-id"]
    matching_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "api.request_failed"
    ]
    assert len(matching_records) == 1
    assert matching_records[0].request_id == internal.json()["request_id"]
    assert "secret" not in caplog.text
