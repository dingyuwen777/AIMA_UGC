from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from typing import Any

import httpx
import pytest
from aima_ugc.adapters.feishu import (
    FeishuBitableClient,
    FeishuConfig,
    FeishuConfigError,
    FeishuFieldMapping,
    FeishuSyncError,
    FeishuSyncSummary,
)
from aima_ugc.adapters.providers.imports import LabeledContent
from aima_ugc.bootstrap.representative_selection_publication import (
    selected_representative_to_row,
)
from aima_ugc.entrypoints.representative_selection_main import _selected_row
from aima_ugc.modules.analysis.representative_selection import (
    RepresentativeCandidate,
    RepresentativeDecisionModel,
    SelectedRepresentative,
)
from aima_ugc.platform.config import PlatformSettings


class _MirrorAPI:
    """Stateful Feishu mock used to verify both mirror directions and deletion rules."""

    fields = [
        {
            "field_id": "primary",
            "field_name": "声音内容/连接",
            "type": 15,
            "is_primary": True,
        },
        {"field_id": "progress", "field_name": "处理进展", "type": 1},
        {"field_id": "labels", "field_name": "一级标签", "type": 4},
        {"field_id": "screenshot", "field_name": "声音截图", "type": 17},
    ]

    def __init__(
        self,
        *,
        external: list[dict[str, Any]],
        embedded: list[dict[str, Any]],
    ) -> None:
        self.records = {"external": external, "embedded": embedded}
        self.mutations: list[tuple[str, str, list[dict[str, Any]] | list[str]]] = []
        self._next_id = 1
        self._next_modified_time = 10_000

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "token", "expire": 7200},
            )
        segments = path.strip("/").split("/")
        app_token = segments[4] if len(segments) > 4 else ""
        if app_token not in self.records:
            raise AssertionError(f"unexpected request: {request.method} {path}")
        if path.endswith("/fields") and request.method == "GET":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": self.fields, "has_more": False}},
            )
        if path.endswith("/records") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"items": self.records[app_token], "has_more": False},
                },
            )

        body = json.loads(request.content)
        if path.endswith("/records/batch_create") and request.method == "POST":
            payload = body["records"]
            self.mutations.append((app_token, "create", payload))
            for item in payload:
                self.records[app_token].append(
                    {
                        "record_id": f"created-{self._next_id}",
                        "fields": dict(item["fields"]),
                        "last_modified_time": self._tick(),
                    }
                )
                self._next_id += 1
            return httpx.Response(200, json={"code": 0, "data": {"records": []}})
        if path.endswith("/records/batch_update") and request.method == "POST":
            payload = body["records"]
            self.mutations.append((app_token, "update", payload))
            by_id = {item["record_id"]: item for item in self.records[app_token]}
            for item in payload:
                record = by_id[item["record_id"]]
                record["fields"].update(item["fields"])
                record["last_modified_time"] = self._tick()
            return httpx.Response(200, json={"code": 0, "data": {"records": []}})
        if path.endswith("/records/batch_delete") and request.method == "POST":
            payload = body["records"]
            self.mutations.append((app_token, "delete", payload))
            deleted = set(payload)
            self.records[app_token][:] = [
                item for item in self.records[app_token] if item["record_id"] not in deleted
            ]
            return httpx.Response(200, json={"code": 0, "data": {"records": []}})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    def _tick(self) -> int:
        self._next_modified_time += 1
        return self._next_modified_time


def _mirror_record(
    record_id: str,
    key: str,
    *,
    progress: str,
    modified_time: int,
    screenshot_token: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "声音内容/连接": {"text": key, "link": f"https://example.test/{key}"},
        "处理进展": progress,
        "一级标签": ["产品体验"],
    }
    if screenshot_token is not None:
        fields["声音截图"] = [{"file_token": screenshot_token, "name": "shot.png"}]
    return {
        "record_id": record_id,
        "fields": fields,
        "last_modified_time": modified_time,
    }


def _mirror_client(api: _MirrorAPI) -> FeishuBitableClient:
    config = FeishuConfig(
        app_id="app",
        app_token="external",
        table_id="tbl-external",
        max_retries=0,
    )
    return FeishuBitableClient(
        config=config,
        app_secret="secret",
        client=httpx.Client(
            base_url="https://open.feishu.cn/",
            transport=httpx.MockTransport(api),
        ),
        upsert_key_fields=("声音内容/连接",),
    )


def test_bidirectional_mirror_uses_newer_record_on_each_side() -> None:
    api = _MirrorAPI(
        external=[
            _mirror_record("external-a", "item-a", progress="外部较新", modified_time=2_000),
            _mirror_record("external-b", "item-b", progress="外部较旧", modified_time=1_000),
        ],
        embedded=[
            _mirror_record("embedded-a", "item-a", progress="内嵌较旧", modified_time=1_000),
            _mirror_record("embedded-b", "item-b", progress="内嵌较新", modified_time=2_000),
        ],
    )

    with _mirror_client(api) as client:
        result = client.mirror_records_bidirectionally(
            external_app_token="external",
            external_table_id="tbl-external",
            embedded_app_token="embedded",
            embedded_table_id="tbl-embedded",
        )

    assert result.external_updated_count == 1
    assert result.embedded_updated_count == 1
    assert result.verified_count == 2
    assert api.records["external"][0]["fields"]["处理进展"] == "外部较新"
    assert api.records["embedded"][0]["fields"]["处理进展"] == "外部较新"
    assert api.records["external"][1]["fields"]["处理进展"] == "内嵌较新"
    assert api.records["embedded"][1]["fields"]["处理进展"] == "内嵌较新"


def test_bidirectional_mirror_creates_records_missing_from_either_side() -> None:
    api = _MirrorAPI(
        external=[_mirror_record("external-a", "item-a", progress="来自外部", modified_time=2_000)],
        embedded=[_mirror_record("embedded-b", "item-b", progress="来自内嵌", modified_time=2_100)],
    )

    with _mirror_client(api) as client:
        result = client.mirror_records_bidirectionally(
            external_app_token="external",
            external_table_id="tbl-external",
            embedded_app_token="embedded",
            embedded_table_id="tbl-embedded",
        )

    assert result.external_created_count == 1
    assert result.embedded_created_count == 1
    assert result.verified_count == 2
    assert {item["fields"]["声音内容/连接"]["text"] for item in api.records["external"]} == {
        "item-a",
        "item-b",
    }
    assert {item["fields"]["声音内容/连接"]["text"] for item in api.records["embedded"]} == {
        "item-a",
        "item-b",
    }


def test_bidirectional_mirror_propagates_known_safe_deletions() -> None:
    api = _MirrorAPI(
        external=[_mirror_record("external-a", "item-a", progress="待删除", modified_time=1_000)],
        embedded=[_mirror_record("embedded-b", "item-b", progress="待删除", modified_time=1_000)],
    )
    known_hashes = tuple(
        sha256(value.encode("utf-8")).hexdigest()
        for value in (
            "https://example.test/item-a",
            "https://example.test/item-b",
        )
    )

    with _mirror_client(api) as client:
        result = client.mirror_records_bidirectionally(
            external_app_token="external",
            external_table_id="tbl-external",
            embedded_app_token="embedded",
            embedded_table_id="tbl-embedded",
            known_key_hashes=known_hashes,
            last_synced_at_ms=1_500,
        )

    assert result.external_deleted_count == 1
    assert result.embedded_deleted_count == 1
    assert result.verified_count == 0
    assert api.records == {"external": [], "embedded": []}


def test_bidirectional_mirror_restores_deleted_side_when_remaining_record_changed() -> None:
    api = _MirrorAPI(
        external=[
            _mirror_record("external-a", "item-a", progress="删除后又修改", modified_time=2_000)
        ],
        embedded=[],
    )
    key = "https://example.test/item-a"

    with _mirror_client(api) as client:
        result = client.mirror_records_bidirectionally(
            external_app_token="external",
            external_table_id="tbl-external",
            embedded_app_token="embedded",
            embedded_table_id="tbl-embedded",
            known_key_hashes=(sha256(key.encode("utf-8")).hexdigest(),),
            last_synced_at_ms=1_500,
        )

    assert result.embedded_created_count == 1
    assert result.external_deleted_count == 0
    assert result.verified_count == 1


def test_bidirectional_mirror_excludes_base_bound_attachments() -> None:
    api = _MirrorAPI(
        external=[
            _mirror_record(
                "external-a",
                "item-a",
                progress="一致",
                modified_time=2_000,
                screenshot_token="external-file",
            )
        ],
        embedded=[
            _mirror_record(
                "embedded-a",
                "item-a",
                progress="一致",
                modified_time=1_000,
                screenshot_token="embedded-file",
            )
        ],
    )

    with _mirror_client(api) as client:
        result = client.mirror_records_bidirectionally(
            external_app_token="external",
            external_table_id="tbl-external",
            embedded_app_token="embedded",
            embedded_table_id="tbl-embedded",
        )

    assert result.excluded_fields == ("声音截图",)
    assert result.external_updated_count == 0
    assert result.embedded_updated_count == 0
    assert api.mutations == []


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
        {
            "field_id": "primary",
            "field_name": "一级标签",
            "type": 3,
            "property": {"options": [{"name": "外观设计"}]},
        },
        {
            "field_id": "secondary",
            "field_name": "二级标签",
            "type": 3,
            "property": {"options": [{"name": "颜色与配色"}]},
        },
        {"field_id": "content-link", "field_name": "声音内容/连接", "type": 1},
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
            assert {field["field_name"] for field in table["fields"]} == (
                {field["field_name"] for field in _fields()}
                | {"一级标签", "二级标签", "用户情绪", "处理进展", "声音截图"}
            )
            field_names = [field["field_name"] for field in table["fields"]]
            ordered_names = [
                "声音内容/连接",
                "声音截图",
                "处理进展",
                "发布时间",
                "一级标签",
                "二级标签",
            ]
            assert [field_names.index(name) for name in ordered_names] == sorted(
                field_names.index(name) for name in ordered_names
            )
            content_link = next(
                field for field in table["fields"] if field["field_name"] == "声音内容/连接"
            )
            assert content_link["type"] == 15
            primary_label = next(
                field for field in table["fields"] if field["field_name"] == "一级标签"
            )
            secondary_label = next(
                field for field in table["fields"] if field["field_name"] == "二级标签"
            )
            assert primary_label["type"] == 4
            assert secondary_label["type"] == 4
            source_sentiment = next(
                field for field in table["fields"] if field["field_name"] == "情感"
            )
            assert source_sentiment["property"] == {"options": [{"name": "正面"}, {"name": "负面"}]}
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
    assert table.app_token == "base"
    assert table.bitable_block_token == "base_tbl-new"
    assert table.url == "https://feishu.cn/base/base?table=tbl-new"
    assert table.as_dict()["bitable_block_token"] == "base_tbl-new"
    assert not any(path.endswith("/records") for _, path in calls)


def test_configure_embedded_table_replaces_only_blank_default_schema() -> None:
    target_fields: list[dict[str, Any]] = [
        {
            "field_id": "primary-default",
            "field_name": "Multiline",
            "type": 1,
            "is_primary": True,
        },
        {"field_id": "default-2", "field_name": "Multiline 1", "type": 1},
        {"field_id": "default-3", "field_name": "Single option", "type": 3},
    ]
    target_records: list[dict[str, Any]] = [
        {"record_id": "rec-default-1", "fields": {}},
        {"record_id": "rec-default-2", "fields": {}},
        {"record_id": "rec-default-3", "fields": {}},
    ]
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "token", "expire": 7200},
            )
        if path == "/open-apis/bitable/v1/apps/base/tables/tbl-template/fields":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": _fields(), "has_more": False}},
            )
        if path == "/open-apis/bitable/v1/apps/embedded/tables/tbl-embedded/records":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": target_records, "has_more": False}},
            )
        fields_path = "/open-apis/bitable/v1/apps/embedded/tables/tbl-embedded/fields"
        if path == fields_path and request.method == "GET":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": target_fields, "has_more": False}},
            )
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, path, body))
        if path.endswith("/records/batch_delete") and request.method == "POST":
            assert body == {"records": ["rec-default-1", "rec-default-2", "rec-default-3"]}
            target_records.clear()
            return httpx.Response(200, json={"code": 0, "data": {"records": []}})
        if path == f"{fields_path}/primary-default" and request.method == "PUT":
            target_fields[0] = {
                "field_id": "primary-default",
                "is_primary": True,
                **body,
            }
            return httpx.Response(200, json={"code": 0, "data": {"field": target_fields[0]}})
        if path.startswith(f"{fields_path}/") and request.method == "DELETE":
            field_id = path.rsplit("/", 1)[-1]
            target_fields[:] = [field for field in target_fields if field["field_id"] != field_id]
            return httpx.Response(200, json={"code": 0, "data": {}})
        if path == fields_path and request.method == "POST":
            created = {"field_id": f"created-{len(target_fields)}", **body}
            target_fields.append(created)
            return httpx.Response(200, json={"code": 0, "data": {"field": created}})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    config = FeishuConfig(app_id="app", app_token="base", table_id="tbl-template", max_retries=0)
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(
        config=config,
        app_secret="secret",
        client=client,
        upsert_key_fields=("声音内容/连接",),
    ) as feishu:
        table = feishu.configure_embedded_table_from_current(
            app_token="embedded",
            table_id="tbl-embedded",
            name="20260922T120000.000000+0800",
        )

    assert table.bitable_block_token == "embedded_tbl-embedded"
    assert table.url is None
    primary_update = next(
        body
        for method, path, body in calls
        if method == "PUT" and path.endswith("/primary-default")
    )
    assert primary_update == {"field_name": "声音内容/连接", "type": 15}
    assert {field["field_name"] for field in target_fields} == (
        {field["field_name"] for field in _fields()} | {"用户情绪", "处理进展", "声音截图"}
    )
    assert not any(path.endswith("/tables") for _method, path, _body in calls)
    assert target_records == []


def test_sync_summary_serializes_target_bitable_identity() -> None:
    summary = FeishuSyncSummary(
        created_count=1,
        updated_count=0,
        verified_count=1,
        verification_errors=(),
        field_mapping=FeishuFieldMapping(resolved={}, unavailable={}),
        target_table_id="tbl-new",
        target_table_name="20260909T120000.000000+0800",
        target_app_token="base",
        target_bitable_block_token="base_tbl-new",
        target_table_url="https://feishu.cn/base/base?table=tbl-new",
    )

    assert summary.as_dict() == {
        "created_count": 1,
        "updated_count": 0,
        "verified_count": 1,
        "verification_errors": [],
        "field_mapping": {"resolved": {}, "unavailable": {}},
        "target_table_id": "tbl-new",
        "target_table_name": "20260909T120000.000000+0800",
        "target_app_token": "base",
        "target_bitable_block_token": "base_tbl-new",
        "target_table_url": "https://feishu.cn/base/base?table=tbl-new",
    }


def test_target_table_schema_uses_content_link_as_idempotency_key() -> None:
    fields = [
        {"field_id": "main", "field_name": "声音内容/连接", "type": 15},
        {"field_id": "example", "field_name": "典型评论示例", "type": 1},
        {
            "field_id": "primary",
            "field_name": "一级标签",
            "type": 3,
            "property": {"options": [{"name": "外观设计"}]},
        },
        {
            "field_id": "secondary",
            "field_name": "二级标签",
            "type": 3,
            "property": {"options": [{"name": "颜色与配色"}]},
        },
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
        {
            "field_id": "progress",
            "field_name": "处理进展",
            "type": 3,
            "property": {"options": [{"name": "待处理"}]},
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
            primary_label="外观设计",
            secondary_label="颜色与配色",
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
    blank_labels = selected_representative_to_row(
        replace(
            selected,
            candidate=replace(
                candidate,
                content=replace(candidate.content, primary_label="", secondary_label=""),
            ),
        )
    )
    assert blank_labels["一级标签"] == "无法分类"
    assert blank_labels["二级标签"] == "无法判断"
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
    assert prepared.creates[0]["声音内容/连接"] == {
        "link": "https://example.test/id-1",
        "text": "用户体验",
    }
    assert "典型评论示例" not in prepared.creates[0]
    assert prepared.creates[0]["来源"] == "抖音"
    assert prepared.creates[0]["一级标签"] == "外观设计"
    assert prepared.creates[0]["二级标签"] == "颜色与配色"
    assert prepared.creates[0]["用户情绪"] == "正面"
    assert "典型评论示例" not in prepared.creates[0]
    assert "处理建议" not in prepared.creates[0]
    assert "处理进展" not in prepared.creates[0]

    row_with_advice = selected_representative_to_row(
        selected,
        action_advice="  建议核查售后流程。 ",
    )
    assert row_with_advice["典型评论示例"] is None
    assert row_with_advice["处理建议"] == "建议核查售后流程。"
    assert row_with_advice["处理进展"] == ""


def test_multi_select_labels_split_newline_values_and_remove_duplicates() -> None:
    fields = [
        {"field_id": "main", "field_name": "声音内容/连接", "type": 15},
        {
            "field_id": "primary",
            "field_name": "一级标签",
            "type": 4,
            "property": {
                "options": [
                    {"name": "外观设计"},
                    {"name": "品牌评价"},
                    {"name": "电池、续航与充电"},
                ]
            },
        },
        {
            "field_id": "secondary",
            "field_name": "二级标签",
            "type": 4,
            "property": {"options": [{"name": "颜色与配色"}, {"name": "口碑与信任"}]},
        },
        {
            "field_id": "source",
            "field_name": "来源",
            "type": 3,
            "property": {"options": [{"name": "抖音"}]},
        },
    ]

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

    config = FeishuConfig(app_id="app", app_token="base", table_id="table", max_retries=0)
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    rows = [
        {
            "声音内容/连接": "https://example.test/id-1",
            "来源": "抖音",
            "一级标签": "电池、续航与充电\n品牌评价\n电池、续航与充电",
            "二级标签": "颜色与配色\r\n口碑与信任",
        }
    ]
    with FeishuBitableClient(
        config=config,
        app_secret="secret",
        client=client,
        upsert_key_fields=("声音内容/连接",),
    ) as feishu:
        prepared = feishu.preflight(rows)

    assert prepared.creates[0]["一级标签"] == ["电池、续航与充电", "品牌评价"]
    assert prepared.creates[0]["二级标签"] == ["颜色与配色", "口碑与信任"]


def test_douyin_screenshot_is_uploaded_as_bitable_attachment(tmp_path) -> None:
    screenshot = tmp_path / "抖音_id-1.png"
    screenshot.write_bytes(b"fake-png")
    fields = [
        {"field_id": "main", "field_name": "声音内容/连接", "type": 15},
        {"field_id": "screenshot", "field_name": "声音截图", "type": 17},
        {
            "field_id": "source",
            "field_name": "来源",
            "type": 3,
            "property": {"options": [{"name": "抖音"}]},
        },
    ]
    uploaded: list[bytes] = []

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
        if path.endswith("/medias/upload_all"):
            body = request.read()
            uploaded.append(body)
            assert b'name="parent_type"\r\n\r\nbitable_file' in body
            assert b'name="parent_node"\r\n\r\nbase' in body
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "file-shot-1"}})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    config = FeishuConfig(app_id="app", app_token="base", table_id="table", max_retries=0)
    client = httpx.Client(
        base_url="https://open.feishu.cn/", transport=httpx.MockTransport(respond)
    )
    with FeishuBitableClient(
        config=config,
        app_secret="secret",
        client=client,
        upsert_key_fields=("声音内容/连接",),
    ) as feishu:
        prepared = feishu.preflight(
            [
                {
                    "声音内容/连接": "https://example.test/id-1",
                    "来源": "抖音",
                    "声音截图": screenshot,
                }
            ]
        )

    assert len(uploaded) == 1
    assert prepared.creates[0]["声音截图"] == [{"file_token": "file-shot-1"}]


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
