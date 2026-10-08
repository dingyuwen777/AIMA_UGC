"""多企业**登录路由**的 PostgreSQL 集成回归。

════════ 为什么必须单独写这个文件 ════════

多企业改造交付时发现：**新路由 `/api/v1/auth/feishu/{connector_code}/...`
在集成测试里零覆盖** —— 既有 `test_feishu_login_routes.py` 只打了旧路由
（`/login`、`/callback`）。而"路由能注册"不等于"这条链路能走通"：

    · 路径参数 `connector_code` 会不会与飞书回调的 `code` 撞名？
    · 多企业时 `redirect_uri` / `app_id` 有没有取到**本企业**的？
    · 跨企业拿 state 打回调会不会被放行？

这些都只有**真实走一遍 HTTP 链路**才能证明。本文件补上这一段。

════════ 覆盖什么 ════════

    M1  `/feishu/nnit/login` → 302，授权页 `client_id` 是 **NNIT** 的
    M2  `/feishu/aima/login` → 302，授权页 `client_id` 是 **爱玛**的 ★ 关键
    M3  授权页的 `redirect_uri` 是**本企业**那条（不是别家的）
    M4  ★ **路径参数不撞名**：`connector_code` 拿到企业标识，`code` 拿到授权码
    M5  `/feishu/aima/callback` 全流程 → 建会话 → 302 回站内
    M6  两家企业的会话**互不干扰**（各自能取到身份）
    M7  **跨企业 state** 打回调 → 被拒（400）
    M8  未知 code → **404**（不是 500、不是静默回退）
    M9  `/api/v1/auth/connectors` 返回两家（只含 code 与显示名）
    M10 旧路由（不带 code）在**多企业形态**下仍可用（走默认那家）

⚠️ 用**真实 PostgreSQL** + **假飞书**：数据库的一次性 state、会话哈希是数据库行为；
真实飞书是外部资源，测试里不真调。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.feishu_auth_http import (
    CALLBACK_PATH,
    CONNECTORS_PATH,
    LOGIN_PATH,
    MULTI_CALLBACK_PATH,
    MULTI_LOGIN_PATH,
    FeishuAuthRoutes,
    FeishuLoginRequiredResolver,
    install_feishu_auth_routes,
)
from aima_ugc.modules.identity.feishu import (
    FeishuDepartment,
    FeishuTokens,
    FeishuUser,
    FeishuUserDetail,
)
from aima_ugc.modules.identity.feishu.session_store import SESSION_COOKIE_NAME
from aima_ugc.modules.identity.tables import (
    identity_external_identities_table,
)
from aima_ugc.platform.config import PlatformSettings
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.platform import identity_test_database

# ── 两家企业的固定值（与真实部署口径一致）─────────────────────────────
SITE = "http://site.example"
NNIT = {
    "code": "nnit",
    "display_name": "NNIT",
    "app_id": "cli_nnit_test",
    "app_secret_ref": "secret_nnit",
    "admin_group_id": "nnit-admin-group",
    "user_group_id": "nnit-user-group",
    "redirect_uri": f"{SITE}/api/v1/auth/feishu/nnit/callback",
}
AIMA = {
    "code": "aima",
    "display_name": "爱玛科技",
    "app_id": "cli_aima_test",
    "app_secret_ref": "secret_aima",
    "admin_group_id": "aima-admin-group",
    "user_group_id": "aima-user-group",
    "redirect_uri": f"{SITE}/api/v1/auth/feishu/aima/callback",
}
AUTH_CODE = "AUTHORIZATION_CODE_FROM_FEISHU"
CLIENT_IP = "203.0.113.7"


class FakeFeishuClient:
    """假飞书：只实现登录链路用到的方法（与既有集成测试同风格）。

    ⚠️ 刻意**不区分企业** —— 它是替身，用来证明"客户端被正确注入"；
    "客户端是否按企业区分"由 `tests/unit/identity/test_multi_connector_clients.py` 覆盖。
    """

    def __init__(self, *, group_ids: tuple[str, ...] = ()) -> None:
        """保存本用例模拟的企业群组。"""

        self._group_ids = group_ids

    def exchange_authorization_code(self, code: str) -> FeishuTokens:
        """校验传入的是授权码并返回模拟用户令牌。"""

        assert code == AUTH_CODE, f"回调拿到的 code 不是授权码：{code!r}"
        return FeishuTokens(
            access_token="u-fake-access",
            expires_in=7200,
            token_type="Bearer",
            scope="contact:user.base:readonly",
            refresh_token="r-fake-refresh",
        )

    def get_current_user(self, user_access_token: str) -> FeishuUser:
        """返回当前路由场景的固定模拟用户。"""

        return FeishuUser(
            open_id="ou-fake-1",
            name="测试用户",
            union_id="on-fake-1",
            avatar_url=None,
        )

    def list_user_groups(self, open_id: str) -> tuple[str, ...]:
        """返回本用例指定的企业群组。"""

        return self._group_ids

    def get_user(self, open_id: str) -> FeishuUserDetail:
        """⚠️ `FeishuUserDetail` 只有 `open_id` / `name` / `department_ids` / `avatar_url`
        —— **没有 `union_id`**（那是 `FeishuUser` 的字段）。"""

        return FeishuUserDetail(
            open_id=open_id,
            name="测试用户",
            department_ids=("od-dept-1",) if self._group_ids else (),
            avatar_url=None,
        )

    def get_department(self, department_id: str) -> FeishuDepartment:
        """⚠️ 字段名是 `department_id`（不是 `open_department_id`）。"""

        return FeishuDepartment(department_id=department_id, name="测试部门")


def _connectors_json() -> str:
    """两家企业的 `AIMA_FEISHU_CONNECTORS`（紧凑单行 JSON）。"""

    import json

    return json.dumps([NNIT, AIMA], ensure_ascii=False, separators=(",", ":"))


@pytest.fixture
def pg_session_factory() -> Iterator[sessionmaker[Session]]:
    """复用连接前拒绝业务数据库的隔离身份测试环境。"""

    yield from identity_test_database.isolated_identity_database()


def _build_multi_client(
    session_factory: sessionmaker[Session],
    *,
    group_ids: tuple[str, ...] = (),
) -> tuple[TestClient, FeishuAuthRoutes]:
    """按**入口同样的方式**装配一个多企业应用，注入假飞书与真实 Session 工厂。"""

    # ⚠️ 多企业形态：用 AIMA_FEISHU_CONNECTORS，而不是单企业字段。
    settings = PlatformSettings(
        data_dir=Path("."),
        log_dir=Path("."),
        secret_dir=Path("."),
        feishu_connectors_json=_connectors_json(),
    )
    from aima_ugc.bootstrap.feishu_auth_http import _build_connector_settings_map

    cmap = _build_connector_settings_map(settings)

    def fake_secret(secret_ref: str) -> SecretStr:
        """匹配当前密钥读取接口；真实飞书客户端由替身隔离。"""

        return SecretStr(f"FAKE_SECRET_{secret_ref}")

    routes = FeishuAuthRoutes(
        auth_settings=next(iter(cmap.values())),
        connectors=cmap,
        connector_display_names={c["code"]: c["display_name"] for c in (NNIT, AIMA)},
        session_factory=session_factory,
        client=FakeFeishuClient(group_ids=group_ids),  # type: ignore[arg-type]
        app_secret_reader=fake_secret,
    )
    application = create_app(identity_resolver=FeishuLoginRequiredResolver(routes))
    install_feishu_auth_routes(application, auth_routes=routes)
    return TestClient(application, raise_server_exceptions=False), routes


def _state_from(client: TestClient, path: str) -> tuple[str, str]:
    """走一次登录，返回 `(state, redirect_uri)`。"""

    resp = client.get(path, follow_redirects=False, headers={"x-forwarded-for": CLIENT_IP})
    assert resp.status_code == 302, f"{path} 期望 302，实际 {resp.status_code}"
    location = resp.headers["location"]
    assert "accounts.feishu.cn" in location or "open.feishu.cn" in location, location
    qs = location.split("?", 1)[1]
    query = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
    from urllib.parse import unquote

    return query["state"], unquote(query.get("redirect_uri", ""))


# ═══════════════ M1~M3 登录入口按企业分流 ═══════════════
def test_m1_nnit_login_redirects_with_nnit_app_id(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M1：`/feishu/nnit/login` → 授权页的 `client_id` 是 **NNIT** 的。"""

    client, _ = _build_multi_client(pg_session_factory)
    resp = client.get(MULTI_LOGIN_PATH.replace("{connector_code}", "nnit"), follow_redirects=False)
    assert resp.status_code == 302
    from urllib.parse import unquote

    location = unquote(resp.headers["location"])
    assert f"client_id={NNIT['app_id']}" in location


def test_m2_aima_login_redirects_with_aima_app_id(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M2 ★：`/feishu/aima/login` → 授权页的 `client_id` 是 **爱玛**的。

    这条是那个"共用客户端"缺陷的**端到端**回归：早期实现会让这里出现 NNIT 的 App ID。
    """

    client, _ = _build_multi_client(pg_session_factory)
    resp = client.get(MULTI_LOGIN_PATH.replace("{connector_code}", "aima"), follow_redirects=False)
    assert resp.status_code == 302
    from urllib.parse import unquote

    location = unquote(resp.headers["location"])
    assert f"client_id={AIMA['app_id']}" in location, location
    assert NNIT["app_id"] not in location, "爱玛的登录跳到了 NNIT 的应用"


def test_m3_redirect_uri_is_own_enterprise(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M3：授权页带的 `redirect_uri` 是**本企业**那条，不是别家的。"""

    client, _ = _build_multi_client(pg_session_factory)
    _, nnit_uri = _state_from(client, MULTI_LOGIN_PATH.replace("{connector_code}", "nnit"))
    _, aima_uri = _state_from(client, MULTI_LOGIN_PATH.replace("{connector_code}", "aima"))
    assert nnit_uri == NNIT["redirect_uri"]
    assert aima_uri == AIMA["redirect_uri"]
    assert nnit_uri != aima_uri


# ═══════════════ M4 ★ 路径参数不撞名 ═══════════════
def test_m4_path_param_does_not_shadow_feishu_code(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M4 ★：**路径参数 `connector_code` 不与飞书授权码 `code` 撞名**。

    若路径参数也取名 `code`，FastAPI 会**静默**把企业标识填进授权码参数，
    回调时拿它去换令牌 → 飞书报"授权码无效"，而根源在参数名。

    这里直接走一次完整回调，断言"换令牌收到的是真授权码"——
    `FakeFeishuClient.exchange_authorization_code` 里有 `assert code == AUTH_CODE`，
    若被路径参数污染，这个断言会失败。
    """

    client, _ = _build_multi_client(pg_session_factory, group_ids=("nnit-user-group",))
    state, _ = _state_from(client, MULTI_LOGIN_PATH.replace("{connector_code}", "nnit"))

    resp = client.get(
        MULTI_CALLBACK_PATH.replace("{connector_code}", "nnit"),
        params={"code": AUTH_CODE, "state": state},
        follow_redirects=False,
    )
    # 授权码没被污染 → 换令牌成功 → 建会话 → 302
    assert resp.status_code == 302, resp.text[:300]


# ═══════════════ M5 回调全流程 ═══════════════
def test_m5_callback_creates_session(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M5：`/feishu/aima/callback` 走通 → 建会话 → Set-Cookie 带安全属性。"""

    client, _ = _build_multi_client(pg_session_factory, group_ids=("aima-user-group",))
    state, _ = _state_from(client, MULTI_LOGIN_PATH.replace("{connector_code}", "aima"))

    resp = client.get(
        MULTI_CALLBACK_PATH.replace("{connector_code}", "aima"),
        params={"code": AUTH_CODE, "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    cookie = resp.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie.replace("samesite", "SameSite")

    # 会话可用：能取到身份
    me = client.get("/api/v1/principal")
    assert me.status_code == 200
    assert me.json()["source"] == "feishu"


# ═══════════════ M6 两家会话互不干扰 ═══════════════
def test_m6_sessions_from_two_enterprises_are_isolated(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M6：两家企业的登录各自建会话，且映射到**不同的** AIMA 身份。"""

    client, routes = _build_multi_client(pg_session_factory, group_ids=("nnit-user-group",))
    # 两家都登录一遍（同一个 Fake 用户 open_id，但企业不同）
    for code, group in (("nnit", "nnit-user-group"), ("aima", "aima-user-group")):
        routes._client = FakeFeishuClient(group_ids=(group,))  # type: ignore[assignment]
        state, _ = _state_from(client, MULTI_LOGIN_PATH.replace("{connector_code}", code))
        resp = client.get(
            MULTI_CALLBACK_PATH.replace("{connector_code}", code),
            params={"code": AUTH_CODE, "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302, f"{code} 回调失败：{resp.text[:200]}"

    # 库里有两条映射（同一 provider_subject，但 connector_id 不同）
    with pg_session_factory() as s:
        rows = (
            s.execute(
                select(identity_external_identities_table).where(
                    identity_external_identities_table.c.provider_subject == "on-fake-1"
                )
            )
            .mappings()
            .all()
        )
    connectors = {r["connector_id"] for r in rows}
    assert len(connectors) >= 2, f"两家企业应有不同 connector_id，实际 {connectors}"
    assert len({r["principal_id"] for r in rows}) >= 2, "两家企业应是不同 Principal"


# ═══════════════ M7 跨企业 state 被拒 ═══════════════
def test_m7_cross_enterprise_state_is_rejected(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M7：拿 **NNIT** 签发的 state 去打 **爱玛**的回调 → 被拒。

    这是纵深防御：即使配置写错，也不能让 A 的 state 在 B 的回调上生效。
    """

    client, _ = _build_multi_client(pg_session_factory, group_ids=("aima-user-group",))
    nnit_state, _ = _state_from(client, MULTI_LOGIN_PATH.replace("{connector_code}", "nnit"))

    resp = client.get(
        MULTI_CALLBACK_PATH.replace("{connector_code}", "aima"),
        params={"code": AUTH_CODE, "state": nnit_state},
        follow_redirects=False,
    )
    assert resp.status_code == 400, resp.text[:300]
    assert "feishu_state_invalid" in resp.text


# ═══════════════ M8 未知企业 → 404 ═══════════════
def test_m8_unknown_connector_returns_404(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M8：未知企业标识 → **404**（明确报错，不静默回退到别家）。"""

    client, _ = _build_multi_client(pg_session_factory)
    resp = client.get(MULTI_LOGIN_PATH.replace("{connector_code}", "ghost"), follow_redirects=False)
    assert resp.status_code == 404
    assert "unknown_connector" in resp.text


# ═══════════════ M9 企业列表端点 ═══════════════
def test_m9_connectors_endpoint_lists_two_enterprises(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M9：`/api/v1/auth/connectors` 返回两家，且**只含 code 与显示名**。"""

    client, _ = _build_multi_client(pg_session_factory)
    resp = client.get(CONNECTORS_PATH)
    assert resp.status_code == 200
    body = resp.json()
    codes = [i["code"] for i in body["items"]]
    assert codes == ["nnit", "aima"], codes
    assert body["items"][1]["display_name"] == "爱玛科技"
    # 反向断言：不得泄露配置细节
    raw = resp.text.lower()
    for forbidden in ("secret", "app_id", "group_id", "redirect_uri", "cli_"):
        assert forbidden not in raw, f"connectors 端点泄露了 {forbidden}"


# ═══════════════ M10 旧路由在多企业下仍可用 ═══════════════
def test_m10_legacy_route_still_works_in_multi_mode(
    pg_session_factory: sessionmaker[Session],
) -> None:
    """M10：多企业形态下，**旧路由**（不带企业标识）仍可用 —— 走默认那家。

    这是迁移期"已登记进飞书后台的旧回调地址不失效"的保证。
    """

    client, _ = _build_multi_client(pg_session_factory)
    resp = client.get(LOGIN_PATH, follow_redirects=False)
    assert resp.status_code == 302
    from urllib.parse import unquote

    location = unquote(resp.headers["location"])
    # 默认那家 = 配置里的第一家（nnit）
    assert f"client_id={NNIT['app_id']}" in location, location

    # 旧回调路径也能走通
    state, _ = _state_from(client, LOGIN_PATH)
    cb = client.get(
        CALLBACK_PATH, params={"code": AUTH_CODE, "state": state}, follow_redirects=False
    )
    assert cb.status_code in (302, 403), cb.text[:200]
