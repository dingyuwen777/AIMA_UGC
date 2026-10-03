"""从公开计划 API 验证网站采集生命周期与运行冻结的品牌范围。"""

from datetime import timedelta
from uuid import UUID

import pytest
from aima_ugc.bootstrap import brand_vehicle_http, resource_lifecycle_http
from aima_ugc.bootstrap.scheduler import run_scheduler_once
from aima_ugc.entrypoints.api_main import create_app
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.ingestion.wisersone_tables import wisersone_downloads_table
from aima_ugc.platform.time import beijing_now
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.integration.ingestion.test_wisersone_workflow import workflow as workflow


@pytest.fixture
def lifecycle_workflow(workflow, monkeypatch):  # type: ignore[no-untyped-def]
    """复用外部网站 Fake，但从安装完整产品路由的正式 API 入口调用。"""
    runtime, website, _, brand, new_worker, tick = workflow
    monkeypatch.setattr(brand_vehicle_http, "create_platform_runtime", lambda *_: runtime)
    monkeypatch.setattr(resource_lifecycle_http, "create_platform_runtime", lambda *_: runtime)
    client = TestClient(create_app(identity_resolver=DevelopmentIdentityResolver()))
    try:
        yield runtime, website, client, brand, new_worker, tick
    finally:
        client.close()


def _new_plan(client, brand, *, name="网站计划", enabled=False):  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/collection-plans",
        json={
            "plan_type": "wisersone",
            "name": name,
            "schedule_expr": "* * * * *",
            "brand_ids": [brand],
            "enabled": enabled,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_wisersone_edit_copy_enable_archive_and_restore_use_shared_plan_api(
    lifecycle_workflow,
) -> None:  # type: ignore[no-untyped-def]
    _, _, client, brand, _, _ = lifecycle_workflow
    original = _new_plan(client, brand)
    plan_url = f"/api/v1/collection-plans/{original['id']}"
    updated_request = {
        "expected_version": original["schedule_version"],
        "plan_type": "wisersone",
        "name": "每三小时的网站计划",
        "schedule_expr": "0 */3 * * *",
        "brand_ids": [brand],
        "enabled": False,
    }
    response = client.put(plan_url, json=updated_request)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["schedule_version"] == original["schedule_version"] + 1
    assert updated["plan_type"] == "wisersone"
    assert updated["detail_policy"] is None and updated["comment_policy"] is None
    assert updated["platforms"] == [] and updated["keyword_pack_ids"] == []
    assert updated["brand_ids"] == [brand]
    assert updated["schedule_expr"] == "0 */3 * * *"
    # 旧版本写入必须拒绝，不能覆盖已保存的新频率。
    stale = client.put(plan_url, json=updated_request | {"name": "过期草稿"})
    assert stale.status_code == 409, stale.text
    assert "request_id" in stale.json()
    assert client.get(plan_url).json()["name"] == updated["name"]

    copied_response = client.post(f"{plan_url}/copy", json={"name": "网站计划副本"})
    assert copied_response.status_code == 201, copied_response.text
    copied = copied_response.json()
    assert copied["id"] != original["id"] and copied["enabled"] is False
    assert copied["schedule_version"] == 1 and copied["next_run_at"] is None
    for key in (
        "plan_type",
        "schedule_expr",
        "platforms",
        "keyword_pack_ids",
        "brand_ids",
        "comment_policy",
    ):
        assert copied[key] == updated[key]

    enabled = client.put(f"{plan_url}/enabled", json={"enabled": True})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled"] is True
    assert enabled.json()["plan_type"] == "wisersone"
    disabled = client.put(f"{plan_url}/enabled", json={"enabled": False})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False
    archived = client.post(f"{plan_url}/archive")
    assert archived.status_code == 200, archived.text
    archived_items = client.get("/api/v1/resource-lifecycle/collection-plans/archived").json()[
        "items"
    ]
    assert original["id"] in {item["id"] for item in archived_items}
    listed_ids = {item["id"] for item in client.get("/api/v1/collection-plans").json()["items"]}
    assert original["id"] not in listed_ids
    restored = client.post(f"{plan_url}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["plan_type"] == "wisersone" and restored.json()["enabled"] is False
    assert restored.json()["brand_ids"] == [brand]
    assert restored.json()["schedule_expr"] == updated["schedule_expr"]


def test_scheduled_download_keeps_frozen_brand_scope_when_plan_and_catalog_change(
    lifecycle_workflow,
) -> None:  # type: ignore[no-untyped-def]
    runtime, website, client, brand, new_worker, tick = lifecycle_workflow
    plan = _new_plan(client, brand, enabled=True)
    start = beijing_now().replace(second=0, microsecond=0)
    assert run_scheduler_once(runtime, now=start).initialized == 1
    assert run_scheduler_once(runtime, now=start + timedelta(minutes=1)).enqueued == 1
    downloads = client.get("/api/v1/wisersone-downloads").json()["items"]
    assert len(downloads) == 1 and downloads[0]["occurrence_id"]
    run_id = UUID(downloads[0]["id"])
    with runtime.database.engine.connect() as connection:
        frozen = connection.scalar(
            select(wisersone_downloads_table.c.filter_snapshot).where(
                wisersone_downloads_table.c.id == run_id
            )
        )
    assert frozen["catalog"]["selected_brand_ids"] == [brand]
    assert frozen["catalog"]["brands"][0]["display_name"] == "爱玛"

    new_brand_response = client.post(
        "/api/v1/vehicle-brands",
        json={"display_name": "另一品牌", "role": "competitor", "aliases": ["另一品牌"]},
    )
    assert new_brand_response.status_code == 201, new_brand_response.text
    replacement_brand = new_brand_response.json()["id"]
    changed = client.put(
        f"/api/v1/collection-plans/{plan['id']}",
        json={
            "expected_version": plan["schedule_version"],
            "plan_type": "wisersone",
            "name": "改为另一品牌",
            "schedule_expr": "0 */3 * * *",
            "brand_ids": [replacement_brand],
            "enabled": True,
        },
    )
    assert changed.status_code == 200, changed.text
    # 当前目录也移除原匹配词；已创建运行仍应匹配它冻结时保存的“爱玛”。
    catalog_change = client.put(
        f"/api/v1/vehicle-brands/{brand}",
        json={"display_name": "旧品牌更名", "aliases": ["旧品牌更名"]},
    )
    assert catalog_change.status_code == 200, catalog_change.text
    worker = new_worker()
    result = {}
    for _ in range(25):
        tick(worker)
        result = client.get(f"/api/v1/wisersone-downloads/{run_id}").json()
        if result["status"] in {"succeeded", "failed", "partial_failed"}:
            break
    assert result["status"] == "succeeded", result
    assert website.submissions == 1
    with runtime.database.engine.connect() as connection:
        current_frozen = connection.scalar(
            select(wisersone_downloads_table.c.filter_snapshot).where(
                wisersone_downloads_table.c.id == run_id
            )
        )
        campaign_frozen = connection.scalar(
            select(historical_import_campaigns_table.c.keyword_pack_snapshot).where(
                historical_import_campaigns_table.c.id == UUID(result["campaign_id"])
            )
        )
        assert current_frozen == frozen and campaign_frozen == frozen
        assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
