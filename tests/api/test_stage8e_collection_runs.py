from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.bootstrap.api import create_app
from fastapi.testclient import TestClient

RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = UUID("22222222-2222-4222-8222-222222222222")
CONFIG_ID = UUID("33333333-3333-4333-8333-333333333333")


class _FakeCollectionService:
    def get_capabilities(self):  # type: ignore[no-untyped-def]
        return {
            "provider_configs": [
                {
                    "id": str(CONFIG_ID),
                    "provider": "tikhub",
                    "display_name": "TikHub 主配置",
                }
            ],
            "capabilities": [],
        }

    def create_run(self, request, *, request_id):  # type: ignore[no-untyped-def]
        assert request.mode == "discovery"
        assert request.keywords == ("爱玛", "爱玛 Q7")
        assert request_id
        return {
            "run_id": str(RUN_ID),
            "job_id": str(JOB_ID),
            "mode": "discovery",
            "import_batch_id": None,
            "status": "queued",
        }

    def get_run(self, run_id):  # type: ignore[no-untyped-def]
        assert run_id == RUN_ID
        return {
            "run_id": str(RUN_ID),
            "job_id": str(JOB_ID),
            "mode": "discovery",
            "import_batch_id": None,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "attempt": 0,
            "max_attempts": 2,
            "platforms": ["xhs"],
            "keywords": ["爱玛", "爱玛 Q7"],
            "stats": {
                "requested_count": 0,
                "succeeded_count": 0,
                "failed_count": 0,
                "content_count": 0,
                "comment_count": 0,
                "filtered_count": 0,
            },
            "scopes": [],
            "error_summary": None,
            "error_code": None,
            "created_at": datetime(2026, 8, 21, 0, 0, tzinfo=UTC).isoformat(),
            "started_at": None,
            "finished_at": None,
        }

    def list_runtime_runs(self, query):  # type: ignore[no-untyped-def]
        assert query.limit == 20
        return {"items": [], "next_cursor": None, "has_more": False}

    def get_runtime_summary(self):  # type: ignore[no-untyped-def]
        return {
            "processing_count": 1,
            "completed_today_count": 2,
            "contents_ingested_today": 3,
            "as_of": datetime(2026, 8, 21, 0, 0, tzinfo=UTC).isoformat(),
        }


def test_create_discovery_collection_run_returns_202() -> None:
    client = TestClient(create_app(collection_service=_FakeCollectionService()))

    response = client.post(
        "/api/v1/collection-runs",
        headers={"x-request-id": "req-stage8e"},
        json={
            "mode": "discovery",
            "keywords": [" 爱玛 ", "爱玛 Q7"],
            "platforms": [{"platform": "xhs", "provider_config_id": str(CONFIG_ID)}],
            "include_comments": True,
            "include_sub_comments": False,
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "run_id": str(RUN_ID),
        "job_id": str(JOB_ID),
        "mode": "discovery",
        "import_batch_id": None,
        "status": "queued",
    }


def test_create_collection_run_rejects_cross_mode_fields_with_request_id() -> None:
    client = TestClient(create_app(collection_service=_FakeCollectionService()))

    response = client.post(
        "/api/v1/collection-runs",
        headers={"x-request-id": "req-invalid-stage8e"},
        json={
            "mode": "batch_supplement",
            "keywords": ["不应出现"],
            "platforms": [{"platform": "xhs", "provider_config_id": str(CONFIG_ID)}],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["request_id"] == response.headers["x-request-id"]
    assert payload["type"].endswith("/request_validation_error")
    assert payload["errors"]


def test_collection_run_detail_and_runtime_summary_are_queryable() -> None:
    client = TestClient(create_app(collection_service=_FakeCollectionService()))

    detail = client.get(f"/api/v1/collection-runs/{RUN_ID}")
    summary = client.get("/api/v1/collection-runtime/summary")
    listing = client.get("/api/v1/collection-runtime/runs")

    assert detail.status_code == 200
    assert detail.json()["run_id"] == str(RUN_ID)
    assert summary.status_code == 200
    assert summary.json()["contents_ingested_today"] == 3
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "next_cursor": None, "has_more": False}
