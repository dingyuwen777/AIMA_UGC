"""登录配置只有 Connector 数组，报告应用不能成为开发身份回退的歧义。"""

import json

import pytest
from aima_ugc.bootstrap.feishu_auth_http import FeishuLoginRequiredResolver, build_feishu_identity
from aima_ugc.modules.identity import DevelopmentIdentityResolver
from aima_ugc.platform.config.settings import load_settings


@pytest.mark.parametrize(
    "field",
    ["AIMA_FEISHU_ADMIN_GROUP_ID", "AIMA_FEISHU_USER_GROUP_ID", "AIMA_FEISHU_REDIRECT_URI"],
)
def test_removed_flat_login_configuration_is_rejected(field: str) -> None:
    """旧登录输入显式失败，不能静默忽略后启用开发管理员。"""
    with pytest.raises(ValueError, match="AIMA_FEISHU_CONNECTORS"):
        load_settings({field: "obsolete-value"})


def test_one_connector_is_a_complete_single_app_login() -> None:
    """一个数组元素完成正式登录装配，无需额外单应用字段。"""
    connector = {
        "code": "single",
        "display_name": "单应用",
        "app_id": "cli_single",
        "app_secret_ref": "single_secret",
        "admin_group_id": "admin",
        "user_group_id": "user",
        "redirect_uri": "http://127.0.0.1:5173/api/v1/auth/feishu/single/callback",
    }
    settings = load_settings(
        {"AIMA_IDENTITY_MODE": "feishu", "AIMA_FEISHU_CONNECTORS": json.dumps([connector])}
    )
    resolver, routes = build_feishu_identity(settings)
    assert isinstance(resolver, FeishuLoginRequiredResolver)
    assert routes.settings_for("single").app_id == "cli_single"
    assert not hasattr(settings, "feishu_admin_group_id")


def test_report_app_alone_does_not_enable_login() -> None:
    """报告应用独立保留，只有 CONNECTORS 能启用网页登录。"""
    settings = load_settings({"AIMA_FEISHU_APP_ID": "cli_report"})
    resolver, _ = build_feishu_identity(settings)
    assert isinstance(resolver, DevelopmentIdentityResolver)
