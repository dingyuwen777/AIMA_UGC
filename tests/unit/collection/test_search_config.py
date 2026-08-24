from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.capabilities import (
    BILIBILI_TIKHUB_CAPABILITY,
    DOUYIN_TIKHUB_CAPABILITY,
    KUAISHOU_TIKHUB_CAPABILITY,
    WEIBO_TIKHUB_CAPABILITY,
    XIAOHONGSHU_TIKHUB_CAPABILITY,
)
from aima_ugc.modules.collection.search_config import (
    manual_discovery_search_config,
    normalize_search_config,
)


@pytest.mark.parametrize(
    ("capability", "expected"),
    (
        (
            XIAOHONGSHU_TIKHUB_CAPABILITY,
            {"sort_mode": "latest", "published_within": "1d", "content_type": "all"},
        ),
        (
            DOUYIN_TIKHUB_CAPABILITY,
            {
                "sort_mode": "latest",
                "published_within": "1d",
                "duration": "all",
                "content_type": "all",
            },
        ),
        (
            WEIBO_TIKHUB_CAPABILITY,
            {"sort_mode": "latest", "published_within": "day"},
        ),
        (
            BILIBILI_TIKHUB_CAPABILITY,
            {"sort_mode": "latest", "content_type": "video"},
        ),
        (KUAISHOU_TIKHUB_CAPABILITY, {"content_type": "video"}),
    ),
)
def test_manual_discovery_default_uses_each_platforms_real_capability(
    capability,  # type: ignore[no-untyped-def]
    expected: dict[str, str],
) -> None:
    assert manual_discovery_search_config(capability) == expected


def test_search_config_rejects_unsupported_dimension_and_value() -> None:
    with pytest.raises(ValueError, match="published_within"):
        normalize_search_config(
            BILIBILI_TIKHUB_CAPABILITY,
            {"published_within": "1d"},
        )
    with pytest.raises(ValueError, match="sort_mode=provider_private"):
        normalize_search_config(
            XIAOHONGSHU_TIKHUB_CAPABILITY,
            {"sort_mode": "provider_private"},
        )


def test_new_plan_can_require_all_supported_search_dimensions() -> None:
    with pytest.raises(ValueError, match="缺少显式字段.*published_within"):
        normalize_search_config(
            XIAOHONGSHU_TIKHUB_CAPABILITY,
            {"sort_mode": "latest", "content_type": "all"},
            require_complete=True,
        )

    assert normalize_search_config(
        XIAOHONGSHU_TIKHUB_CAPABILITY,
        {"sort_mode": "latest", "published_within": "1d", "content_type": "all"},
        require_complete=True,
    ) == {"sort_mode": "latest", "published_within": "1d", "content_type": "all"}


def test_existing_plan_empty_config_remains_valid_for_legacy_runtime_defaults() -> None:
    assert normalize_search_config(XIAOHONGSHU_TIKHUB_CAPABILITY, {}) == {}
