"""真实 TikHub Fixture/Probe 已证明能力的 Capability/Registry 回归。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.adapters.providers.tikhub.capabilities import (
    BILIBILI_TIKHUB_CAPABILITY,
    DOUYIN_TIKHUB_CAPABILITY,
    KUAISHOU_TIKHUB_CAPABILITY,
    WEIBO_TIKHUB_CAPABILITY,
    XHS_TIKHUB_CAPABILITY,
)
from aima_ugc.modules.system.models import ProviderConfig


def _operation(capability, business_operation: str):
    operation = capability.operation(business_operation)
    assert operation is not None
    return operation


def test_real_probe_backed_capabilities_cover_all_five_platforms() -> None:
    capabilities = (
        XHS_TIKHUB_CAPABILITY,
        DOUYIN_TIKHUB_CAPABILITY,
        WEIBO_TIKHUB_CAPABILITY,
        BILIBILI_TIKHUB_CAPABILITY,
        KUAISHOU_TIKHUB_CAPABILITY,
    )
    assert {item.platform for item in capabilities} == {
        "xhs",
        "douyin",
        "weibo",
        "bilibili",
        "kuaishou",
    }
    assert all(item.provider == "tikhub" for item in capabilities)
    assert all(item.operation("keyword_search") is not None for item in capabilities)
    assert all(item.operation("content_detail") is not None for item in capabilities)
    assert all(item.operation("comments") is not None for item in capabilities)


def test_reply_capabilities_match_real_nonempty_and_empty_evidence() -> None:
    assert _operation(XHS_TIKHUB_CAPABILITY, "comments").supports_sub_comments is True
    assert _operation(DOUYIN_TIKHUB_CAPABILITY, "comments").supports_sub_comments is True
    assert _operation(WEIBO_TIKHUB_CAPABILITY, "comments").supports_sub_comments is True
    assert _operation(BILIBILI_TIKHUB_CAPABILITY, "comments").supports_sub_comments is True

    for capability in (
        XHS_TIKHUB_CAPABILITY,
        DOUYIN_TIKHUB_CAPABILITY,
        WEIBO_TIKHUB_CAPABILITY,
        BILIBILI_TIKHUB_CAPABILITY,
    ):
        assert capability.operation("sub_comments") is not None

    kuaishou_comments = _operation(KUAISHOU_TIKHUB_CAPABILITY, "comments")
    assert kuaishou_comments.supports_sub_comments is False
    assert KUAISHOU_TIKHUB_CAPABILITY.operation("sub_comments") is None


def test_real_comment_shape_controls_reply_count_and_incremental_claims() -> None:
    assert _operation(XHS_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(DOUYIN_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(WEIBO_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(BILIBILI_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(KUAISHOU_TIKHUB_CAPABILITY, "comments").supports_reply_count is False

    for capability in (
        XHS_TIKHUB_CAPABILITY,
        DOUYIN_TIKHUB_CAPABILITY,
        WEIBO_TIKHUB_CAPABILITY,
        BILIBILI_TIKHUB_CAPABILITY,
        KUAISHOU_TIKHUB_CAPABILITY,
    ):
        assert _operation(capability, "comments").supports_incremental_comment_sort is False


def test_search_capabilities_expose_normalized_business_values_not_provider_cursors() -> None:
    douyin = _operation(DOUYIN_TIKHUB_CAPABILITY, "keyword_search")
    assert set(douyin.supported_sort_modes) == {"general", "most_liked", "latest"}
    assert set(douyin.supported_time_filters) == {"all", "1d", "7d", "180d"}
    assert set(douyin.supported_content_types) == {"all", "video", "image", "article"}
    assert douyin.native_time_filter is True

    weibo = _operation(WEIBO_TIKHUB_CAPABILITY, "keyword_search")
    assert set(weibo.supported_sort_modes) == {
        "general",
        "latest",
        "hot",
        "video",
        "image",
        "article",
    }
    assert set(weibo.supported_time_filters) == {"all", "hour", "day", "week", "month"}
    assert weibo.native_time_filter is True

    bilibili = _operation(BILIBILI_TIKHUB_CAPABILITY, "keyword_search")
    assert set(bilibili.supported_sort_modes) == {
        "general",
        "latest",
        "play_count",
        "danmaku_count",
    }
    assert bilibili.supported_content_types == ("video",)
    assert bilibili.native_time_filter is False

    kuaishou = _operation(KUAISHOU_TIKHUB_CAPABILITY, "keyword_search")
    assert kuaishou.supported_sort_modes == ()
    assert kuaishou.supported_time_filters == ()


def test_default_registry_resolves_all_real_verified_tikhub_platforms() -> None:
    registry = build_default_provider_registry()
    config = ProviderConfig(
        id=uuid4(),
        provider="tikhub",
        display_name="TikHub 真实兼容验证",
        base_url="https://api.tikhub.io",
        secret_ref="providers/tikhub/test/api-key",
        enabled=True,
    )

    for platform in ("xhs", "douyin", "weibo", "bilibili", "kuaishou"):
        route = registry.resolve(config=config, platform=platform)
        assert route.platform == platform
        assert route.provider == "tikhub"
        assert route.capability.operation("keyword_search") is not None
