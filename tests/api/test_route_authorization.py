"""最终应用全部实际路由的认证、管理员拒绝及无业务副作用边界。"""

from __future__ import annotations

import re
import sys
from typing import Any
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.feishu_auth_http import (
    AuthenticationRequired,
    FeishuAuthRoutes,
)
from aima_ugc.bootstrap.route_authorization import route_authorization_inventory
from aima_ugc.bootstrap.route_policy import ROUTE_POLICIES
from aima_ugc.entrypoints import api_main
from aima_ugc.modules.identity import Principal
from fastapi import Request
from fastapi.testclient import TestClient

_ADMIN_ROUTES = tuple(key for key, value in ROUTE_POLICIES.items() if value == "administrator")
_PROTECTED_ROUTES = tuple(key for key, value in ROUTE_POLICIES.items() if value != "public")
_SERVICE_ARGUMENTS = (
    "import_service",
    "content_service",
    "reporting_service",
    "collection_service",
    "strategy_service",
    "historical_import_service",
    "canonical_replay_service",
    "administration_service",
    "feishu_publication_service",
    "report_runs_service",
    "product_service",
    "workbench_service",
)


class _Identity:
    """仅替换已验证身份来源；不替换任何路由授权或业务服务。"""

    def __init__(self, principal: Principal | None) -> None:
        self.principal = principal
        self.calls = 0

    def resolve(self, request: Request) -> Principal:
        """每次请求重新反映撤销或角色变化。"""
        del request
        self.calls += 1
        if self.principal is None:
            raise AuthenticationRequired
        return self.principal


class _ForbiddenBusiness:
    """任何 Service 访问都证明认证/授权执行得太晚。"""

    def __init__(self, side_effects: list[str]) -> None:
        self.side_effects = side_effects

    def __getattr__(self, name: str) -> Any:
        self.side_effects.append(f"service:{name}")
        raise AssertionError(f"拒绝请求不能进入业务服务: {name}")


def _path(template: str) -> str:
    """用合法 UUID/位置覆盖对象路由，避免无效参数掩盖授权失败。"""
    return re.sub(
        r"\{([^}]+)\}",
        lambda match: "0" if match.group(1) == "position" else str(uuid4()),
        template,
    )


@pytest.fixture
def guarded_application(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """使用最终 assembly，给所有业务和 Runtime 构造设置失败探针。"""
    side_effects: list[str] = []
    identity = _Identity(Principal("user:ordinary", "普通用户", "user", "development"))
    unexpected = _ForbiddenBusiness(side_effects)

    def forbidden_runtime(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        side_effects.append("runtime:database/artifact/provider")
        raise AssertionError("拒绝请求不能初始化数据库、Artifact 或外部 Provider Runtime")

    # 扩展路由有各自的懒装配入口；一起拦截才不遗漏兼容/隐藏路由。
    for name, module in tuple(sys.modules.items()):
        if name.startswith("aima_ugc.bootstrap.") and hasattr(module, "create_platform_runtime"):
            monkeypatch.setattr(module, "create_platform_runtime", forbidden_runtime)
    monkeypatch.setattr(
        api_main,
        "build_feishu_identity",
        lambda: (identity, FeishuAuthRoutes(auth_settings=None)),
    )
    application = api_main.create_app(
        **dict.fromkeys(_SERVICE_ARGUMENTS, unexpected),
    )
    return application, identity, side_effects


@pytest.mark.parametrize(("method", "path"), _ADMIN_ROUTES)
def test_every_administrator_route_rejects_user_before_any_business_effect(
    guarded_application,
    method: str,
    path: str,  # type: ignore[no-untyped-def]
) -> None:
    """包括 GET、预览、取消、Lifecycle、Legacy 和框架文档入口。"""
    application, _, side_effects = guarded_application
    client = TestClient(application, raise_server_exceptions=False)

    response = client.request(method, _path(path), content=b"not-valid-json")

    assert response.status_code == 403, (method, path, response.text)
    if method != "HEAD":
        assert response.json()["errors"][0]["code"] == "administrator_required"
        assert response.json()["request_id"] == response.headers["x-request-id"]
    assert side_effects == [], "不得创建/取消 Job、写数据库、调用 Provider 或变更 Artifact"


@pytest.mark.parametrize(("method", "path"), _PROTECTED_ROUTES)
def test_every_protected_route_rejects_missing_session_before_any_business_effect(
    guarded_application,
    method: str,
    path: str,  # type: ignore[no-untyped-def]
) -> None:
    """业务读取、个人配置、内部媒体与对象下载同样要求会话。"""
    application, identity, side_effects = guarded_application
    identity.principal = None
    response = TestClient(application, raise_server_exceptions=False).request(
        method,
        _path(path),
        content=b"not-valid-json",
    )

    assert response.status_code == 401, (method, path, response.text)
    if method != "HEAD":
        assert response.json()["errors"][0]["code"] == "authentication_required"
        assert response.json()["request_id"] == response.headers["x-request-id"]
    assert side_effects == []


def test_inventory_covers_final_extensions_hidden_routes_and_each_method(
    guarded_application,  # type: ignore[no-untyped-def]
) -> None:
    """审计来自最终注册集合，不能只检查 OpenAPI 可见的主 Router。"""
    application, _, _ = guarded_application
    inventory = route_authorization_inventory(application)
    actual = {(entry["method"], entry["path"]) for entry in inventory}

    assert actual == set(ROUTE_POLICIES)
    assert ("GET", "/api/v1/contents/{content_id}/media/{position}") in actual
    assert ("POST", "/api/v1/data-import-campaigns/{campaign_id}/revoke") in actual
    assert ("POST", "/api/v1/provider-configs/{provider_config_id}/restore") in actual
    assert ("GET", "/docs") in actual
    assert ("HEAD", "/docs") in actual
    assert application.state.route_authorization_policy == inventory


@pytest.mark.parametrize("include_in_schema", [True, False])
def test_late_unknown_route_blocks_startup(
    guarded_application,
    include_in_schema: bool,  # type: ignore[no-untyped-def]
) -> None:
    """新增接口没有明确策略时启动失败；隐藏接口不能成为逃逸入口。"""
    application, _, side_effects = guarded_application

    @application.get("/api/v1/unclassified-business", include_in_schema=include_in_schema)
    def unclassified() -> dict[str, bool]:
        return {"should_not_run": True}

    with pytest.raises(RuntimeError, match="未声明权限"):
        with TestClient(application):
            pytest.fail("未知授权路由不能进入运行状态")
    assert side_effects == []


def test_identity_is_resolved_once_per_request_but_revocation_applies_next_request(
    guarded_application,  # type: ignore[no-untyped-def]
) -> None:
    """Route 与 Service 复用可信身份，但不跨请求缓存 Session。"""
    application, identity, side_effects = guarded_application
    client = TestClient(application)

    assert client.get("/api/v1/principal").status_code == 200
    assert identity.calls == 1
    identity.principal = None
    assert client.get("/api/v1/principal").status_code == 401
    assert identity.calls == 2
    assert side_effects == []


def test_identity_dependency_failure_is_not_disguised_as_missing_session(
    guarded_application,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    """真实依赖故障保持故障语义，不能诱导重新登录循环。"""
    application, identity, side_effects = guarded_application

    def unavailable(request: Request) -> Principal:
        del request
        raise RuntimeError("identity dependency unavailable")

    monkeypatch.setattr(identity, "resolve", unavailable)
    response = TestClient(application, raise_server_exceptions=False).get("/api/v1/principal")

    assert response.status_code == 500
    assert response.json()["errors"][0]["code"] == "internal_error"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "authentication_required" not in response.text
    assert side_effects == []


def test_public_liveness_does_not_require_identity_or_business_dependencies(
    guarded_application,  # type: ignore[no-untyped-def]
) -> None:
    """公开健康检查仍可被容器探针调用；认证服务不可用也不阻塞存活探测。"""
    application, identity, side_effects = guarded_application
    identity.principal = None

    response = TestClient(application).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert identity.calls == 0
    assert side_effects == []
