"""Connector 配置对象与注册表的单元测试。

════════ 这些测试守住什么 ════════

本文件的核心不是"覆盖率"，而是**把每一个静默出错的场景变成会失败的断言**：

| 测试组 | 守住的静默故障 |
|---|---|
| `connector_id` 派生不变性 | 改了算法 → 已有身份映射全部失联（**老用户变新用户**）|
| code 校验 | 非法标识进 URL → 路径穿越 / 路由混淆 |
| 重复检测（code / app_id / secret_ref）| 企业静默失效、**身份串号（安全）**、用错密钥 |
| redirect_uri 与 code 一致性 | 回调走错企业 |
| 两个组相同 | 角色判定退化为"在组里即管理员" |

**⚠️ `connector_id` 那条是回归防线**：库里有真实数据依赖它，
所以断言写的是**生产环境实际存在的值**，不是随便编的 UUID。
"""

from __future__ import annotations

import pytest
from aima_ugc.platform.identity.connector import (
    CONNECTOR_CODE_PATTERN,
    MAX_CONNECTOR_CODE_LENGTH,
    ConnectorConfigurationError,
    FeishuConnector,
    build_registry,
    parse_connector,
)


def _connector(**overrides: object) -> FeishuConnector:
    """构造一个合法 Connector，测试按需覆盖个别字段。"""

    base: dict[str, object] = {
        "code": "nnit",
        "display_name": "NNIT",
        "app_id": "cli_aa2092574af9dbc2",
        "app_secret_ref": "feishu_app_secret",
        "admin_group_id": "65aad3687f68ba7b",
        "user_group_id": "b9fc8b542d694d2e",
        "redirect_uri": "http://example.test/api/v1/auth/feishu/nnit/callback",
    }
    base.update(overrides)
    return FeishuConnector(**base)  # type: ignore[arg-type]


def _raw(**overrides: object) -> dict[str, object]:
    """构造一条合法的原始配置（JSON 里的形态）。"""

    return {
        "code": "nnit",
        "display_name": "NNIT",
        "app_id": "cli_aa2092574af9dbc2",
        "app_secret_ref": "feishu_app_secret",
        "admin_group_id": "65aad3687f68ba7b",
        "user_group_id": "b9fc8b542d694d2e",
        "redirect_uri": "http://example.test/api/v1/auth/feishu/nnit/callback",
        **overrides,
    }


# ═══════════════════════ ① connector_id 派生不变性（★ 兼容性命门）═══════════════════════
def test_connector_id_matches_existing_production_value() -> None:
    """**回归防线**：生产库里的真实值必须能被当前算法重新派生出来。

    ⚠️ 这个断言用的是**实际存在于数据库里的值**（3 条身份映射都指向它）。
    若本测试失败，说明派生算法被改动了 —— 那会让所有老用户与新身份对不上，
    **属于必须阻止的兼容性事故**，不是"改个测试就行"的小事。
    """

    connector = _connector(app_id="cli_aa2092574af9dbc2")
    assert connector.connector_id == "7d88a4816c7a5e07a95ca3c2012fb2f7"


def test_connector_id_is_deterministic() -> None:
    """同一 app_id 反复派生必须得到同一个值（否则映射表失去意义）。"""

    assert _connector().connector_id == _connector().connector_id


def test_connector_id_differs_between_apps() -> None:
    """不同 app_id 必须派生出不同值 —— 这是多企业隔离的基础。"""

    nnit = _connector(code="nnit", app_id="cli_nnit")
    aima = _connector(
        code="aima",
        app_id="cli_aima",
        redirect_uri="http://example.test/api/v1/auth/feishu/aima/callback",
    )
    assert nnit.connector_id != aima.connector_id


# ═══════════════════════ ② code 校验 ═══════════════════════
@pytest.mark.parametrize(
    "code",
    ["aima", "nnit", "partner-b", "a1", "x" * MAX_CONNECTOR_CODE_LENGTH],
)
def test_valid_codes_accepted(code: str) -> None:
    """合法标识：小写字母/数字/连字符，字母或数字开头。"""

    assert parse_connector(_raw(code=code), index=0).code == code


@pytest.mark.parametrize(
    "code",
    [
        "AIMA",  # 大写：URL 里大小写敏感，易混
        "-aima",  # 连字符开头
        "aima/evil",  # 🔴 路径分隔符 —— 路径穿越风险
        "aima.evil",  # 点：可能与路由后缀混淆
        "aima evil",  # 空格
        "aima%2f",  # 编码字符
        "",  # 空（另有 require_str 拦住）
        "x" * (MAX_CONNECTOR_CODE_LENGTH + 1),  # 超长
    ],
)
def test_invalid_codes_rejected(code: str) -> None:
    """非法标识必须被拒 —— 它们会直接进 URL 路径。"""

    with pytest.raises(ConnectorConfigurationError):
        parse_connector(_raw(code=code), index=0)


def test_code_pattern_anchored() -> None:
    """正则必须整体锚定，不能是"包含即通过"。"""

    assert CONNECTOR_CODE_PATTERN.match("aima")
    assert not CONNECTOR_CODE_PATTERN.match("aima/evil")


# ═══════════════════════ ③ 单条配置解析 ═══════════════════════
@pytest.mark.parametrize(
    "field",
    [
        "code",
        "display_name",
        "app_id",
        "app_secret_ref",
        "admin_group_id",
        "user_group_id",
        "redirect_uri",
    ],
)
def test_missing_required_field_rejected(field: str) -> None:
    """每个必填字段缺失都要报错，且错误信息里能看出是第几条、哪个字段。"""

    raw = _raw()
    del raw[field]
    with pytest.raises(ConnectorConfigurationError) as exc:
        parse_connector(raw, index=2)
    assert field in str(exc.value)
    assert "第 3 个" in str(exc.value)  # index=2 → 人类可读的"第 3 个"


def test_non_dict_entry_rejected() -> None:
    """列表里混进非对象要报错（JSON 写错时的常见形态）。"""

    with pytest.raises(ConnectorConfigurationError):
        parse_connector("not-an-object", index=0)  # type: ignore[arg-type]


def test_blank_string_field_rejected() -> None:
    """空白字符串等价于缺失（Compose 里留空变量的常见形态）。"""

    with pytest.raises(ConnectorConfigurationError):
        parse_connector(_raw(app_id="   "), index=0)


def test_whitespace_trimmed() -> None:
    """首尾空白要归一，避免"看起来一样但比较不相等"的隐患。"""

    assert parse_connector(_raw(code="  nnit  "), index=0).code == "nnit"


# ═══════════════════════ ④ 注册表：跨条目校验 ═══════════════════════
def test_single_connector_registry() -> None:
    """单企业注册表：`single` 返回它（前端据此不显示选择列表）。"""

    registry = build_registry([_connector()])
    assert len(registry) == 1
    assert registry.single is not None
    assert registry.single.code == "nnit"
    assert registry.codes == ("nnit",)


def test_multi_connector_registry_has_no_single() -> None:
    """多企业时 `single` 为 `None`（前端要显示选择列表）。"""

    registry = build_registry(
        [
            _connector(),
            _connector(
                code="aima",
                display_name="爱玛科技",
                app_id="cli_aima",
                app_secret_ref="feishu_aima_secret",
                redirect_uri="http://example.test/api/v1/auth/feishu/aima/callback",
            ),
        ]
    )
    assert len(registry) == 2
    assert registry.single is None


def test_registry_preserves_configuration_order() -> None:
    """顺序必须等于配置顺序 —— 前端按钮顺序依赖它，不能随机。"""

    registry = build_registry(
        [
            _connector(
                code="aima",
                app_id="cli_a",
                app_secret_ref="secret_a",
                admin_group_id="admin_a",
                user_group_id="user_a",
                redirect_uri="http://x/feishu/aima/callback",
            ),
            _connector(
                code="nnit",
                app_id="cli_n",
                app_secret_ref="secret_n",
                admin_group_id="admin_n",
                user_group_id="user_n",
                redirect_uri="http://x/feishu/nnit/callback",
            ),
        ]
    )
    assert registry.codes == ("aima", "nnit")
    assert [c.code for c in registry] == ["aima", "nnit"]


def test_registry_lookup_by_code() -> None:
    """按 code 查找命中；未知 code 返回 None（由调用方决定 404 还是回退）。"""

    registry = build_registry([_connector()])
    assert registry.get("nnit") is not None
    assert registry.get("unknown") is None


def test_empty_registry_rejected() -> None:
    """空列表必须拒绝：那会让**所有人**（含管理员）都登不进来。"""

    with pytest.raises(ConnectorConfigurationError) as exc:
        build_registry([])
    assert "空列表" in str(exc.value)


def test_duplicate_code_rejected() -> None:
    """code 重复 → 后一条覆盖前一条 → 某家企业静默失效。"""

    with pytest.raises(ConnectorConfigurationError) as exc:
        build_registry([_connector(), _connector(app_id="cli_other")])
    assert "重复" in str(exc.value)


def test_duplicate_app_id_rejected() -> None:
    """🔴 **安全关键**：app_id 重复 → connector_id 相同 → 两家企业身份互相覆盖。"""

    with pytest.raises(ConnectorConfigurationError) as exc:
        build_registry(
            [
                _connector(),
                _connector(
                    code="aima",
                    app_secret_ref="feishu_aima_secret",
                    redirect_uri="http://x/feishu/aima/callback",
                ),
            ]
        )
    assert "同一个 `app_id`" in str(exc.value)


def test_duplicate_secret_ref_rejected() -> None:
    """secret_ref 重复 → 用 A 的密钥换 B 的令牌 → 登录失败且难定位。"""

    with pytest.raises(ConnectorConfigurationError) as exc:
        build_registry(
            [
                _connector(),
                _connector(
                    code="aima",
                    app_id="cli_aima",
                    redirect_uri="http://x/feishu/aima/callback",
                ),
            ]
        )
    assert "同一个 `app_secret_ref`" in str(exc.value)


def test_redirect_uri_must_contain_own_code() -> None:
    """回调地址必须含本企业 code —— 否则回调走错企业。"""

    with pytest.raises(ConnectorConfigurationError) as exc:
        build_registry([_connector(code="aima", redirect_uri="http://x/feishu/nnit/callback")])
    assert "/feishu/aima/callback" in str(exc.value)


def test_admin_and_user_group_must_differ() -> None:
    """管理员组与用户组相同 → 角色判定退化为"在组里即管理员"。"""

    with pytest.raises(ConnectorConfigurationError) as exc:
        build_registry([_connector(user_group_id="65aad3687f68ba7b")])
    assert "退化为" in str(exc.value)


def test_valid_multi_connector_registry() -> None:
    """两个合法 connector 能共存（本次改造的核心目标）。"""

    registry = build_registry(
        [
            _connector(),
            _connector(
                code="aima",
                display_name="爱玛科技",
                app_id="cli_aima",
                app_secret_ref="feishu_aima_secret",
                admin_group_id="aima-admin-group",
                user_group_id="aima-user-group",
                redirect_uri="http://example.test/api/v1/auth/feishu/aima/callback",
            ),
        ]
    )
    assert len(registry) == 2
    assert registry.get("aima").display_name == "爱玛科技"  # type: ignore[union-attr]
    # 两家企业的 connector_id 必须不同（身份才能隔离）
    nnit, aima = registry.connectors
    assert nnit.connector_id != aima.connector_id
