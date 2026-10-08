"""多企业**按企业区分飞书客户端**的防回归测试。

════════ 这个文件守住什么 ════════

**一个实测过的致命缺陷**（2026-09-21）：

    `_feishu_client()` 早期实现缓存**单个**客户端，并固定用
    `self._settings.app_id` —— 多企业形态下所有企业共用同一个客户端。

    实测证据：`settings_for("aima").app_id = cli_AIMA`，
    而 `_feishu_client().app_id = cli_NNIT`。

    **后果**：爱玛用户被用 NNIT 的 App ID + Secret 去换令牌 → 登录必然失败。
    这种错误**不会报"配置错"**，只会表现为"飞书说授权码无效"之类的误导性错误。

**本文件用两条断言把它钉死**：
    · 每家企业拿到**自己**的 App ID；
    · 两家拿到的是**不同实例**（证明真的按企业缓存）。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from aima_ugc.bootstrap.feishu_auth_http import (
    FeishuAuthRoutes,
    FeishuAuthSettings,
    _build_connector_settings_map,
)
from aima_ugc.platform.config.settings import PlatformSettings
from pydantic import SecretStr

SITE = "http://example.invalid"


def _settings() -> PlatformSettings:
    """两家企业的多企业配置。"""

    payload = [
        {
            "code": "nnit",
            "display_name": "NNIT",
            "app_id": "cli_NNIT",
            "app_secret_ref": "secret_nnit",
            "admin_group_id": "n-adm",
            "user_group_id": "n-usr",
            "redirect_uri": f"{SITE}/api/v1/auth/feishu/nnit/callback",
        },
        {
            "code": "aima",
            "display_name": "爱玛科技",
            "app_id": "cli_AIMA",
            "app_secret_ref": "secret_aima",
            "admin_group_id": "a-adm",
            "user_group_id": "a-usr",
            "redirect_uri": f"{SITE}/api/v1/auth/feishu/aima/callback",
        },
    ]
    return PlatformSettings(
        data_dir=Path("."),
        log_dir=Path("."),
        secret_dir=Path("."),
        feishu_connectors_json=json.dumps(payload, ensure_ascii=False),
    )


@pytest.fixture
def routes() -> Iterator[FeishuAuthRoutes]:
    """装配一个多企业的 `FeishuAuthRoutes`。

    ⚠️ 这里**注入一个假 reader**（而不是让它真去读 Secret 文件）——
    单元测试环境没有 Secret 文件，真读会 `FileNotFoundError`。
    注入 reader 不影响被测点：**"客户端是否按企业区分"** 取决于
    `app_id` 与 Secret **引用**的传递，与 Secret 内容无关。
    """

    cmap = _build_connector_settings_map(_settings())
    instance = FeishuAuthRoutes(
        auth_settings=next(iter(cmap.values())),
        connectors=cmap,
        app_secret_reader=_fake_secret,
    )
    try:
        yield instance
    finally:
        for client in instance._clients.values():
            client.close()


def _fake_secret(secret_ref: str) -> SecretStr:
    """按企业引用返回不同的测试密钥，未知引用直接失败。"""

    return SecretStr(
        {
            "secret_nnit": "FAKE_NNIT_SECRET",
            "secret_aima": "FAKE_AIMA_SECRET",
            "feishu_app_secret": "FAKE_SINGLE_SECRET",
        }[secret_ref]
    )


def _settings_for(routes: FeishuAuthRoutes, code: str) -> FeishuAuthSettings:
    """配置缺失时明确失败，避免把空值传给客户端构造入口。"""

    settings = routes.settings_for(code)
    assert settings is not None
    return settings


# ═══════════════ ① Secret 引用按企业传递 ═══════════════
def test_each_connector_carries_its_own_secret_ref() -> None:
    """`FeishuAuthSettings` 必须带**本企业**的 `app_secret_ref`。

    ⚠️ 缺了它，读 Secret 时只能回退到全局引用 → 所有企业读同一份密钥。
    """

    cmap = _build_connector_settings_map(_settings())
    assert cmap["nnit"].app_secret_ref == "secret_nnit"
    assert cmap["aima"].app_secret_ref == "secret_aima"


# ═══════════════ ② ★ 客户端按企业区分（核心防回归）═══════════════
def test_each_connector_gets_its_own_app_id(routes: FeishuAuthRoutes) -> None:
    """**每家企业必须拿到自己的 App ID**。

    这是那个致命缺陷的直接回归断言：早期实现会让 aima 拿到 `cli_NNIT`。
    """

    nnit_client = routes._feishu_client(_settings_for(routes, "nnit"))
    aima_client = routes._feishu_client(_settings_for(routes, "aima"))

    nnit_app_id = getattr(nnit_client, "_app_id", None) or getattr(nnit_client, "app_id", None)
    aima_app_id = getattr(aima_client, "_app_id", None) or getattr(aima_client, "app_id", None)

    assert nnit_app_id == "cli_NNIT", f"NNIT 拿到 {nnit_app_id}"
    assert aima_app_id == "cli_AIMA", f"爱玛拿到 {aima_app_id} —— 用错企业的 App ID"


def test_connector_clients_are_distinct_instances(routes: FeishuAuthRoutes) -> None:
    """两家企业拿到的是**不同实例** —— 证明真的按企业缓存，不是共用。"""

    nnit_client = routes._feishu_client(_settings_for(routes, "nnit"))
    aima_client = routes._feishu_client(_settings_for(routes, "aima"))
    assert nnit_client is not aima_client


def test_same_connector_reuses_its_client(routes: FeishuAuthRoutes) -> None:
    """同一企业重复取 → **复用**同一个实例（不每次新建，避免重复读 Secret）。"""

    first = routes._feishu_client(_settings_for(routes, "nnit"))
    second = routes._feishu_client(_settings_for(routes, "nnit"))
    assert first is second


# ═══════════════ ③ 注入优先（保证测试/替换可控）═══════════════
def test_injected_client_wins_over_config(routes: FeishuAuthRoutes) -> None:
    """注入的客户端**优先于**按配置新建 —— 且对多企业请求同样生效。

    ⚠️ 这条也是回归断言：早先的实现只在"不传 auth_settings"的分支里用注入值，
    多企业路径会绕过注入、真去连飞书（实测导致 13 个集成测试 401）。
    """

    sentinel = object()
    routes._client = sentinel  # type: ignore[assignment]

    assert routes._feishu_client(_settings_for(routes, "nnit")) is sentinel
    assert routes._feishu_client(_settings_for(routes, "aima")) is sentinel


# ═══════════════ ④ 单企业形态不受影响 ═══════════════
def test_single_enterprise_falls_back_to_default_settings() -> None:
    """单企业（未传 `connectors`）→ 走 `self._settings`，行为与改造前一致。"""

    from datetime import timedelta

    single = FeishuAuthSettings(
        app_id="cli_SINGLE",
        admin_group_id="adm",
        user_group_id="usr",
        redirect_uri=f"{SITE}/api/v1/auth/feishu/callback",
        session_ttl=timedelta(hours=1),
        state_ttl=timedelta(minutes=10),
    )
    r = FeishuAuthRoutes(auth_settings=single, app_secret_reader=_fake_secret)
    client = r._feishu_client(single)
    try:
        app_id = getattr(client, "_app_id", None) or getattr(client, "app_id", None)
        assert app_id == "cli_SINGLE"
    finally:
        client.close()
