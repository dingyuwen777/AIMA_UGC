from __future__ import annotations

import pytest
from aima_ugc.contracts.platform import PlatformName
from aima_ugc.platform.presentation import platform_display_name


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("xiaohongshu", "小红书"),
        ("douyin", "抖音"),
        ("weibo", "微博"),
        ("bilibili", "哔哩哔哩"),
        ("kuaishou", "快手"),
    ],
)
def test_platform_display_name_translates_formal_machine_values(
    platform: PlatformName,
    expected: str,
) -> None:
    assert platform_display_name(platform) == expected
