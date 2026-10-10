"""普通用户合法读取、导出字段与 Cookie 写请求的公开 HTTP 边界。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.product_http import PostgresProductHttpService
from aima_ugc.bootstrap.reporting_http import PostgresReportingHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.contracts.product import ContentCountResponse
from aima_ugc.entrypoints.api_main import create_app
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.identity.feishu import SESSION_COOKIE_NAME
from aima_ugc.modules.reporting.column_catalog import EXPORT_COLUMN_CATALOG_VERSION
from fastapi import Request
from fastapi.testclient import TestClient


class _Identity:
    """固定已认证 Principal，保留生产路由、列校验和 CSRF 执行。"""

    def __init__(self, role: str = "user", *, source: str = "development") -> None:
        self.principal = Principal("user:columns", "字段用户", role, source)  # type: ignore[arg-type]
        self.trusted_browser_urls = ("https://aima.example:9443/api/v1/auth/feishu/callback",)

    def resolve(self, request: Request) -> Principal:
        del request
        return self.principal


class _ForbiddenRuntime:
    """禁止触碰数据库、Job、Artifact 或 Provider，记录意外业务副作用。"""

    def __init__(self) -> None:
        self.effects: list[str] = []

    def __getattr__(self, name: str) -> Any:
        self.effects.append(name)
        raise AssertionError(f"非法字段必须在获取 Runtime 依赖之前被拒绝: {name}")


class _CountService:
    """内容计数是 POST 只读业务，普通用户仍可访问。"""

    def __init__(self) -> None:
        self.calls = 0

    def count_contents(self, request: Any) -> ContentCountResponse:
        self.calls += 1
        assert request.count_mode == "exact"
        return ContentCountResponse(
            count_mode="exact",
            count=7,
            count_kind="exact",
            as_of=datetime(2026, 10, 10, tzinfo=UTC),
        )


@pytest.mark.parametrize("role", ["user", "administrator"])
def test_column_catalog_and_system_defaults_follow_current_role(role: str) -> None:
    """管理员仍有完整目录；用户的业务列完整且看不到内部来源定位列。"""
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(role),
            product_service=PostgresProductHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.get("/api/v1/export-columns")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == EXPORT_COLUMN_CATALOG_VERSION
    keys = {column["key"] for column in body["columns"]}
    assert {
        "title",
        "text",
        "author_display_name",
        "brands",
        "vehicles",
        "sentiment",
        "primary_label",
        "secondary_label",
        "like_count",
    }.issubset(keys)
    restricted = {"source_item_id", "raw_locator"}
    assert keys & restricted == (restricted if role == "administrator" else set())
    assert runtime.effects == []


@pytest.mark.parametrize("columns", [["raw_locator"], ["source_item_id"], ["no-such-column"]])
def test_forged_export_columns_are_rejected_before_database_or_job(columns: list[str]) -> None:
    """前端目录隐藏不是安全依据；伪造请求仍由 Service 先拒绝。"""
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            reporting_service=PostgresReportingHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.post(
        "/api/v1/data-exports",
        json={
            "targets": {"scope": "selected", "content_ids": [str(uuid4())]},
            "columns": columns,
        },
    )

    assert response.status_code == 422
    if columns[0] in {"raw_locator", "source_item_id"}:
        assert response.json()["errors"][0]["code"] == "export_columns_invalid"
    assert runtime.effects == []


@pytest.mark.parametrize("columns", [[], ["title", "title"], [" title"], [""]])
def test_invalid_personal_defaults_have_validation_error_without_writes(
    columns: list[str],
) -> None:
    """空数组、重复和空白不落库；NULL 才表示系统默认。"""
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            reporting_service=PostgresReportingHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.put(
        "/api/v1/me/export-column-default",
        json={
            "revision": 0,
            "catalog_version": EXPORT_COLUMN_CATALOG_VERSION,
            "columns": columns,
        },
    )

    assert response.status_code == 422
    assert runtime.effects == []


@pytest.mark.parametrize("columns", [["raw_locator"], ["source_item_id"], ["removed-key"]])
def test_personal_default_cannot_bypass_role_column_permission(columns: list[str]) -> None:
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            reporting_service=PostgresReportingHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.put(
        "/api/v1/me/export-column-default",
        json={
            "revision": 0,
            "catalog_version": EXPORT_COLUMN_CATALOG_VERSION,
            "columns": columns,
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "export_columns_invalid"
    assert runtime.effects == []


def test_stale_column_catalog_returns_conflict_without_writing() -> None:
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            reporting_service=PostgresReportingHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.put(
        "/api/v1/me/export-column-default",
        json={
            "revision": 0,
            "catalog_version": EXPORT_COLUMN_CATALOG_VERSION - 1,
            "columns": ["title"],
        },
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "export_column_default_conflict"
    assert runtime.effects == []


def test_personal_default_does_not_accept_client_selected_principal_id() -> None:
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            reporting_service=PostgresReportingHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.put(
        "/api/v1/me/export-column-default",
        json={
            "principal_id": "another-user",
            "revision": 0,
            "catalog_version": EXPORT_COLUMN_CATALOG_VERSION,
            "columns": ["title"],
        },
    )

    assert response.status_code == 422
    assert runtime.effects == []


def test_export_creator_cannot_be_selected_by_client_payload() -> None:
    """客户端无法替另一个 Principal 创建、认领或伪造导出归属。"""
    runtime = _ForbiddenRuntime()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            reporting_service=PostgresReportingHttpService(cast(PlatformRuntime, runtime)),
        )
    )

    response = client.post(
        "/api/v1/data-exports",
        json={
            "targets": {"scope": "selected", "content_ids": [str(uuid4())]},
            "columns": ["title"],
            "created_by": "another-user",
            "requested_by": "another-user",
        },
    )

    assert response.status_code == 422
    assert runtime.effects == []


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example"},
        {"Origin": "https://aima.example:9443", "Sec-Fetch-Site": "cross-site"},
        {"Origin": "https://aima.example:9443", "Sec-Fetch-Site": "same-site"},
        {"Origin": "https://aima.example"},
        {"Origin": "https://aima.example:9443@evil.example"},
    ],
)
def test_cookie_authenticated_write_rejects_untrusted_origin_without_business_effect(
    headers: dict[str, str],
) -> None:
    service = _CountService()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(source="feishu"),
            product_service=service,  # type: ignore[arg-type]
        )
    )
    client.cookies.set(SESSION_COOKIE_NAME, "test-session")

    response = client.post(
        "/api/v1/contents/count",
        json={"count_mode": "exact", "exact_limit": 100},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "csrf_rejected"
    assert service.calls == 0


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://aima.example:9443", "Sec-Fetch-Site": "same-origin"},
        {"Referer": "https://aima.example:9443/voice-plaza"},
    ],
)
def test_configured_public_origin_allows_write_through_internal_http_proxy(
    headers: dict[str, str],
) -> None:
    """受信任回调地址包含协议和端口；无需相信任意 X-Forwarded 头。"""
    service = _CountService()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(source="feishu"),
            product_service=service,  # type: ignore[arg-type]
        ),
        base_url="http://internal-api:8000",
    )
    client.cookies.set(SESSION_COOKIE_NAME, "test-session")

    response = client.post(
        "/api/v1/contents/count",
        json={"count_mode": "exact", "exact_limit": 100},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["count"] == 7
    assert service.calls == 1


def test_development_identity_keeps_local_read_only_post_count_usable() -> None:
    service = _CountService()
    client = TestClient(
        create_app(
            identity_resolver=_Identity(),
            product_service=service,  # type: ignore[arg-type]
        )
    )

    response = client.post(
        "/api/v1/contents/count", json={"count_mode": "exact", "exact_limit": 100}
    )

    assert response.status_code == 200
    assert service.calls == 1
