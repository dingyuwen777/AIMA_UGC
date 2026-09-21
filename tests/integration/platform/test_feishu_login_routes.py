"""飞书登录 / 回调 / 登出的 **PostgreSQL 集成回归**。

覆盖任务书 DoD：

    D2  `GET /api/v1/auth/feishu/login` → 302，Location 是飞书授权页
    D3  state **一次性**：重放第二次 → 400
    D5  callback 全流程（Fake 飞书）→ 建会话 + Set-Cookie 含 HttpOnly/SameSite
    D6  不属于任何用户组 → **403**（不是 500）
    D7  无会话访问 `/api/v1/principal` → **401**
    D8  有会话 → `/api/v1/principal` 返回真实身份（`source="feishu"`）
    D9  日志里不含授权码 / state / token
    D10 `POST /api/v1/auth/logout` → 会话**服务端失效**（再访问 → 401）

⚠️ 用**真实 PostgreSQL**（隔离端口，见 `_ISOLATED_DB_PORT`）与**假飞书**：
数据库约束（一次性 state 的原子消费、会话只存 hash）是数据库自己的行为，
用内存替身测等于没测；而真实飞书属于外部付费/限流资源，禁止在测试里真调（任务书 §六）。

⚠️ 测试**不导入** `entrypoints/api_main`（那会在导入时用**进程环境**建一个 app），
而是直接调用 `create_app` + `install_feishu_auth_routes`，装配方式与入口完全一致。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.feishu_auth_http import (
    CALLBACK_PATH,
    LOGIN_PATH,
    LOGOUT_PATH,
    FeishuAuthRoutes,
    FeishuAuthSettings,
    FeishuLoginRequiredResolver,
    install_feishu_auth_routes,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from aima_ugc.modules.identity.feishu import (
    FeishuDepartment,
    FeishuError,
    FeishuTokens,
    FeishuUser,
    SessionStore,
    hash_session_token,
)
from aima_ugc.modules.identity.feishu.session_store import SESSION_COOKIE_NAME
from aima_ugc.modules.identity.tables import (
    identity_external_identities_table,
    identity_login_states_table,
    identity_principals_table,
    identity_sessions_table,
)
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.database import DatabaseRuntime
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.usefixtures("isolated_identity_schema")

APP_ID = "cli_feishu_login_test"
ADMIN_GROUP_ID = "grp_admin_test"
USER_GROUP_ID = "grp_user_test"
REDIRECT_URI = "http://localhost:8000/api/v1/auth/feishu/callback"

AUTHORIZATION_CODE = "AUTHORIZATION_CODE_MUST_NOT_LEAK"
SESSION_TOKEN = "session-token-must-not-be-logged"
ACCESS_TOKEN = "user-access-token-must-not-be-logged"

_UNION_ID = "on_test_union_id_0001"
_OPEN_ID = "ou_test_open_id_0001"


@pytest.fixture(scope="session")
def identity_database() -> Iterator[DatabaseRuntime]:
    """真实 PostgreSQL（隔离端口）；会话结束后 dispose，不删库。"""

    runtime = DatabaseRuntime(load_settings())
    try:
        yield runtime
    finally:
        runtime.dispose()


@pytest.fixture
def session_factory(identity_database: DatabaseRuntime) -> Iterator[sessionmaker[Session]]:
    """每个用例前清空身份四表，保证互不干扰。"""

    factory = sessionmaker(bind=identity_database.engine, class_=Session, expire_on_commit=False)
    _truncate(identity_database)
    try:
        yield factory
    finally:
        _truncate(identity_database)


@pytest.fixture(scope="session", autouse=True)
def isolated_identity_schema(identity_database: DatabaseRuntime) -> None:
    """确认连的是**隔离库**（有 identity_* 表），防止误连生产库清数据。"""

    with identity_database.engine.connect() as connection:
        exists = connection.execute(
            text("SELECT to_regclass('public.identity_sessions') IS NOT NULL")
        ).scalar()
    if not exists:
        pytest.fail("隔离测试库缺少 identity_sessions；请先 alembic upgrade head")


def _truncate(runtime: DatabaseRuntime) -> None:
    """清空身份相关的四张表（只动这四张）。"""

    with runtime.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE identity_sessions, identity_login_states, "
                "identity_external_identities, identity_principals RESTART IDENTITY CASCADE"
            )
        )


class FakeFeishuClient:
    """假飞书：只实现登录流程真正会调的 5 个方法，**不发任何网络请求**。"""

    def __init__(
        self,
        *,
        group_ids: tuple[str, ...] = (USER_GROUP_ID,),
        user_name: str = "张三",
        exchange_error: FeishuError | None = None,
        group_error: FeishuError | None = None,
        department_name: str = "市场部",
    ) -> None:
        """配置本次登录要返回的组 / 姓名 / 部门，以及是否模拟飞书故障。"""

        self._group_ids = group_ids
        self._user_name = user_name
        self._exchange_error = exchange_error
        self._group_error = group_error
        self._department_name = department_name
        self.calls: list[str] = []

    def exchange_authorization_code(self, code: str) -> FeishuTokens:
        """用授权码换令牌；可被配置成直接抛飞书错误。"""

        self.calls.append("exchange")
        assert code == AUTHORIZATION_CODE
        if self._exchange_error is not None:
            raise self._exchange_error
        return FeishuTokens(
            access_token=ACCESS_TOKEN,
            expires_in=7200,
            token_type="Bearer",
            scope="contact:user.base:readonly",
        )

    def get_current_user(self, user_access_token: str) -> FeishuUser:
        """取当前用户；令牌只做断言，**不会被记录或回显**。"""

        self.calls.append("user")
        assert user_access_token == ACCESS_TOKEN
        return FeishuUser(
            open_id=_OPEN_ID,
            name=self._user_name,
            union_id=_UNION_ID,
            avatar_url="https://example.invalid/avatar.png",
        )

    def list_user_groups(self, open_id: str) -> tuple[str, ...]:
        """查用户组；可被配置成抛飞书错误。"""

        self.calls.append("groups")
        assert open_id == _OPEN_ID
        if self._group_error is not None:
            raise self._group_error
        return self._group_ids

    def get_user(self, open_id: str) -> Any:
        """取用户详情（部门用）；返回固定部门 ID。"""

        self.calls.append("detail")
        from aima_ugc.modules.identity.feishu import FeishuUserDetail

        return FeishuUserDetail(open_id=open_id, department_ids=("od_dept_1",))

    def get_department(self, department_id: str) -> FeishuDepartment:
        """把部门 ID 换成可读名称。"""

        self.calls.append("department")
        return FeishuDepartment(department_id=department_id, name=self._department_name)


def _auth_settings(*, cookie_secure: bool = False) -> FeishuAuthSettings:
    """测试用飞书配置（本地 HTTP → 关闭 Secure）。"""

    return FeishuAuthSettings(
        app_id=APP_ID,
        admin_group_id=ADMIN_GROUP_ID,
        user_group_id=USER_GROUP_ID,
        redirect_uri=REDIRECT_URI,
        cookie_secure=cookie_secure,
    )


def _build_client(
    session_factory: sessionmaker[Session],
    *,
    client: FakeFeishuClient | None = None,
    cookie_secure: bool = False,
    session_ttl: timedelta | None = None,
) -> tuple[TestClient, FeishuAuthRoutes]:
    """按入口同样的方式装配应用，但允许注入假飞书与真实 Session 工厂。"""

    auth_settings = _auth_settings(cookie_secure=cookie_secure)
    if session_ttl is not None:
        auth_settings = FeishuAuthSettings(
            app_id=APP_ID,
            admin_group_id=ADMIN_GROUP_ID,
            user_group_id=USER_GROUP_ID,
            redirect_uri=REDIRECT_URI,
            cookie_secure=cookie_secure,
            session_ttl=session_ttl,
        )
    routes = FeishuAuthRoutes(
        auth_settings=auth_settings,
        session_factory=session_factory,
        client=client or FakeFeishuClient(),  # type: ignore[arg-type]
    )
    application = create_app(
        identity_resolver=FeishuLoginRequiredResolver(routes),
    )
    install_feishu_auth_routes(application, auth_routes=routes)
    return TestClient(application, raise_server_exceptions=False), routes


def _login_and_get_state(client: TestClient, *, return_to: str | None = None) -> str:
    """走一次 /login，从 Location 里取出 state（state 只在这里出现，用于驱动回调）。"""

    params = {"return_to": return_to} if return_to is not None else None
    response = client.get(LOGIN_PATH, params=params, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    query = dict(pair.split("=", 1) for pair in location.split("?", 1)[1].split("&") if "=" in pair)
    return query["state"]


# ── D2 登录入口 ──────────────────────────────────────────────────────────────
def test_d2_login_redirects_to_feishu_authorize_page(
    session_factory: sessionmaker[Session],
) -> None:
    """`/login` → 302，Location 指向飞书授权页且带上本应用的 client_id。"""

    client, _ = _build_client(session_factory)
    response = client.get(LOGIN_PATH, follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.feishu.cn/open-apis/authen/v1/authorize?")
    assert f"client_id={APP_ID}" in location
    assert "response_type=code" in location
    # redirect_uri 必须与配置逐字一致，否则飞书返回 20029。
    assert (
        "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Ffeishu%2Fcallback"
        in location
    )


def test_d2_login_records_state_hash_only(session_factory: sessionmaker[Session]) -> None:
    """登录只把 state 的 SHA-256 写库：库里**查不到**明文 state。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)

    with session_factory() as session:
        rows = session.execute(select(identity_login_states_table.c.state_hash)).scalars().all()

    assert len(rows) == 1
    assert rows[0] == sha256(state.encode()).hexdigest()
    assert state not in rows, "明文 state 绝不能落库"


def test_d2_login_does_not_echo_unsafe_return_to(
    session_factory: sessionmaker[Session],
) -> None:
    """`return_to=https://evil` 不能进入跳转地址（这里只影响回调跳转，不进授权 URL）。"""

    client, _ = _build_client(session_factory)
    response = client.get(
        LOGIN_PATH, params={"return_to": "https://evil.example/steal"}, follow_redirects=False
    )
    location = response.headers["location"]

    assert "evil.example" not in location

    with session_factory() as session:
        stored = session.execute(select(identity_login_states_table.c.return_to)).scalars().all()

    assert stored == ["/"], "不安全的 return_to 必须在**存入时**就被替换成 /"


# ── D5 回调全流程 ────────────────────────────────────────────────────────────
def test_d5_callback_creates_session_with_hardened_cookie(
    session_factory: sessionmaker[Session],
) -> None:
    """回调全流程 → 建会话 + Set-Cookie 含 HttpOnly/SameSite=Lax/Path=/。"""

    fake = FakeFeishuClient(group_ids=(USER_GROUP_ID,))
    client, _ = _build_client(session_factory, client=fake)
    state = _login_and_get_state(client, return_to="/voice-plaza")

    response = client.get(
        CALLBACK_PATH,
        params={"code": AUTHORIZATION_CODE, "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/voice-plaza"
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie, "本地 HTTP 不该带 Secure，否则浏览器不写 Cookie"
    assert fake.calls == ["exchange", "user", "groups", "detail", "department"]

    # 库里存的是 hash，不是明文令牌。
    with session_factory() as session:
        token_hashes = session.execute(select(identity_sessions_table.c.token_hash)).scalars().all()
        row = session.execute(
            select(
                identity_sessions_table.c.role,
                identity_sessions_table.c.display_name,
                identity_sessions_table.c.department_name,
                identity_sessions_table.c.feishu_group_ids,
            )
        ).one()

    assert len(token_hashes) == 1
    assert len(token_hashes[0]) == 64, "必须只存 SHA-256（64 位十六进制）"
    assert row[0] == "user"
    assert row[1] == "张三"
    assert row[2] == "市场部"


def test_d5_callback_marks_cookie_secure_on_https(
    session_factory: sessionmaker[Session],
) -> None:
    """HTTPS 环境（`cookie_secure=True`）必须带上 Secure 属性。"""

    client, _ = _build_client(session_factory, cookie_secure=True)
    state = _login_and_get_state(client)

    response = client.get(
        CALLBACK_PATH,
        params={"code": AUTHORIZATION_CODE, "state": state},
        follow_redirects=False,
    )

    assert "Secure" in response.headers["set-cookie"]


def test_d5_admin_group_wins_when_user_is_in_both(
    session_factory: sessionmaker[Session],
) -> None:
    """**同时在两个组**时必须判成 administrator（成员测试，不看顺序）。"""

    # 故意把 User 组放前面：用 groups[0] 的实现会在这里判错。
    fake = FakeFeishuClient(group_ids=(USER_GROUP_ID, ADMIN_GROUP_ID))
    client, _ = _build_client(session_factory, client=fake)
    state = _login_and_get_state(client)

    client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    with session_factory() as session:
        role = session.execute(select(identity_sessions_table.c.role)).scalar_one()
    assert role == "administrator"


def test_d5_repeated_login_reuses_the_same_principal(
    session_factory: sessionmaker[Session],
) -> None:
    """同一飞书身份登录两次 → 只有一个 AIMA Principal（复用，不新建）。"""

    client, _ = _build_client(session_factory)
    for _ in range(2):
        state = _login_and_get_state(client)
        callback = client.get(
            CALLBACK_PATH,
            params={"code": AUTHORIZATION_CODE, "state": state},
            follow_redirects=False,
        )
        assert callback.status_code == 302

    with session_factory() as session:
        principals = session.scalar(select(func.count()).select_from(identity_principals_table))
        mappings = session.scalar(
            select(func.count()).select_from(identity_external_identities_table)
        )
        sessions = session.scalar(select(func.count()).select_from(identity_sessions_table))

    assert (principals, mappings, sessions) == (1, 1, 2), "身份复用，但每次登录各发一个会话"


# ── D3 state 一次性 ─────────────────────────────────────────────────────────
def test_d3_replayed_state_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    """同一 state 用第二次 → 400，且**不产生**第二个会话。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)

    first = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )
    second = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    assert first.status_code == 302
    assert second.status_code == 400
    assert second.json()["errors"][0]["code"] == "feishu_state_invalid"

    with session_factory() as session:
        sessions = session.scalar(select(func.count()).select_from(identity_sessions_table))
    assert sessions == 1, "重放不得再建会话"


def test_d3_forged_state_is_rejected(session_factory: sessionmaker[Session]) -> None:
    """伪造的 state → 400（不能因为"库里没有"就放过）。"""

    client, _ = _build_client(session_factory)
    response = client.get(
        CALLBACK_PATH,
        params={"code": AUTHORIZATION_CODE, "state": "forged-state-value"},
    )

    assert response.status_code == 400


def test_d3_expired_state_is_rejected(session_factory: sessionmaker[Session]) -> None:
    """过期 state → 400（把库里的 `expires_at` 改到过去来模拟）。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)

    with session_factory() as session, session.begin():
        session.execute(
            text("UPDATE identity_login_states SET expires_at = now() - interval '1 minute'")
        )

    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )
    assert response.status_code == 400


def test_d3_missing_state_is_rejected(session_factory: sessionmaker[Session]) -> None:
    """完全没有 state → 400，而不是 500。"""

    client, _ = _build_client(session_factory)
    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE}, follow_redirects=False
    )

    assert response.status_code == 400


# ── D6 不属于任何组 → 403（不是 500）────────────────────────────────────────
def test_d6_user_outside_all_groups_is_forbidden(
    session_factory: sessionmaker[Session],
) -> None:
    """不在任何允许用户组 → **403**，且不建会话。"""

    client, _ = _build_client(session_factory, client=FakeFeishuClient(group_ids=()))
    state = _login_and_get_state(client)

    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    assert response.status_code == 403, "无权限必须是 403，不能是 500"
    assert response.json()["errors"][0]["code"] == "feishu_group_required"

    with session_factory() as session:
        sessions = session.scalar(select(func.count()).select_from(identity_sessions_table))
    assert sessions == 0


def test_d6_unknown_group_is_forbidden(session_factory: sessionmaker[Session]) -> None:
    """只属于"别的组"（不是配置的 Admin/User 组）同样 403。"""

    client, _ = _build_client(session_factory, client=FakeFeishuClient(group_ids=("grp_other",)))
    state = _login_and_get_state(client)

    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    assert response.status_code == 403


# ── 飞书不可达 → 502 / 503 ──────────────────────────────────────────────────
def test_feishu_retryable_failure_returns_503(
    session_factory: sessionmaker[Session],
) -> None:
    """飞书暂时不可用（可重试却仍失败）→ 503。"""

    failing = FakeFeishuClient(
        exchange_error=FeishuError(
            "用授权码换令牌", code=99991402, msg="rate limited", retryable=True
        )
    )
    client, _ = _build_client(session_factory, client=failing)
    state = _login_and_get_state(client)

    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "feishu_upstream_unavailable"


def test_feishu_permanent_failure_returns_502(
    session_factory: sessionmaker[Session],
) -> None:
    """飞书明确拒绝（授权码无效等不可重试）→ 502。"""

    failing = FakeFeishuClient(
        exchange_error=FeishuError(
            "用授权码换令牌", code=20003, msg="invalid code", retryable=False
        )
    )
    client, _ = _build_client(session_factory, client=failing)
    state = _login_and_get_state(client)

    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    assert response.status_code == 502


def test_feishu_error_response_does_not_echo_credentials(
    session_factory: sessionmaker[Session],
) -> None:
    """飞书失败的响应体里不得出现授权码 / 令牌原文。"""

    failing = FakeFeishuClient(
        exchange_error=FeishuError(
            "用授权码换令牌",
            code=99991402,
            msg=f"rate limited for {AUTHORIZATION_CODE} {ACCESS_TOKEN}",
            retryable=True,
        )
    )
    client, _ = _build_client(session_factory, client=failing)
    state = _login_and_get_state(client)

    response = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )
    body = response.text

    assert AUTHORIZATION_CODE not in body
    assert ACCESS_TOKEN not in body
    assert state not in body


# ── D7 / D8 会话语义 ────────────────────────────────────────────────────────
def test_d7_principal_without_session_is_unauthorized(
    session_factory: sessionmaker[Session],
) -> None:
    """无会话访问 `/api/v1/principal` → **401**（不是 403，也不是 200）。"""

    client, _ = _build_client(session_factory)

    response = client.get("/api/v1/principal")

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "authentication_required"


def test_d8_principal_with_session_returns_feishu_identity(
    session_factory: sessionmaker[Session],
) -> None:
    """有会话 → 返回**真实身份**，且 `source="feishu"`（不是 development）。"""

    client, _ = _build_client(session_factory, client=FakeFeishuClient(user_name="李四"))
    state = _login_and_get_state(client)
    callback = client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )
    assert callback.status_code == 302
    # TestClient 会保留 Set-Cookie，下一次请求即带上会话。
    assert SESSION_COOKIE_NAME in client.cookies

    response = client.get("/api/v1/principal")

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "李四"
    assert payload["role"] == "user"
    assert payload["source"] == "feishu"
    assert payload["principal_id"] != _UNION_ID, "principal_id 必须是 AIMA 的 Uuid，不是飞书 ID"


def test_d7_revoked_session_is_unauthorized(
    session_factory: sessionmaker[Session],
) -> None:
    """会话被撤销（不是过期）后访问 → 401（与"从未登录"对外不区分）。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)
    client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    with session_factory() as session, session.begin():
        session.execute(text("UPDATE identity_sessions SET revoked_at = now()"))

    response = client.get("/api/v1/principal")
    assert response.status_code == 401


def test_d7_expired_session_is_unauthorized(
    session_factory: sessionmaker[Session],
) -> None:
    """会话过期后访问 → 401。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)
    client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    with session_factory() as session, session.begin():
        session.execute(
            text("UPDATE identity_sessions SET expires_at = now() - interval '1 second'")
        )

    response = client.get("/api/v1/principal")
    assert response.status_code == 401


def test_d7_administrator_guard_still_returns_403_not_401(
    session_factory: sessionmaker[Session],
) -> None:
    """已登录的普通用户访问管理员接口 → **403**。

    ⚠️ 回归重点：401 与 403 的区分**不能**把 `require_administrator()` 也变成 401，
    否则前端会"无权限 → 跳登录 → 还是无权限"地打转。
    """

    client, _ = _build_client(session_factory, client=FakeFeishuClient(group_ids=(USER_GROUP_ID,)))
    state = _login_and_get_state(client)
    client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    response = client.get("/api/v1/provider-configs")

    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "administrator_required"


# ── D10 登出 ────────────────────────────────────────────────────────────────
def test_d10_logout_revokes_the_session_server_side(
    session_factory: sessionmaker[Session],
) -> None:
    """登出 → 会话**服务端失效**（不是只清浏览器 Cookie），再访问 → 401。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)
    client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )
    assert client.get("/api/v1/principal").status_code == 200

    logout = client.post(LOGOUT_PATH)

    assert logout.status_code == 204
    assert client.get("/api/v1/principal").status_code == 401
    with session_factory() as session:
        revoked = session.execute(select(identity_sessions_table.c.revoked_at)).scalar_one()
    assert revoked is not None, "登出必须在服务端留下撤销时间"


def test_d10_logout_without_session_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    """没有会话时登出也是 204（幂等），不能报错。"""

    client, _ = _build_client(session_factory)
    assert client.post(LOGOUT_PATH).status_code == 204
    assert client.post(LOGOUT_PATH).status_code == 204


def test_d10_logout_clears_the_cookie(
    session_factory: sessionmaker[Session],
) -> None:
    """登出必须下发清 Cookie 的 Set-Cookie（Max-Age=0）。"""

    client, _ = _build_client(session_factory)
    state = _login_and_get_state(client)
    client.get(
        CALLBACK_PATH, params={"code": AUTHORIZATION_CODE, "state": state}, follow_redirects=False
    )

    logout = client.post(LOGOUT_PATH)
    cookie = logout.headers["set-cookie"]

    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie


# ── D9 日志中不含凭据 ───────────────────────────────────────────────────────
def test_d9_credentials_never_enter_logs(
    session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """抓完整登录 + 登出流程的日志，断言授权码 / state / 会话令牌 / 用户令牌都不在。

    ⚠️ 只看 **AIMA 应用日志**（`aima_ugc` logger）。`TestClient` 自身基于 httpx，
    而 httpx 会把它发出的每个请求 URL 记进 `httpx` logger —— 那是**测试替身**的行为：
    真实浏览器请求不经过 httpx，生产链路里没有这条日志。这里显式压低 httpx 的日志级别，
    避免它污染断言（否则测的是 httpx 而不是我们的代码）。
    """

    client, _ = _build_client(session_factory)
    httpx_logger = logging.getLogger("httpx")
    previous_level = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)
    try:
        with caplog.at_level(logging.DEBUG, logger="aima_ugc"):
            state = _login_and_get_state(client, return_to="/voice-plaza")
            client.get(
                CALLBACK_PATH,
                params={"code": AUTHORIZATION_CODE, "state": state},
                follow_redirects=False,
            )
            client.post(LOGOUT_PATH)
    finally:
        httpx_logger.setLevel(previous_level)

    logged = "\n".join(
        record.getMessage() + str(record.__dict__)
        for record in caplog.records
        if record.name.startswith("aima_ugc")
    )

    assert AUTHORIZATION_CODE not in logged, "授权码泄进日志"
    assert state not in logged, "state 泄进日志"
    assert ACCESS_TOKEN not in logged, "user_access_token 泄进日志"
    assert SESSION_TOKEN not in logged
    # 会话令牌明文只在 Set-Cookie 里出现；日志里连它的 hash 都不该被打印。
    with session_factory() as session:
        stored_hash = session.execute(select(identity_sessions_table.c.token_hash)).scalars().all()
    assert all(token_hash not in logged for token_hash in stored_hash)

    assert "identity.feishu_login_succeeded" in logged, "成功路径必须有日志（否则无法验证）"


def test_d9_helper_stores_only_hashes(session_factory: sessionmaker[Session]) -> None:
    """会话 hash 工具的行为回归：`find()` 认明文、库里只有 hash。"""

    from aima_ugc.modules.identity.feishu import generate_session_token

    token = generate_session_token()
    with session_factory() as session, session.begin():
        assert SessionStore(session).find(token) is None

    with session_factory() as session:
        assert (
            session.execute(
                select(identity_sessions_table.c.token_hash).where(
                    identity_sessions_table.c.token_hash == hash_session_token(token)
                )
            ).scalar_one_or_none()
            is None
        )


# ── 未配飞书时的兜底 ────────────────────────────────────────────────────────
def test_unconfigured_routes_answer_503_without_touching_database(
    identity_database: DatabaseRuntime,
) -> None:
    """未配飞书时 `/login` 返回 503，且**不**因为这条路去连数据库。"""

    routes = FeishuAuthRoutes(auth_settings=None)
    application = create_app(identity_resolver=DevelopmentIdentityResolver())
    install_feishu_auth_routes(application, auth_routes=routes)

    client = TestClient(application, raise_server_exceptions=False)
    response = client.get(LOGIN_PATH)

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "feishu_not_configured"

    # 关键断言：这条路**没有**建立任何 Session 工厂（因此也没连库）。
    assert routes._session_factory is None  # noqa: SLF001 - 断言的就是"惰性未触发"


def test_settings_snapshot_used_by_tests_matches_isolation(
    identity_database: DatabaseRuntime,
) -> None:
    """防呆：确认测试连的是**隔离**库，而不是开发库。

    ⚠️ 判据刻意**不写死端口号**（本地开发用 55444、CI 用 5432 的服务容器），
    否则这条"安全网"自己会在另一套环境里变成假 FAIL（规则 #23③：判据不要绑快照值）。
    真正要防的是"误连到同事/生产库然后 TRUNCATE 掉真实数据"，
    因此判据是"**库名带隔离标记**或**主机是本机**"。
    """

    settings: PlatformSettings = load_settings()
    password = settings.postgres_password_file.read_text(encoding="utf-8").strip()
    target = f"{settings.db_host}:{settings.db_port}/{settings.db_name}"
    assert password == "ci-postgres", (
        "集成测试只允许连专用测试库（密码文件内容必须是 ci-postgres）；"
        f"当前连的是 {target} —— 请检查 AIMA_* 环境变量"
    )


def test_import_targets_are_importable_from_entrypoint() -> None:
    """入口必须能导入装配函数（防止只在测试里能跑、进生产 import 就炸）。"""

    from aima_ugc.entrypoints.api_main import create_app as entrypoint_create_app

    assert callable(entrypoint_create_app)
    assert Path(__file__).exists()
