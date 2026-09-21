"""飞书登录路由中**不依赖数据库**部分的单元回归。

覆盖任务书 DoD：

    D1  三个路由的路径与契约路径完全一致
    D4  `return_to` 白名单：合法站内路径放行，绝对 URL / `//evil` / `javascript:` 等全拒
    D9  授权码 / state 不会进入访问日志（query string 被抹掉）
    配置  未配飞书 → 不启用；半配 → 直接报错（不静默降级）

这里**不连数据库**：路由挂了没有、跳转目标合不合法、日志里有什么，
都不需要真实 PostgreSQL 才能验证。真正的登录全流程在
`tests/integration/platform/test_feishu_login_routes.py` 验证。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aima_ugc.bootstrap.feishu_auth_http import (
    CALLBACK_PATH,
    LOGIN_PATH,
    LOGOUT_PATH,
    MULTI_CALLBACK_PATH,
    MULTI_LOGIN_PATH,
    AuthenticationRequired,
    FeishuAuthRoutes,
    FeishuAuthSettings,
    _CookieRedactingMiddleware,
    build_feishu_auth_settings,
    build_feishu_identity,
    is_safe_return_to,
    safe_return_to,
)
from aima_ugc.entrypoints.api_main import create_app as create_main_app
from aima_ugc.modules.identity import AuthorizationDenied, DevelopmentIdentityResolver
from aima_ugc.platform.config import load_settings
from pydantic import SecretStr, ValidationError

# ── D4：必须被拒绝的 `return_to` 形态（每一条都对应一种真实绕过手法）────────────
UNSAFE_RETURN_TO = [
    "https://evil.example/steal",  # 绝对 URL
    "http://127.0.0.1/admin",  # 明文绝对 URL
    "//evil.example/steal",  # 协议相对 URL（最容易被漏掉）
    "///evil.example",  # 三个斜杠仍会被浏览器当主机
    "/\\evil.example",  # 反斜杠：浏览器当 "/"，等价于 //evil
    "\\/evil.example",  # 同上，反向拼写
    "%2f%2fevil.example",  # 编码斜杠（缺前导 /，仍拒）
    "/%2f%2fevil.example",  # 先解码再跳的经典绕过
    "/%5Cevil.example",  # 编码反斜杠
    "javascript:alert(1)",  # 伪协议
    "data:text/html,<script>alert(1)</script>",  # data 伪协议
    "/path\r\nSet-Cookie: x=1",  # 响应头注入
    "/path\nEvil",  # 换行
    "/path\0",  # NUL 截断
    "dashboard",  # 不带前导 "/"，会被拼到当前路径上，行为不可控
    "",  # 空串
    "   ",  # 纯空白
]

# ── D4：必须被放行的站内相对路径 ─────────────────────────────────────────────
SAFE_RETURN_TO = [
    "/",
    "/voice-plaza",
    "/admin/configuration",
    "/collection-runtime?status=running",
    "/voice-plaza#detail",
]


@pytest.mark.parametrize("value", UNSAFE_RETURN_TO)
def test_d4_unsafe_return_to_is_rejected(value: str) -> None:
    """白名单必须**拒绝**一切非站内相对路径，且不原样放行。"""

    assert is_safe_return_to(value) is False, f"不该放行: {value!r}"
    # fail closed：不安全的值退回默认值，绝不原样返回。
    assert safe_return_to(value) == "/"


@pytest.mark.parametrize("value", SAFE_RETURN_TO)
def test_d4_safe_return_to_passes_through(value: str) -> None:
    """合法站内相对路径必须原样（去除首尾空白后）放行。"""

    assert is_safe_return_to(value) is True, f"不该拒绝: {value!r}"
    assert safe_return_to(value) == value


def test_d4_missing_return_to_falls_back_to_root() -> None:
    """没有 `return_to` 时退到首页，而不是报错。"""

    assert is_safe_return_to(None) is False
    assert safe_return_to(None) == "/"


# ── D1：三个路由的路径必须与任务书 §三 完全一致 ────────────────────────────────
def test_d1_route_paths_are_the_frozen_contract() -> None:
    """路径字符串本身是契约，写死断言防止被"顺手改名"。"""

    assert LOGIN_PATH == "/api/v1/auth/feishu/login"
    assert CALLBACK_PATH == "/api/v1/auth/feishu/callback"
    assert LOGOUT_PATH == "/api/v1/auth/logout"


def test_d1_unconfigured_deployment_installs_the_same_three_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配飞书时三个路由**仍然注册**（返回 503），且身份仍是开发身份。

    路由存在与"能力启用"是两件事：路由决定 URL 契约是否稳定；配置决定它背后是飞书还是
    "未启用"。这样部署不会因为少配一个环境变量就 404 —— 404 会被误当成"接口写错了"。
    """

    for name in (
        "AIMA_FEISHU_APP_ID",
        "AIMA_FEISHU_ADMIN_GROUP_ID",
        "AIMA_FEISHU_USER_GROUP_ID",
        "AIMA_FEISHU_REDIRECT_URI",
    ):
        monkeypatch.delenv(name, raising=False)

    application = create_main_app()
    registered = {getattr(route, "path", None) for route in application.routes}

    assert {LOGIN_PATH, CALLBACK_PATH, LOGOUT_PATH} <= registered
    assert application.openapi()["paths"][LOGIN_PATH]["get"]["operationId"] == "startFeishuLogin"
    assert {"404", "429", "503"} <= set(
        application.openapi()["paths"][LOGIN_PATH]["get"]["responses"]
    )
    old_login_parameters = application.openapi()["paths"][LOGIN_PATH]["get"]["parameters"]
    assert {parameter["name"] for parameter in old_login_parameters} == {
        "return_to",
        "connector",
    }
    multi_login_parameters = application.openapi()["paths"][MULTI_LOGIN_PATH]["get"]["parameters"]
    connector_parameter = next(
        parameter for parameter in multi_login_parameters if parameter["name"] == "connector_code"
    )
    assert connector_parameter["in"] == "path"
    assert connector_parameter["required"] is True
    assert connector_parameter["schema"] == {"type": "string", "title": "Connector Code"}
    old_callback_parameters = application.openapi()["paths"][CALLBACK_PATH]["get"]["parameters"]
    assert {parameter["name"] for parameter in old_callback_parameters} == {"code", "state"}
    multi_callback_parameters = application.openapi()["paths"][MULTI_CALLBACK_PATH]["get"][
        "parameters"
    ]
    assert next(
        parameter
        for parameter in multi_callback_parameters
        if parameter["name"] == "connector_code"
    )["schema"] == {"type": "string", "title": "Connector Code"}
    assert application.openapi()["paths"][LOGOUT_PATH]["post"]["operationId"] == (
        "logoutCurrentSession"
    )


def test_d1_configured_deployment_installs_the_three_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配了飞书时同样注册三个路由（这一步不碰数据库）。"""

    monkeypatch.setenv("AIMA_FEISHU_APP_ID", "cli_test_app_id")
    monkeypatch.setenv("AIMA_FEISHU_ADMIN_GROUP_ID", "grp_admin")
    monkeypatch.setenv("AIMA_FEISHU_USER_GROUP_ID", "grp_user")
    monkeypatch.setenv(
        "AIMA_FEISHU_REDIRECT_URI", "http://localhost:8000/api/v1/auth/feishu/callback"
    )

    application = create_main_app()
    registered = {getattr(route, "path", None) for route in application.routes}

    assert {LOGIN_PATH, CALLBACK_PATH, LOGOUT_PATH} <= registered


# ── D13：未配飞书 → 保持开发身份（不破坏现状）────────────────────────────────
def test_d13_unconfigured_identity_stays_development() -> None:
    """没有 `AIMA_FEISHU_APP_ID` 时，装配结果必须是开发身份。"""

    resolver, routes = build_feishu_identity(load_settings({}))

    assert isinstance(resolver, DevelopmentIdentityResolver)
    assert routes is not None


def test_unconfigured_auth_routes_report_not_configured() -> None:
    """未启用时三个路由必须回答 503（"能力未启用"），而不是 500 或 404。"""

    application = create_main_app()
    from fastapi.testclient import TestClient

    client = TestClient(application, raise_server_exceptions=False)
    response = client.get(LOGIN_PATH)

    assert response.status_code == 503
    assert response.json()["status"] == 503
    assert response.json()["errors"][0]["code"] == "feishu_not_configured"


# ── D6 前置：401（未登录）与 403（无权限）必须是**两个**语义 ──────────────────
def test_authentication_required_is_a_more_specific_authorization_denied() -> None:
    """401 异常必须仍是 `AuthorizationDenied` 的子类，但能被更具体的处理器接住。

    这样既有 `except AuthorizationDenied` 的调用方行为不变，同时前端能区分
    "去登录（401）"与"你别登了（403）"。
    """

    assert issubclass(AuthenticationRequired, AuthorizationDenied)
    assert AuthenticationRequired is not AuthorizationDenied


# ── D9：授权码 / state 不得进入访问日志 ──────────────────────────────────────
# ⚠️ 项目未安装 pytest-asyncio，因此用 `asyncio.run` 驱动 ASGI 协程，
# 而不是给测试套件引入新依赖（任务书 §2.2「不引新依赖」）。
def test_d9_sensitive_query_is_redacted_before_downstream() -> None:
    """中间件必须把 `code` / `state` 从 ASGI `scope` 里换掉，真实值另存内存。"""

    seen: dict[str, Any] = {}

    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        seen["query"] = bytes(scope["query_string"]).decode("latin-1")
        seen["state"] = dict(scope.get("state") or {})

    middleware = _CookieRedactingMiddleware(downstream)
    scope = {
        "type": "http",
        "path": CALLBACK_PATH,
        "query_string": b"code=AUTH_CODE_VALUE&state=STATE_VALUE&foo=bar",
        "state": {},
    }

    asyncio.run(middleware(scope, None, None))  # type: ignore[arg-type]

    # 下游拿到的是打码后的 query（uvicorn 访问日志同源读这里），原文已被替换。
    assert "AUTH_CODE_VALUE" not in seen["query"]
    assert "STATE_VALUE" not in seen["query"]
    assert "foo=bar" in seen["query"]
    # 但真实参数仍在（路由要用），只是不参与日志。
    assert seen["state"]["feishu_auth_params"] == {
        "code": "AUTH_CODE_VALUE",
        "state": "STATE_VALUE",
    }
    # 中间件改写的是**同一个** scope 对象，uvicorn 访问日志读到的也是打码后的值。
    assert "AUTH_CODE_VALUE" not in bytes(scope["query_string"]).decode("latin-1")


def test_d9_non_callback_paths_keep_their_query_string() -> None:
    """只有回调路径需要打码；别把无关路径的 query 也改坏。"""

    seen: dict[str, str] = {}

    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        seen["query"] = bytes(scope["query_string"]).decode("latin-1")

    middleware = _CookieRedactingMiddleware(downstream)
    scope = {
        "type": "http",
        "path": "/api/v1/contents",
        "query_string": b"code=NOT_A_SECRET_HERE",
        "state": {},
    }

    asyncio.run(middleware(scope, None, None))  # type: ignore[arg-type]

    assert seen["query"] == "code=NOT_A_SECRET_HERE"


# ── 配置：整组配齐 / 整组不配 ────────────────────────────────────────────────
def test_feishu_settings_absent_means_disabled() -> None:
    """一个都不配 → `None`（不启用），而不是"启用了一个没组 ID 的空壳"。"""

    assert build_feishu_auth_settings(load_settings({})) is None


def test_feishu_settings_partial_configuration_is_rejected() -> None:
    """只配 App ID（无组 ID / 回调地址）必须直接报错，不能静默降级。"""

    with pytest.raises(ValidationError) as error:
        load_settings(
            {
                "AIMA_FEISHU_APP_ID": "cli_test_app_id",
                "AIMA_FEISHU_ADMIN_GROUP_ID": "grp_admin",
            }
        )

    message = str(error.value)
    assert "AIMA_FEISHU_USER_GROUP_ID" in message
    assert "AIMA_FEISHU_REDIRECT_URI" in message


def test_feishu_settings_blank_env_is_treated_as_absent() -> None:
    """`AIMA_FEISHU_APP_ID=`（留空）必须等价于"没配"，否则容器会起不来。"""

    settings = load_settings({"AIMA_FEISHU_APP_ID": ""})

    assert settings.feishu_app_id is None
    assert build_feishu_auth_settings(settings) is None


def test_feishu_settings_secure_flag_follows_redirect_scheme() -> None:
    """Cookie 的 `Secure` 按环境：本地 http 关、生产 https 开。"""

    local = build_feishu_auth_settings(
        load_settings(
            {
                "AIMA_FEISHU_APP_ID": "cli_test_app_id",
                "AIMA_FEISHU_ADMIN_GROUP_ID": "grp_admin",
                "AIMA_FEISHU_USER_GROUP_ID": "grp_user",
                "AIMA_FEISHU_REDIRECT_URI": "http://localhost:8000/cb",
            }
        )
    )
    production = build_feishu_auth_settings(
        load_settings(
            {
                "AIMA_FEISHU_APP_ID": "cli_test_app_id",
                "AIMA_FEISHU_ADMIN_GROUP_ID": "grp_admin",
                "AIMA_FEISHU_USER_GROUP_ID": "grp_user",
                "AIMA_FEISHU_REDIRECT_URI": "https://aima.example/cb",
            }
        )
    )

    assert local is not None and production is not None
    assert local.cookie_secure is False, "本地 HTTP 必须关掉 Secure，否则 Cookie 写不进去"
    assert production.cookie_secure is True, "生产 HTTPS 必须开启 Secure"


def test_feishu_settings_explicit_secure_override_wins() -> None:
    """显式设置的 `AIMA_FEISHU_COOKIE_SECURE` 优先于协议推断。"""

    settings = build_feishu_auth_settings(
        load_settings(
            {
                "AIMA_FEISHU_APP_ID": "cli_test_app_id",
                "AIMA_FEISHU_ADMIN_GROUP_ID": "grp_admin",
                "AIMA_FEISHU_USER_GROUP_ID": "grp_user",
                "AIMA_FEISHU_REDIRECT_URI": "http://localhost:8000/cb",
                "AIMA_FEISHU_COOKIE_SECURE": "true",
            }
        )
    )

    assert settings is not None
    assert settings.cookie_secure is True


def test_connector_id_is_stable_per_app() -> None:
    """同一 App 必须派生出同一个 `connector_id`，否则同一个人会被拆成两个身份。"""

    def settings_for(app_id: str) -> FeishuAuthSettings:
        built = build_feishu_auth_settings(
            load_settings(
                {
                    "AIMA_FEISHU_APP_ID": app_id,
                    "AIMA_FEISHU_ADMIN_GROUP_ID": "grp_admin",
                    "AIMA_FEISHU_USER_GROUP_ID": "grp_user",
                    "AIMA_FEISHU_REDIRECT_URI": "http://localhost:8000/cb",
                }
            )
        )
        assert built is not None
        return built

    assert settings_for("cli_a").connector_id == settings_for("cli_a").connector_id
    assert settings_for("cli_a").connector_id != settings_for("cli_b").connector_id


def test_auth_routes_require_settings_before_touching_dependencies() -> None:
    """未配置时路由装配体自身也要明确报"未启用"。"""

    routes = FeishuAuthRoutes(auth_settings=None)

    with pytest.raises(Exception) as error:
        routes._require_settings()  # noqa: SLF001 - 断言的就是这个内部守卫

    assert error.value.__class__.__name__ == "_FeishuNotConfigured"


def test_multi_connector_clients_use_their_own_app_and_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多企业回调必须按当前企业选择 App ID 与 Secret，不能复用默认企业客户端。"""

    import aima_ugc.bootstrap.feishu_auth_http as auth_http

    class FakeHttpxFeishuClient:
        """只记录装配参数，避免单测建立真实网络连接池。"""

        def __init__(self, *, app_id: str, app_secret: SecretStr) -> None:
            self.app_id = app_id
            self.app_secret = app_secret.get_secret_value()

        def close(self) -> None:
            """匹配生产客户端生命周期接口。"""

    monkeypatch.setattr(auth_http, "HttpxFeishuClient", FakeHttpxFeishuClient)

    first = FeishuAuthSettings(
        app_id="cli_first",
        app_secret_ref="first_secret",
        admin_group_id="grp_first_admin",
        user_group_id="grp_first_user",
        redirect_uri="https://example.test/api/v1/auth/feishu/first/callback",
    )
    second = FeishuAuthSettings(
        app_id="cli_second",
        app_secret_ref="second_secret",
        admin_group_id="grp_second_admin",
        user_group_id="grp_second_user",
        redirect_uri="https://example.test/api/v1/auth/feishu/second/callback",
    )
    read_refs: list[str] = []

    def read_secret(secret_ref: str) -> SecretStr:
        read_refs.append(secret_ref)
        return SecretStr(f"value-for-{secret_ref}")

    routes = FeishuAuthRoutes(
        auth_settings=first,
        connectors={"first": first, "second": second},
        app_secret_reader=read_secret,
    )

    first_client = routes._feishu_client(first)  # noqa: SLF001 - 验证生产装配边界
    second_client = routes._feishu_client(second)  # noqa: SLF001 - 验证生产装配边界
    assert first_client is not second_client
    assert first_client.app_id == "cli_first"  # type: ignore[attr-defined]
    assert second_client.app_id == "cli_second"  # type: ignore[attr-defined]
    assert first_client.app_secret == "value-for-first_secret"  # type: ignore[attr-defined]
    assert second_client.app_secret == "value-for-second_secret"  # type: ignore[attr-defined]
    assert read_refs == ["first_secret", "second_secret"]
