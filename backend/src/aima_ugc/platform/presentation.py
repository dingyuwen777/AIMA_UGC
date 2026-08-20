"""跨 Excel 与报告输出复用的平台展示名称。"""

from __future__ import annotations

from typing import Final

_PLATFORM_DISPLAY_NAMES: Final = {
    "xiaohongshu": "小红书",
    "小红书": "小红书",
    "douyin": "抖音",
    "抖音": "抖音",
    "weibo": "微博",
    "微博": "微博",
    "bilibili": "哔哩哔哩",
    "b站": "哔哩哔哩",
    "哔哩哔哩": "哔哩哔哩",
    "kuaishou": "快手",
    "快手": "快手",
}


def platform_display_name(platform: str) -> str:
    """返回已知平台的中文展示名，未知平台保持原值。"""

    return _PLATFORM_DISPLAY_NAMES.get(platform.casefold(), platform)
