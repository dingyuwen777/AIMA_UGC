"""飞书登录统一数组配置、单应用与多应用及独立报告配置回归。"""

from __future__ import annotations

import json

import pytest
from aima_ugc.platform.config.settings import PlatformSettings, load_settings

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _base_env() -> dict[str, str]:
    """最小可加载的环境（路径类字段必填）。"""

    return {
        "AIMA_DATA_DIR": ".runtime/data",
        "AIMA_LOG_DIR": ".runtime/logs",
        "AIMA_SECRET_DIR": ".runtime/secrets",
    }


def _single_enterprise_env() -> dict[str, str]:
    """单应用就是仅含一个 Connector 的数组。"""
    return {
        **_base_env(),
        "AIMA_FEISHU_CONNECTORS": json.dumps(
            [_connector_dict("single", "cli_single", "secret_single")]
        ),
    }


def _connector_dict(code: str, app_id: str, secret_ref: str) -> dict[str, str]:
    """构造一条多企业配置项。"""

    return {
        "code": code,
        "display_name": f"{code} 企业",
        "app_id": app_id,
        "app_secret_ref": secret_ref,
        "admin_group_id": f"{code}-admin",
        "user_group_id": f"{code}-user",
        "redirect_uri": f"http://x/api/v1/auth/feishu/{code}/callback",
    }


def _multi_enterprise_env() -> dict[str, str]:
    """**改造后**的形态（两家企业）。"""

    payload = [
        _connector_dict("nnit", "cli_nnit", "secret_nnit"),
        _connector_dict("aima", "cli_aima", "secret_aima"),
    ]
    return {**_base_env(), "AIMA_FEISHU_CONNECTORS": json.dumps(payload, ensure_ascii=False)}


# ═══════════════════ 形态一：未配置（行为必须与接入前一致）═══════════════════
def test_no_feishu_config_keeps_development_identity() -> None:
    """什么都不配 → 沿用开发身份，且不报错。"""

    settings = load_settings(_base_env(), base_dir=None)
    assert settings.feishu_app_id is None
    assert settings.has_feishu_connectors is False
    assert settings.feishu_connectors is None


def test_single_enterprise_still_works() -> None:
    """单项数组直接启用正式 Connector 注册表。"""
    settings = load_settings(_single_enterprise_env())
    assert settings.has_feishu_connectors is True
    registry = settings.feishu_connectors
    assert registry is not None and len(registry) == 1
    assert settings.connector_for("single").app_id == "cli_single"


def test_report_secret_file_path_unchanged() -> None:
    """报告应用独立配置，不依赖登录数组。"""
    settings = load_settings({**_base_env(), "AIMA_FEISHU_APP_ID": "cli_report"})
    assert settings.feishu_app_secret_file.name == "feishu_app_secret"
    assert settings.has_feishu_connectors is False


def test_single_enterprise_half_config_still_rejected() -> None:
    """单项数组与多项数组遵循相同完整性校验。"""
    item = _connector_dict("single", "cli_single", "secret_single")
    del item["admin_group_id"]
    with pytest.raises(ValueError, match="admin_group_id"):
        load_settings({**_base_env(), "AIMA_FEISHU_CONNECTORS": json.dumps([item])})


# ═══════════════════ 形态三：多企业（新能力）═══════════════════
def test_multi_enterprise_parsed() -> None:
    """两家企业的配置能解析成注册表，顺序与配置一致。"""

    settings = load_settings(_multi_enterprise_env(), base_dir=None)
    assert settings.has_feishu_connectors is True
    registry = settings.feishu_connectors
    assert registry is not None
    assert registry.codes == ("nnit", "aima")
    assert len(registry) == 2


def test_multi_enterprise_connector_lookup() -> None:
    """能按 code 取到对应企业。"""

    settings = load_settings(_multi_enterprise_env(), base_dir=None)
    aima = settings.connector_for("aima")
    assert aima is not None
    assert aima.app_id == "cli_aima"
    assert settings.connector_for("unknown") is None


def test_multi_enterprise_isolated_connector_ids() -> None:
    """两家企业的 `connector_id` 必须不同（否则身份会串）。"""

    settings = load_settings(_multi_enterprise_env(), base_dir=None)
    registry = settings.feishu_connectors
    assert registry is not None
    ids = {c.connector_id for c in registry}
    assert len(ids) == 2


def test_multi_enterprise_chinese_display_name() -> None:
    """含中文的显示名要能正确解析（环境文件的编码风险点）。"""

    settings = load_settings(_multi_enterprise_env(), base_dir=None)
    aima = settings.connector_for("aima")
    assert aima is not None
    assert aima.display_name == "aima 企业"  # 构造时用的就是 ASCII 模板


def test_login_array_and_report_app_are_independent() -> None:
    """报告应用与登录数组分别生效，不相互覆盖。"""

    env = {**_multi_enterprise_env(), "AIMA_FEISHU_APP_ID": "cli_report"}
    settings = load_settings(env, base_dir=None)
    assert settings.has_feishu_connectors is True
    assert settings.connector_for("nnit") is not None


# ═══════════════════ 多企业配置的错误处理（启动即失败）═══════════════════
def test_blank_connectors_treated_as_unset() -> None:
    """`AIMA_FEISHU_CONNECTORS=`（留空）等价于没配 —— 与既有空值归一口径一致。"""

    env = {**_base_env(), "AIMA_FEISHU_CONNECTORS": ""}
    settings = load_settings(env, base_dir=None)
    assert settings.has_feishu_connectors is False


def test_whitespace_connectors_treated_as_unset() -> None:
    """只有空白也等价于没配。"""

    env = {**_base_env(), "AIMA_FEISHU_CONNECTORS": "   "}
    settings = load_settings(env, base_dir=None)
    assert settings.has_feishu_connectors is False


@pytest.mark.parametrize(
    "bad_value",
    [
        "not json",  # 不是 JSON
        '{"code":"x"}',  # 是对象不是数组
        "[]",  # 空数组
        '[{"code":"X"}]',  # 大写 code
        '[{"code":"a","app_id":"1"}]',  # 缺字段
    ],
)
def test_invalid_multi_enterprise_config_fails_at_load(bad_value: str) -> None:
    """非法多企业配置必须在**加载时**失败，且错误信息可定位。

    ⚠️ 这是"fail fast"的体现：配置错误属于部署错误，
    绝不允许拖到"用户点登录"才暴露。
    """

    env = {**_base_env(), "AIMA_FEISHU_CONNECTORS": bad_value}
    with pytest.raises(Exception) as exc:
        load_settings(env, base_dir=None)
    assert "AIMA_FEISHU_CONNECTORS" in str(exc.value)


def test_duplicate_app_id_across_connectors_fails_at_load() -> None:
    """跨企业的 app_id 重复（**身份串号**）必须在加载时拦住。"""

    payload = [
        _connector_dict("nnit", "cli_same", "secret_nnit"),
        _connector_dict("aima", "cli_same", "secret_aima"),
    ]
    env = {**_base_env(), "AIMA_FEISHU_CONNECTORS": json.dumps(payload)}
    with pytest.raises(Exception) as exc:
        load_settings(env, base_dir=None)
    assert "app_id" in str(exc.value)


def test_secret_ref_path_safety_enforced_for_each_connector() -> None:
    """每个企业的 Secret 引用都要过路径安全校验（防读到批准根之外）。"""

    payload = [_connector_dict("nnit", "cli_nnit", "../../etc/passwd")]
    env = {**_base_env(), "AIMA_FEISHU_CONNECTORS": json.dumps(payload)}
    with pytest.raises(Exception) as exc:
        load_settings(env, base_dir=None)
    assert "app_secret_ref" in str(exc.value)


# ═══════════════════ 属性与校验的分工 ═══════════════════
def test_invalid_json_rejected_at_construction() -> None:
    """非法 JSON 在**构造实例时**就被模型校验拦住（fail fast）。

    ⚠️ 这条测试记录了一个**实际行为**：字段归一与 `validate_feishu_configuration`
    都在 pydantic 模型校验阶段执行，所以"构造一个带非法 JSON 的实例"
    本身就抛 `ValidationError` —— **不可能构造出"带着坏 JSON 但还活着"的实例**。

    这正是想要的：配置错误在**配置加载时**暴露，而不是等到用户点登录。
    """

    with pytest.raises(Exception) as exc:
        PlatformSettings(
            data_dir=".",  # type: ignore[arg-type]
            log_dir=".",  # type: ignore[arg-type]
            secret_dir=".",  # type: ignore[arg-type]
            feishu_connectors_json="not-json",
        )
    assert "AIMA_FEISHU_CONNECTORS" in str(exc.value)


def test_connectors_property_returns_none_when_unset() -> None:
    """未配置多企业时属性返回 `None`（而非空注册表）—— 便于"未启用"判定。"""

    settings = load_settings(_base_env(), base_dir=None)
    assert settings.feishu_connectors is None
    assert settings.has_feishu_connectors is False

    assert settings.has_feishu_connectors is False
