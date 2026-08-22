"""跨 Excel 与报告输出复用的平台中文展示名称。"""

from __future__ import annotations

from typing import Final

from aima_ugc.contracts.platform import PlatformName

_PLATFORM_DISPLAY_NAMES: Final[dict[PlatformName, str]] = {
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "weibo": "微博",
    "bilibili": "哔哩哔哩",
    "kuaishou": "快手",
}


def platform_display_name(platform: PlatformName) -> str:
    """把五个平台正式机器值转换为中文展示文案。"""

    return _PLATFORM_DISPLAY_NAMES[platform]
