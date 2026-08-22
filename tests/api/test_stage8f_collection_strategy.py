from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.bootstrap.api import create_app
from aima_ugc.modules.collection.strategy_http import (
    CollectionStrategyConflict,
    CollectionStrategyInvalid,
    CollectionStrategyResourceNotFound,
)
from fastapi.testclient import TestClient

PACK_ID = UUID("11111111-1111-4111-8111-111111111111")
PLAN_ID = UUID("22222222-2222-4222-8222-222222222222")
CONFIG_ID = UUID("33333333-3333-4333-8333-333333333333")
NOW = datetime(2026, 8, 21, 0, 0, tzinfo=UTC).isoformat()


def _pack(enabled: bool = True) -> dict[str, object]:
    return {
        "id": str(PACK_ID),
        "name": "爱玛新品发现",
        "description": "Discovery",
        "enabled": enabled,
        "version": 4,
        "keyword_count": 2,
    }


def _plan(enabled: bool = True) -> dict[str, object]:
    return {
        "id": str(PLAN_ID),
        "name": "爱玛新品周期采集",
        "enabled": enabled,
        "schedule_expr": "0 9 * * *",
        "timezone": "Asia/Shanghai",
        "schedule_version": 1,
        "next_run_at": None,
        "last_scheduled_at": None,
        "detail_policy": "on_change",
        "comment_policy": "adaptive",
        "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],
        "keyword_pack_ids": [str(PACK_ID)],
        "created_at": NOW,
        "updated_at": NOW,
    }


class _FakeStrategyService:
    def list_keyword_packs(self, query):  # type: ignore[no-untyped-def]
        assert query.limit == 20
        return {"items": [_pack()], "total": 1, "offset": 0, "limit": 20}

    def set_keyword_pack_enabled(self, pack_id, request):  # type: ignore[no-untyped-def]
        assert pack_id == PACK_ID
        return _pack(request.enabled)

    def create_plan(self, request):  # type: ignore[no-untyped-def]
        assert request.schedule_expr == "0 9 * * *"
        assert request.keyword_pack_ids == (PACK_ID,)
        return _plan(request.enabled)

    def list_plans(self, query):  # type: ignore[no-untyped-def]
        assert query.limit == 20
        return {
            "items": [_plan()],
            "total": 1,
            "enabled_count": 1,
            "offset": 0,
            "limit": 20,
        }

    def get_plan(self, plan_id):  # type: ignore[no-untyped-def]
        assert plan_id == PLAN_ID
        return _plan()

    def set_plan_enabled(self, plan_id, request):  # type: ignore[no-untyped-def]
        assert plan_id == PLAN_ID
        return _plan(request.enabled)


def test_stage8f_keyword_pack_list_and_status_are_queryable() -> None:
    client = TestClient(create_app(strategy_service=_FakeStrategyService()))

    listing = client.get("/api/v1/keyword-packs")
    disabled = client.put(
        f"/api/v1/keyword-packs/{PACK_ID}/enabled",
        json={"enabled": False},
    )

    assert listing.status_code == 200
    assert listing.json()["items"][0]["keyword_count"] == 2
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_stage8f_creates_lists_reads_and_disables_periodic_plan() -> None:
    client = TestClient(create_app(strategy_service=_FakeStrategyService()))
    body = {
        "name": "爱玛新品周期采集",
        "schedule_expr": "0 9 * * *",
        "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],
        "keyword_pack_ids": [str(PACK_ID)],
        "enabled": True,
    }

    created = client.post("/api/v1/collection-plans", json=body)
    listing = client.get("/api/v1/collection-plans")
    detail = client.get(f"/api/v1/collection-plans/{PLAN_ID}")
    disabled = client.put(
        f"/api/v1/collection-plans/{PLAN_ID}/enabled",
        json={"enabled": False},
    )

    assert created.status_code == 201
    assert listing.status_code == detail.status_code == disabled.status_code == 200
    assert created.json()["schedule_expr"] == "0 9 * * *"
    assert listing.json()["enabled_count"] == 1
    assert disabled.json()["enabled"] is False


def test_stage8f_rejects_single_run_or_plan_level_relevance_fields() -> None:
    client = TestClient(create_app(strategy_service=_FakeStrategyService()))
    base = {
        "name": "非法计划",
        "schedule_expr": "0 9 * * *",
        "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],
        "keyword_pack_ids": [str(PACK_ID)],
    }

    single = client.post(
        "/api/v1/collection-plans",
        json={**base, "schedule_mode": "once"},
    )
    override = client.post(
        "/api/v1/collection-plans",
        json={**base, "relevance_keyword_pack_id": str(PACK_ID)},
    )

    assert single.status_code == override.status_code == 422
    assert single.json()["request_id"] == single.headers["x-request-id"]


def test_stage8f_conflict_does_not_leak_internal_details() -> None:
    class ConflictService(_FakeStrategyService):
        def create_plan(self, request):  # type: ignore[no-untyped-def]
            del request
            raise CollectionStrategyConflict("postgresql://secret@host/internal")

    response = TestClient(
        create_app(strategy_service=ConflictService()),
        raise_server_exceptions=False,
    ).post(
        "/api/v1/collection-plans",
        json={
            "name": "冲突计划",
            "schedule_expr": "0 9 * * *",
            "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],
            "keyword_pack_ids": [str(PACK_ID)],
        },
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "collection_strategy_conflict"
    assert "secret" not in response.text


def test_stage8f_not_found_and_domain_invalid_keep_request_id_contract() -> None:
    class ErrorService(_FakeStrategyService):
        def get_plan(self, plan_id):  # type: ignore[no-untyped-def]
            del plan_id
            raise CollectionStrategyResourceNotFound

        def create_plan(self, request):  # type: ignore[no-untyped-def]
            del request
            raise CollectionStrategyInvalid("internal cron parser detail")

    client = TestClient(create_app(strategy_service=ErrorService()))
    missing = client.get(f"/api/v1/collection-plans/{PLAN_ID}")
    invalid = client.post(
        "/api/v1/collection-plans",
        json={
            "name": "非法 Cron",
            "schedule_expr": "not-a-cron",
            "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],
            "keyword_pack_ids": [str(PACK_ID)],
        },
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422
    for response in (missing, invalid):
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert "internal" not in response.text
