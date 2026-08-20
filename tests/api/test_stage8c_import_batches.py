from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    ImportBatchListQuery,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportBatchSummaryResponse,
    ImportStatsResponse,
    JobStatusResponse,
)
from aima_ugc.modules.ingestion.http import ImportCursorUnavailable, InvalidImportCursor
from fastapi.testclient import TestClient

_BATCH_ID = UUID("12345678-1234-5678-1234-567812345678")
_JOB_ID = UUID("22345678-1234-5678-1234-567812345678")
_ARTIFACT_ID = UUID("32345678-1234-5678-1234-567812345678")
_CREATED_AT = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)


class _FakeStage8CService:
    def __init__(self) -> None:
        self.query: ImportBatchListQuery | None = None
        self.invalid_cursor = False
        self.cursor_unavailable = False

    def list_import_batches(self, query: ImportBatchListQuery) -> ImportBatchListResponse:
        self.query = query
        if self.invalid_cursor:
            raise InvalidImportCursor
        if self.cursor_unavailable:
            raise ImportCursorUnavailable
        job = JobStatusResponse(
            id=_JOB_ID,
            job_type="ingestion.import-excel.v1",
            status="running",
            attempt=2,
            max_attempts=10,
            progress=67,
            created_at=_CREATED_AT,
            started_at=_CREATED_AT,
        )
        item = ImportBatchResponse(
            id=_BATCH_ID,
            input_artifact_id=_ARTIFACT_ID,
            source_filename="爱玛8月舆情.xlsx",
            status="running",
            stage="filtering",
            stats=ImportStatsResponse(rows_seen=1284, rows_matched=1152, rows_filtered_out=132),
            created_at=_CREATED_AT,
            started_at=_CREATED_AT,
            job=job,
        )
        return ImportBatchListResponse(items=(item,), next_cursor="signed-next", has_more=True)

    def get_import_batch_summary(self) -> ImportBatchSummaryResponse:
        return ImportBatchSummaryResponse(
            processing_count=12,
            completed_today_count=86,
            rows_ingested_today=3284,
            as_of=_CREATED_AT,
        )


def test_list_and_summary_return_real_stage8c_contracts() -> None:
    service = _FakeStage8CService()
    client = TestClient(create_app(import_service=service))  # type: ignore[arg-type]

    listed = client.get(
        "/api/v1/import-batches",
        params={
            "identifier": str(_BATCH_ID),
            "status": "running",
            "stage": "filtering",
            "created_from": "2026-08-19T00:00:00Z",
            "created_to": "2026-08-21T00:00:00Z",
            "limit": 20,
        },
    )
    summary = client.get("/api/v1/import-batches/summary")

    assert listed.status_code == summary.status_code == 200
    assert listed.json()["items"][0]["source_filename"] == "爱玛8月舆情.xlsx"
    assert listed.json()["items"][0]["job"]["progress"] == 67
    assert listed.json()["next_cursor"] == "signed-next"
    assert service.query is not None
    assert service.query.identifier == _BATCH_ID
    assert summary.json()["rows_ingested_today"] == 3284


def test_invalid_cursor_uses_stable_400_error_with_request_id() -> None:
    service = _FakeStage8CService()
    service.invalid_cursor = True
    response = TestClient(
        create_app(import_service=service),  # type: ignore[arg-type]
        raise_server_exceptions=False,
    ).get("/api/v1/import-batches", params={"cursor": "tampered"})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_import_cursor"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_unavailable_cursor_signing_uses_safe_503_error() -> None:
    service = _FakeStage8CService()
    service.cursor_unavailable = True
    response = TestClient(
        create_app(import_service=service),  # type: ignore[arg-type]
        raise_server_exceptions=False,
    ).get("/api/v1/import-batches")

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "import_cursor_unavailable"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "signing" not in response.text.casefold()
