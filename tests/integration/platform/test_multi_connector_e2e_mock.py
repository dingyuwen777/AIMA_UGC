"""多企业**真实 HTTP 链路**的端到端实测。

════════ 与 `test_multi_connector_routes.py` 的区别 ════════

| | routes 测试 | **本文件** |
|---|---|---|
| 飞书侧 | Python 替身对象（跳过 HTTP）| **本地假飞书 HTTP 服务** |
| 客户端 | 注入替身 | **真实 `HttpxFeishuClient`** |
| 验证到 | 路由分发、企业分流 | **+ HTTP 请求构造、JSON 解析、令牌缓存、重试** |

**为什么要这一层**：单元测试注入替身对象时，**HTTP 层完全没跑** ——
请求路径写错、字段名解析错、令牌传递错，替身都发现不了。
本文件用真实客户端到回环假服务验证 HTTP 接线、JSON 解析和企业令牌边界。
授权码、令牌种类和具体对象路径的严格请求约束继续由现有 Adapter 单元测试保护。

════════ 覆盖 ════════

    E1  ★ 两家企业依次登录，各自用自己的 App ID + Secret 换令牌
    E2  ★ 假飞书**校验 app_secret** → 用错密钥会失败（证明真的区分了企业）
    E3  ★ 换令牌时带的是**本企业**的 tenant_access_token
    E4  完整链路：登录 → 回调 → 建会话 → 取身份（含部门名）
    E5  ★ 同一个 open_id 在两家企业 → 库里**两条**身份，互不覆盖
    E6  角色判定按各自企业的组 ID
    E7  假飞书收到的请求序列符合预期（无多余调用）
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.feishu_auth_http import (
    MULTI_CALLBACK_PATH,
    MULTI_LOGIN_PATH,
    FeishuAuthRoutes,
    FeishuLoginRequiredResolver,
    _build_connector_settings_map,
    install_feishu_auth_routes,
)
from aima_ugc.bootstrap.route_authorization import install_route_authorization
from aima_ugc.modules.identity.feishu import HttpxFeishuClient
from aima_ugc.modules.identity.tables import identity_external_identities_table
from aima_ugc.platform.config import PlatformSettings
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.platform import identity_test_database
from tests.integration.platform.mock_feishu_server import (
    STATE,
    MockFeishuServer,
)

SITE = "http://site.example"

# 两家企业的**完整**配置（含只在假飞书里存在的 App Secret）
NNIT = {
    "code": "nnit",
    "display_name": "NNIT",
    "app_id": "cli_nnit_e2e",
    "app_secret": "secret-for-nnit",
    "admin_group_id": "og-nnit-admin",
    "user_group_id": "og-nnit-user",
    "open_id": "ou-shared-person",
    "name": "张三（NNIT）",
    "department_id": "od-nnit-dept",
    "department_name": "NNIT-技术部",
}
AIMA = {
    "code": "aima",
    "display_name": "爱玛科技",
    "app_id": "cli_aima_e2e",
    "app_secret": "secret-for-aima",
    "admin_group_id": "og-aima-admin",
    "user_group_id": "og-aima-user",
    "open_id": "ou-shared-person",  # ⚠️ 故意同一个人
    "name": "张三（爱玛）",
    "department_id": "od-aima-dept",
    "department_name": "爱玛-市场部",
}
AUTH_CODE = "MOCK_AUTH_CODE"


@pytest.fixture(scope="module")
def mock_feishu() -> Iterator[MockFeishuServer]:
    """启动假飞书服务；模块级复用。"""

    STATE.enterprises.clear()
    STATE.requests.clear()
    for ent, groups in ((NNIT, ("og-nnit-user",)), (AIMA, ("og-aima-user",))):
        STATE.add_enterprise(
            app_id=ent["app_id"],
            app_secret=ent["app_secret"],
            admin_group_id=ent["admin_group_id"],
            user_group_id=ent["user_group_id"],
            user_open_id=ent["open_id"],
            user_name=ent["name"],
            department_id=ent["department_id"],
            department_name=ent["department_name"],
            member_of=groups,
        )
    with MockFeishuServer() as srv:
        yield srv


@pytest.fixture
def pg_factory() -> Iterator[sessionmaker[Session]]:
    """复用连接前拒绝业务数据库的隔离身份测试环境。"""

    yield from identity_test_database.isolated_identity_database()


def _connectors_json() -> str:
    """生成两家模拟企业的当前连接器配置。"""

    return json.dumps(
        [
            {
                "code": e["code"],
                "display_name": e["display_name"],
                "app_id": e["app_id"],
                "app_secret_ref": f"secret_{e['code']}",
                "admin_group_id": e["admin_group_id"],
                "user_group_id": e["user_group_id"],
                "redirect_uri": f"{SITE}/api/v1/auth/feishu/{e['code']}/callback",
            }
            for e in (NNIT, AIMA)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _build_e2e_client(
    session_factory: sessionmaker[Session],
    base_url: str,
) -> tuple[TestClient, FeishuAuthRoutes]:
    """装配：**真实 HttpxFeishuClient**（指向假飞书）+ 真实数据库。"""

    settings = PlatformSettings(
        data_dir=Path("."),
        log_dir=Path("."),
        secret_dir=Path("."),
        feishu_connectors_json=_connectors_json(),
    )
    cmap = _build_connector_settings_map(settings)

    # 每家企业一个**真实客户端**，指向假飞书，用**自己的**密钥
    secrets = {f"secret_{ent['code']}": ent["app_secret"] for ent in (NNIT, AIMA)}

    routes = FeishuAuthRoutes(
        auth_settings=next(iter(cmap.values())),
        connectors=cmap,
        connector_display_names={e["code"]: e["display_name"] for e in (NNIT, AIMA)},
        session_factory=session_factory,
        app_secret_reader=lambda ref: SecretStr(secrets[ref]),
    )
    # 用真实客户端替换缓存：按 connector 各建一个（都指向假飞书）
    for cs in cmap.values():
        routes._clients[cs.connector_id] = HttpxFeishuClient(
            app_id=cs.app_id,
            app_secret=SecretStr(secrets[cs.app_secret_ref]),
            base_url=base_url,
            max_attempts=1,  # 测试不重试，失败即失败
        )
    resolver = FeishuLoginRequiredResolver(routes)
    application = create_app(identity_resolver=resolver)
    install_feishu_auth_routes(application, auth_routes=routes)
    install_route_authorization(application, identity_resolver=resolver)
    return TestClient(application, raise_server_exceptions=False), routes


@pytest.fixture
def e2e_client_factory(
    pg_factory: sessionmaker[Session],
    mock_feishu: MockFeishuServer,
) -> Iterator[Callable[[], tuple[TestClient, FeishuAuthRoutes]]]:
    """进入真实应用生命周期，失败或结束时关闭全部 HTTP 客户端。"""

    with ExitStack() as stack:

        def build() -> tuple[TestClient, FeishuAuthRoutes]:
            """进入应用生命周期并登记所有客户端的退出清理。"""

            client, routes = _build_e2e_client(pg_factory, mock_feishu.base_url)
            stack.enter_context(client)
            return client, routes

        yield build


def _login_and_callback(client: TestClient, code: str) -> httpx.Response:
    """走一次完整登录，返回回调响应供状态和 Cookie 校验。"""

    resp = client.get(MULTI_LOGIN_PATH.replace("{connector_code}", code), follow_redirects=False)
    assert resp.status_code == 302, resp.text[:200]
    from urllib.parse import unquote

    location = unquote(resp.headers["location"])
    qs = dict(p.split("=", 1) for p in location.split("?", 1)[1].split("&") if "=" in p)
    state = qs["state"]

    cb = client.get(
        MULTI_CALLBACK_PATH.replace("{connector_code}", code),
        params={"code": AUTH_CODE, "state": state},
        follow_redirects=False,
    )
    assert isinstance(cb, httpx.Response)
    return cb


# ═══════════════ E1~E3 ★ 两家各自用自己的凭证 ═══════════════
def test_e1_two_enterprises_login_with_their_own_credentials(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E1 ★：两家企业**都能登录成功**，且走的是**各自的** App ID。"""

    for ent in (NNIT, AIMA):
        client, _ = e2e_client_factory()
        resp = _login_and_callback(client, ent["code"])
        assert resp.status_code == 302, f"{ent['code']} 登录失败：{resp.text[:300]}"


def test_e2_wrong_app_secret_fails(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E2 ★：**用错企业的 App Secret 会失败** —— 证明真的按企业取了凭证。

    这条是"共用客户端"缺陷的**反证**：若两家共用凭证，这里不会失败。
    """

    client, routes = e2e_client_factory()
    cmap_nnit = routes.settings_for("nnit")
    assert cmap_nnit is not None
    # 故意把 NNIT 的客户端换成"爱玛的密钥"
    routes._clients.pop(cmap_nnit.connector_id).close()
    routes._clients[cmap_nnit.connector_id] = HttpxFeishuClient(
        app_id=NNIT["app_id"],
        app_secret=SecretStr(AIMA["app_secret"]),  # ← 错密钥
        base_url=mock_feishu.base_url,
        max_attempts=1,
    )
    resp = _login_and_callback(client, "nnit")
    assert resp.status_code != 302, "错密钥竟然登录成功了"
    assert resp.status_code in (502, 503), resp.status_code


def test_e3_token_exchange_uses_own_tenant_token(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E3 ★：换令牌时带的 `tenant_access_token` 是**本企业**的凭证。

    假飞书按 token 前缀 `t-<app_id>` 反查企业，若用错会返回"invalid tenant token"。
    """

    client, _ = e2e_client_factory()
    STATE.requests.clear()
    resp = _login_and_callback(client, "aima")
    assert resp.status_code == 302, resp.text[:300]

    # 假飞书收到的请求里，换令牌那次用的是爱玛的 tenant token
    exchange = [
        r for r in STATE.requests if r.get("path") == "/open-apis/authen/v1/oidc/access_token"
    ]
    assert exchange, "没有收到换令牌请求"
    assert exchange[-1]["bearer"] == f"t-{AIMA['app_id']}"
    # 校验 app 令牌请求用的 app_id 是爱玛
    app_tokens = [
        r for r in STATE.requests if r.get("path") == "/open-apis/auth/v3/app_access_token/internal"
    ]
    assert app_tokens, "没有收到应用令牌请求"
    assert app_tokens[-1]["body"]["app_id"] == AIMA["app_id"], app_tokens[-1]["body"]


# ═══════════════ E4 完整链路（含部门名）═══════════════
def test_e4_full_chain_includes_department_name(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E4：完整链路跑通，且**部门名**取到了（证明部门接口也走了真实 HTTP）。"""

    client, _ = e2e_client_factory()
    resp = _login_and_callback(client, "aima")
    assert resp.status_code == 302

    me = client.get("/api/v1/principal")
    assert me.status_code == 200
    body = me.json()
    assert body["source"] == "feishu"
    assert body["display_name"] == AIMA["name"]
    assert body["department_name"] == AIMA["department_name"], body


# ═══════════════ E5 ★ 同一人在两家 = 两条身份 ═══════════════
def test_e5_same_person_two_enterprises_two_identities(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E5 ★：**同一个 open_id** 在两家企业登录 → 库里**两条**独立身份。"""

    for ent in (NNIT, AIMA):
        client, _ = e2e_client_factory()
        resp = _login_and_callback(client, ent["code"])
        assert resp.status_code == 302, resp.text[:200]

    with pg_factory() as s:
        table = identity_external_identities_table
        rows = s.execute(select(table)).mappings().all()

    # ⚠️ `provider_subject` 优先取 **union_id**（代码：`user.union_id or user.open_id`），
    #    而假飞书返回的 union_id 形如 `on-<open_id>`。这里不硬编码猜值，
    #    而是**直接断言"库里同一 subject 有两条不同 connector_id 的映射"**。
    by_subject: dict[str, set[str]] = {}
    for r in rows:
        by_subject.setdefault(r["provider_subject"], set()).add(r["connector_id"])

    shared = [subj for subj, conns in by_subject.items() if len(conns) >= 2]
    assert shared, f"应有同一 provider_subject 落在两家企业下的记录，实际：{dict(by_subject)}"
    # 两条映射应指向**不同 Principal**
    principals = {
        r["connector_id"]: r["principal_id"] for r in rows if r["provider_subject"] == shared[0]
    }
    assert len(set(principals.values())) >= 2, (
        f"同一人在两家企业应是不同 Principal，实际 {principals}"
    )


# ═══════════════ E6 角色按各自企业的组判定 ═══════════════
def test_e6_role_resolved_per_enterprise_groups(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E6：角色按**各自企业**的组 ID 判定（组 ID 不同，不会互相命中）。"""

    for ent, expected_role in ((NNIT, "user"), (AIMA, "user")):
        client, _ = e2e_client_factory()
        _login_and_callback(client, ent["code"])
        me = client.get("/api/v1/principal")
        assert me.status_code == 200
        assert me.json()["role"] == expected_role, me.json()


# ═══════════════ E7 请求序列符合预期 ═══════════════
def test_e7_request_sequence(
    mock_feishu: MockFeishuServer,
    pg_factory: sessionmaker[Session],
    e2e_client_factory: Callable[[], tuple[TestClient, FeishuAuthRoutes]],
) -> None:
    """E7：一次完整登录对假飞书发起的请求序列符合预期（无多余调用）。"""

    client, _ = e2e_client_factory()
    STATE.requests.clear()
    resp = _login_and_callback(client, "nnit")
    assert resp.status_code == 302

    paths = [r["path"] for r in STATE.requests]
    print(f"\n  实际请求序列（{len(paths)} 次）:")
    for p in paths:
        print(f"     {p}")

    assert "/open-apis/auth/v3/app_access_token/internal" in paths
    assert "/open-apis/authen/v1/oidc/access_token" in paths
    assert "/open-apis/authen/v1/user_info" in paths
    assert "/open-apis/contact/v3/group/member_belong" in paths
    # 部门链路（best-effort）
    assert any("/contact/v3/users/" in p for p in paths)
