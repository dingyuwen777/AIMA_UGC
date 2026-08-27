"""Stage 12B Historical Import HTTP 路由与错误表达。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    HistoricalCampaignConflictListResponse,
    HistoricalCampaignCreatedResponse,
    HistoricalCampaignCreateRequest,
    HistoricalCampaignItemListResponse,
    HistoricalCampaignListResponse,
    HistoricalCampaignResponse,
    HistoricalDirectoryListQuery,
    HistoricalDirectoryListResponse,
    LocalDataImportCampaignCreatedResponse,
    LocalDataImportCampaignCreateRequest,
    LocalDataImportFileUploadedResponse,
)
from aima_ugc.modules.ingestion.historical_http import HistoricalCampaignStateConflict
from fastapi.testclient import TestClient

CAMPAIGN_ID = UUID("10000000-0000-0000-0000-000000000001")
JOB_ID = UUID("20000000-0000-0000-0000-000000000001")
ITEM_ID = UUID("40000000-0000-0000-0000-000000000001")
ARTIFACT_ID = UUID("50000000-0000-0000-0000-000000000001")


def _campaign(status: str = "ready") -> HistoricalCampaignResponse:
    return HistoricalCampaignResponse(
        id=CAMPAIGN_ID,
        status=status,
        source_kind="server_path",
        ingestion_policy="historical_fill_only",
        declared_file_count=1,
        root_relative_path="history",
        recursive=True,
        discovered_file_count=1,
        ready_item_count=1,
        total_rows=10,
        progress={
            "preflight_completed_file_count": 1,
            "preflight_percent": 100,
            "migration_completed_row_count": 0,
            "migration_percent": 0,
        },
        created_at=datetime(2026, 8, 26, 8, 0, tzinfo=UTC),
    )


class _FakeHistoricalService:
    def list_directories(
        self, query: HistoricalDirectoryListQuery
    ) -> HistoricalDirectoryListResponse:
        assert query.relative_path == "history"
        return HistoricalDirectoryListResponse(available=True)

    def create_campaign(
        self,
        request: HistoricalCampaignCreateRequest,
        *,
        request_id: str,
    ) -> HistoricalCampaignCreatedResponse:
        assert request.relative_paths == ("history",)
        assert request_id
        return HistoricalCampaignCreatedResponse(
            campaign_id=CAMPAIGN_ID,
            discovery_job_id=JOB_ID,
        )

    def create_local_campaign(
        self,
        request: LocalDataImportCampaignCreateRequest,
        *,
        request_id: str,
    ) -> LocalDataImportCampaignCreatedResponse:
        assert request.files[0].relative_path == "folder/a.xlsx"
        assert request.ingestion_policy == "standard_observation"
        assert request_id
        return LocalDataImportCampaignCreatedResponse(
            campaign_id=CAMPAIGN_ID,
            upload_items=({"item_id": ITEM_ID, "relative_path": "folder/a.xlsx"},),
        )

    def upload_local_file(
        self,
        campaign_id: UUID,
        item_id: UUID,
        *,
        filename: str,
        content_type: str | None,
        source: object,
        request_id: str,
    ) -> LocalDataImportFileUploadedResponse:
        assert campaign_id == CAMPAIGN_ID
        assert item_id == ITEM_ID
        assert filename == "a.xlsx"
        assert content_type
        assert source
        assert request_id
        return LocalDataImportFileUploadedResponse(
            campaign_id=CAMPAIGN_ID,
            item_id=ITEM_ID,
            artifact_id=ARTIFACT_ID,
            sha256="a" * 64,
            byte_size=4,
        )

    def finalize_local_campaign(
        self,
        campaign_id: UUID,
        *,
        request_id: str,
    ) -> HistoricalCampaignResponse:
        assert campaign_id == CAMPAIGN_ID
        assert request_id
        return _campaign("snapshotting")

    def list_campaigns(self) -> HistoricalCampaignListResponse:
        return HistoricalCampaignListResponse(items=(_campaign(),))

    def get_campaign(self, campaign_id: UUID) -> HistoricalCampaignResponse:
        assert campaign_id == CAMPAIGN_ID
        return _campaign()

    def list_items(self, campaign_id: UUID) -> HistoricalCampaignItemListResponse:
        assert campaign_id == CAMPAIGN_ID
        return HistoricalCampaignItemListResponse(items=(), total_count=501, has_more=True)

    def list_conflicts(self, campaign_id: UUID) -> HistoricalCampaignConflictListResponse:
        assert campaign_id == CAMPAIGN_ID
        return HistoricalCampaignConflictListResponse(items=(), total_count=501, has_more=True)

    def start_campaign(
        self, campaign_id: UUID, *, request_id: str | None = None
    ) -> HistoricalCampaignResponse:
        assert campaign_id == CAMPAIGN_ID
        assert request_id
        return _campaign("queued")

    def cancel_campaign(
        self, campaign_id: UUID, *, request_id: str | None = None
    ) -> HistoricalCampaignResponse:
        assert campaign_id == CAMPAIGN_ID
        assert request_id
        return _campaign("cancelling")

    def retry_failed(
        self, campaign_id: UUID, *, request_id: str | None = None
    ) -> HistoricalCampaignResponse:
        assert campaign_id == CAMPAIGN_ID
        assert request_id
        return _campaign("running")


def test_historical_import_routes_form_one_campaign_lifecycle() -> None:
    client = TestClient(create_app(historical_import_service=_FakeHistoricalService()))

    directory = client.get(
        "/api/v1/historical-import/directories",
        params={"relative_path": "history"},
    )
    created = client.post(
        "/api/v1/historical-import-campaigns",
        json={
            "client_idempotency_key": "campaign-1",
            "relative_paths": ["history"],
            "recursive": True,
            "keyword_pack_ids": ["30000000-0000-0000-0000-000000000001"],
        },
    )
    detail = client.get(f"/api/v1/historical-import-campaigns/{CAMPAIGN_ID}")
    items = client.get(f"/api/v1/historical-import-campaigns/{CAMPAIGN_ID}/items")
    conflicts = client.get(f"/api/v1/historical-import-campaigns/{CAMPAIGN_ID}/conflicts")
    started = client.post(f"/api/v1/historical-import-campaigns/{CAMPAIGN_ID}/start")
    cancelled = client.post(f"/api/v1/historical-import-campaigns/{CAMPAIGN_ID}/cancel")

    assert directory.status_code == 200
    assert created.status_code == 202
    assert created.json() == {"campaign_id": str(CAMPAIGN_ID), "discovery_job_id": str(JOB_ID)}
    assert detail.json()["can_start"] is True
    assert detail.json()["progress"]["preflight_percent"] == 100
    assert items.json()["has_more"] is True
    assert items.json()["total_count"] == 501
    assert conflicts.json()["has_more"] is True
    assert conflicts.json()["total_count"] == 501
    assert started.json()["status"] == "queued"
    assert cancelled.json()["status"] == "cancelling"


def test_unified_data_import_routes_stage_local_files_before_common_preflight() -> None:
    client = TestClient(create_app(historical_import_service=_FakeHistoricalService()))

    created = client.post(
        "/api/v1/data-import-campaigns/local",
        json={
            "client_idempotency_key": "local-campaign-1",
            "files": [{"relative_path": "folder/a.xlsx", "byte_size": 4}],
            "keyword_pack_ids": ["30000000-0000-0000-0000-000000000001"],
            "ingestion_policy": "standard_observation",
        },
    )
    uploaded = client.put(
        f"/api/v1/data-import-campaigns/{CAMPAIGN_ID}/items/{ITEM_ID}/content",
        files={
            "file": (
                "a.xlsx",
                b"xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    finalized = client.post(f"/api/v1/data-import-campaigns/{CAMPAIGN_ID}/finalize")
    listed = client.get("/api/v1/data-import-campaigns")

    assert created.status_code == 201
    assert created.json()["upload_items"] == [
        {"item_id": str(ITEM_ID), "relative_path": "folder/a.xlsx"}
    ]
    assert uploaded.status_code == 200
    assert uploaded.json()["artifact_id"] == str(ARTIFACT_ID)
    assert finalized.status_code == 202
    assert finalized.json()["status"] == "snapshotting"
    assert listed.status_code == 200


def test_historical_start_conflict_is_stable_409() -> None:
    class ConflictService(_FakeHistoricalService):
        def start_campaign(
            self, campaign_id: UUID, *, request_id: str | None = None
        ) -> HistoricalCampaignResponse:
            raise HistoricalCampaignStateConflict

    response = TestClient(create_app(historical_import_service=ConflictService())).post(
        f"/api/v1/historical-import-campaigns/{CAMPAIGN_ID}/start"
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "historical_campaign_state_conflict"


def test_historical_paths_reject_escape_before_service() -> None:
    response = TestClient(create_app(historical_import_service=_FakeHistoricalService())).get(
        "/api/v1/historical-import/directories",
        params={"relative_path": "../secret"},
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("/request_validation_error")
    assert response.json()["errors"][0]["code"] == "value_error"
