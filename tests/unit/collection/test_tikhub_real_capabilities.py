"""真实 TikHub Fixture/Probe 已证明能力的 Capability/Registry 回归。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.adapters.providers.tikhub.capabilities import (
    BILIBILI_TIKHUB_CAPABILITY,
    DOUYIN_TIKHUB_CAPABILITY,
    KUAISHOU_TIKHUB_CAPABILITY,
    WEIBO_TIKHUB_CAPABILITY,
    XIAOHONGSHU_TIKHUB_CAPABILITY,
)
from aima_ugc.modules.system.models import ProviderConfig


def _operation(capability, business_operation: str):
    operation = capability.operation(business_operation)
    assert operation is not None
    return operation


def test_real_probe_backed_capabilities_cover_all_five_platforms() -> None:
    capabilities = (
        XIAOHONGSHU_TIKHUB_CAPABILITY,
        DOUYIN_TIKHUB_CAPABILITY,
        WEIBO_TIKHUB_CAPABILITY,
        BILIBILI_TIKHUB_CAPABILITY,
        KUAISHOU_TIKHUB_CAPABILITY,
    )
    assert {item.platform for item in capabilities} == {
        "xiaohongshu",
        "douyin",
        "weibo",
        "bilibili",
        "kuaishou",
    }
    assert all(item.provider == "tikhub" for item in capabilities)
    assert all(item.operation("keyword_search") is not None for item in capabilities)
    assert all(item.operation("content_detail") is not None for item in capabilities)
    assert all(item.operation("comments") is not None for item in capabilities)


def test_reply_capabilities_match_real_nonempty_evidence() -> None:
    capabilities = (
        XIAOHONGSHU_TIKHUB_CAPABILITY,
        DOUYIN_TIKHUB_CAPABILITY,
        WEIBO_TIKHUB_CAPABILITY,
        BILIBILI_TIKHUB_CAPABILITY,
        KUAISHOU_TIKHUB_CAPABILITY,
    )
    for capability in capabilities:
        assert _operation(capability, "comments").supports_sub_comments is True
        assert capability.operation("sub_comments") is not None


def test_real_comment_shape_controls_reply_count_and_incremental_claims() -> None:
    assert _operation(XIAOHONGSHU_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(DOUYIN_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(WEIBO_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(BILIBILI_TIKHUB_CAPABILITY, "comments").supports_reply_count is True
    assert _operation(KUAISHOU_TIKHUB_CAPABILITY, "comments").supports_reply_count is True

    # xiaohongshu latest_v2 与 B站 mode=2/next_offset=0 都有当前真实“最新优先”证据；
    # 抖音缺少最新评论排序，微博/快手真实页顺序不满足安全历史边界。
    assert (
        _operation(XIAOHONGSHU_TIKHUB_CAPABILITY, "comments").supports_incremental_comment_sort
        is True
    )
    assert (
        _operation(BILIBILI_TIKHUB_CAPABILITY, "comments").supports_incremental_comment_sort is True
    )
    for capability in (
        DOUYIN_TIKHUB_CAPABILITY,
        WEIBO_TIKHUB_CAPABILITY,
        KUAISHOU_TIKHUB_CAPABILITY,
    ):
        assert _operation(capability, "comments").supports_incremental_comment_sort is False


def test_search_capabilities_expose_only_runtime_supported_business_values() -> None:
    xiaohongshu = _operation(XIAOHONGSHU_TIKHUB_CAPABILITY, "keyword_search")
    assert set(xiaohongshu.supported_content_types) == {"all", "video", "image"}

    douyin = _operation(DOUYIN_TIKHUB_CAPABILITY, "keyword_search")
    assert set(douyin.supported_sort_modes) == {"general", "most_liked", "latest"}
    assert set(douyin.supported_time_filters) == {"all", "1d", "7d", "180d"}
    assert set(douyin.supported_duration_filters) == {
        "all",
        "under_1m",
        "1_5m",
        "over_5m",
    }
    assert set(douyin.supported_content_types) == {"all", "video", "image"}
    assert douyin.native_time_filter is True

    weibo = _operation(WEIBO_TIKHUB_CAPABILITY, "keyword_search")
    assert set(weibo.supported_sort_modes) == {"general", "latest", "hot"}
    # 微博 Provider search_type 是单一维度；不能再把 content_type 与 sort_mode 虚构成独立组合。
    assert weibo.supported_content_types == ()
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
    assert bilibili.observes_comment_count is False

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

    for platform in ("xiaohongshu", "douyin", "weibo", "bilibili", "kuaishou"):
        route = registry.resolve(config=config, platform=platform)
        assert route.platform == platform
        assert route.provider == "tikhub"
        assert route.capability.operation("keyword_search") is not None
