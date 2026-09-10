from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from aima_ugc.adapters.feishu import (
    FeishuBitableClient,
    FeishuConfig,
    FeishuConfigError,
    FeishuSyncError,
)
from aima_ugc.adapters.providers.imports import LabeledContent
from aima_ugc.entrypoints.representative_selection_main import _selected_row
from aima_ugc.modules.analysis.representative_selection import (
    RepresentativeCandidate,
    RepresentativeDecisionModel,
    SelectedRepresentative,
)
from aima_ugc.platform.config import PlatformSettings


def _fields() -> list[dict[str, Any]]:
    return [
        {
            "field_id": "platform",
            "field_name": "平台",
            "type": 3,
            "property": {"options": [{"name": "抖音"}, {"name": "小红书"}]},
        },
        {
            "field_id": "sentiment",
            "field_name": "情感",
            "type": 3,
            "property": {"options": [{"name": "正面"}, {"name": "负面"}]},
        },
        {"field_id": "content-id", "field_name": "内容ID", "type": 1},
        {"field_id": "title", "field_name": "标题", "type": 1},
        {"field_id": "body", "field_name": "正文", "type": 1},
        {"field_id": "author", "field_name": "作者", "type": 1},
        {"field_id": "url", "field_name": "内容链接", "type": 15},
        {"field_id": "published", "field_name": "发布时间", "type": 5},
        {"field_id": "theme", "field_name": "代表性主题", "type": 1},
        {"field_id": "reason", "field_name": "入选理由", "type": 1},
        {"field_id": "score", "field_name": "代表性评分", "type": 2},
    ]


def test_missing_feishu_settings_have_stable_safe_error() -> None:
    settings = PlatformSettings(data_dir="data", log_dir="logs", secret_dir="secrets")

    with pytest.raises(FeishuConfigError, match="AIMA_FEISHU_WIKI_TOKEN") as error:
        FeishuConfig.from_settings(settings)

    assert error.value.missing == (
        "AIMA_FEISHU_APP_ID",
        "AIMA_FEISHU_TABLE_ID",
        "AIMA_FEISHU_APP_TOKEN 或 AIMA_FEISHU_WIKI_TOKEN",
    )


def test_direct_app_token_is_accepted_without_wiki_request() -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        raise AssertionError("直接使用 app_token 时不应请求 Wiki 解析接口")

    config = FeishuConfig(
        app_id="app",
        app_token="base-token",
        table_id="table",
        max_retries=0,
    )
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(config=config, app_secret="secret", client=client) as feishu:
        assert feishu.resolve_app_token() == "base-token"

    assert calls == []


def test_create_table_from_current_clones_schema_without_touching_old_records() -> None:
    calls: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append((request.method, path))
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "token", "expire": 7200},
            )
        if path.endswith("/fields"):
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": _fields(), "has_more": False}},
            )
        if path.endswith("/tables") and request.method == "POST":
            payload = json.loads(request.read().decode("utf-8"))
            table = payload["table"]
            assert table["name"] == "20260909T120000.000000+0800"
            assert table["default_view_name"] == "表格视图"
            assert {field["field_name"] for field in table["fields"]} == {
                field["field_name"] for field in _fields()
            }
            source_sentiment = next(
                field for field in table["fields"] if field["field_name"] == "情感"
            )
            assert source_sentiment["property"] == {
                "options": [{"name": "正面"}, {"name": "负面"}]
            }
            return httpx.Response(
                200,
                json={"code": 0, "data": {"table_id": "tbl-new"}},
            )
        raise AssertionError(f"unexpected request: {request.method} {path}")

    config = FeishuConfig(app_id="app", app_token="base", table_id="tbl-template", max_retries=0)
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(config=config, app_secret="secret", client=client) as feishu:
        table = feishu.create_table_from_current(name="20260909T120000.000000+0800")

    assert table.table_id == "tbl-new"
    assert table.name == "20260909T120000.000000+0800"
    assert table.skipped_fields == ()
    assert not any(path.endswith("/records") for _, path in calls)


def test_target_table_schema_uses_content_link_as_idempotency_key() -> None:
    fields = [
        {"field_id": "main", "field_name": "声音内容/连接", "type": 1},
        {"field_id": "example", "field_name": "典型评论示例", "type": 1},
        {
            "field_id": "source",
            "field_name": "来源",
            "type": 3,
            "property": {"options": [{"name": "抖音"}, {"name": "小红书"}]},
        },
        {"field_id": "published", "field_name": "发布时间", "type": 5},
        {
            "field_id": "emotion",
            "field_name": "用户情绪",
            "type": 3,
            "property": {"options": [{"name": "正面"}]},
        },
    ]
    candidate = RepresentativeCandidate(
        item_no=1,
        content=LabeledContent(
            row_number=2,
            platform="抖音",
            content_id="id-1",
            title="用户体验",
            text="评论正文",
            author="用户",
            published_at="2026-09-01 10:00:00",
            content_url="https://example.test/id-1",
            voice_type="真实用户发声",
            sentiment_label="正面",
        ),
    )
    selected = SelectedRepresentative(
        candidate=candidate,
        decision=RepresentativeDecisionModel(
            item_no=1,
            eligible=True,
            sentiment="正面",
            theme="续航表现",
            reason="具体使用事实",
            score=5,
            exclusion_reason=None,
        ),
    )
    row = _selected_row(selected)
    config = FeishuConfig(app_id="app", app_token="base", table_id="table", max_retries=0)
    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "token", "expire": 7200},
            )
        if path.endswith("/fields"):
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": fields, "has_more": False}},
            )
        if path.endswith("/records") and request.method == "GET":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": [], "has_more": False}},
            )
        raise AssertionError(f"unexpected request: {request.method} {path}")

    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(
        config=config,
        app_secret="secret",
        client=client,
        upsert_key_fields=("声音内容/连接",),
    ) as feishu:
        prepared = feishu.preflight([row])

    assert len(prepared.creates) == 1
    assert prepared.creates[0]["声音内容/连接"].endswith("https://example.test/id-1")
    assert prepared.creates[0]["来源"] == "抖音"
    assert prepared.creates[0]["用户情绪"] == "正面"


def test_preflight_update_create_and_readback_are_idempotent() -> None:
    records: dict[str, dict[str, Any]] = {
        "rec-existing": {
            "record_id": "rec-existing",
            "fields": {"平台": "抖音", "情感": "正面", "内容ID": "id-1", "标题": "旧标题"},
        }
    }
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = request.read().decode("utf-8") if request.content else ""
        calls.append((request.method, path, None))
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200, json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200}
            )
        if path.endswith("/wiki/v2/spaces/get_node"):
            return httpx.Response(
                200, json={"code": 0, "data": {"node": {"obj_token": "app-token"}}}
            )
        if path.endswith("/fields"):
            return httpx.Response(
                200, json={"code": 0, "data": {"items": _fields(), "has_more": False}}
            )
        if path.endswith("/records") and request.method == "GET":
            return httpx.Response(
                200, json={"code": 0, "data": {"items": list(records.values()), "has_more": False}}
            )
        if path.endswith("/batch_update"):
            request_payload = httpx.Response(200, content=body.encode("utf-8")).json()
            for item in request_payload["records"]:
                records[item["record_id"]]["fields"].update(item["fields"])
            return httpx.Response(200, json={"code": 0, "data": {}})
        if path.endswith("/batch_create"):
            request_payload = httpx.Response(200, content=body.encode("utf-8")).json()
            for index, item in enumerate(request_payload["records"], start=1):
                record_id = f"rec-created-{index}"
                records[record_id] = {"record_id": record_id, "fields": item["fields"]}
            return httpx.Response(200, json={"code": 0, "data": {}})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    config = FeishuConfig(
        app_id="cli-test",
        wiki_token="wiki-token",
        table_id="tbl-test",
        max_retries=0,
    )
    rows = [
        {
            "平台": "抖音",
            "情感": "正面",
            "内容ID": "id-1",
            "标题": "新标题",
            "正文": "正文",
            "作者": "用户",
            "内容链接": "https://example.test/id-1",
            "发布时间": "2026-09-01 10:00:00",
            "代表性主题": "续航表现",
            "入选理由": "具体使用体验",
            "代表性评分": 5,
        },
        {
            "平台": "小红书",
            "情感": "负面",
            "内容ID": "id-2",
            "标题": "标题2",
            "正文": "正文2",
            "作者": "用户2",
            "内容链接": "https://example.test/id-2",
            "发布时间": "2026-09-01 11:00:00",
            "代表性主题": "售后问题",
            "入选理由": "具体投诉事实",
            "代表性评分": 4,
        },
    ]
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(config=config, app_secret="app-secret", client=client) as feishu:
        prepared, summary = feishu.sync(rows)

    assert len(prepared.updates) == 1
    assert len(prepared.creates) == 1
    assert summary.created_count == 1
    assert summary.updated_count == 1
    assert summary.verified_count == 2
    assert not summary.verification_errors
    assert records["rec-existing"]["fields"]["标题"] == "新标题"
    assert any(path.endswith("/batch_update") for _, path, _ in calls)
    assert any(path.endswith("/batch_create") for _, path, _ in calls)


def test_missing_required_feishu_field_stops_before_write() -> None:
    write_calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal write_calls
        path = request.url.path
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200, json={"code": 0, "tenant_access_token": "token", "expire": 7200}
            )
        if path.endswith("/wiki/v2/spaces/get_node"):
            return httpx.Response(200, json={"code": 0, "data": {"node": {"obj_token": "app"}}})
        if path.endswith("/fields"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "items": [{"field_id": "id", "field_name": "平台", "type": 1}],
                        "has_more": False,
                    },
                },
            )
        if "/records" in path:
            write_calls += 1
        return httpx.Response(200, json={"code": 0, "data": {"items": [], "has_more": False}})

    config = FeishuConfig(app_id="app", wiki_token="wiki", table_id="table", max_retries=0)
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(config=config, app_secret="secret", client=client) as feishu:
        with pytest.raises(FeishuSyncError, match="Upsert 必需字段"):
            feishu.preflight([{"平台": "抖音", "情感": "正面", "内容ID": "id"}])

    assert write_calls == 0


def test_retryable_feishu_response_is_retried_with_bounded_delay() -> None:
    wiki_attempts = 0
    delays: list[float] = []

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal wiki_attempts
        path = request.url.path
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200, json={"code": 0, "tenant_access_token": "token", "expire": 7200}
            )
        if path.endswith("/wiki/v2/spaces/get_node"):
            wiki_attempts += 1
            if wiki_attempts == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"code": 0, "data": {"node": {"obj_token": "app"}}})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    config = FeishuConfig(app_id="app", wiki_token="wiki", table_id="table", max_retries=1)
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(
        config=config,
        app_secret="secret",
        client=client,
        sleep=delays.append,
    ) as feishu:
        assert feishu.resolve_app_token() == "app"

    assert wiki_attempts == 2
    assert delays == [0.0]
