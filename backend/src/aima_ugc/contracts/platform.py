"""AIMA_UGC 唯一平台机器身份 Contract。"""

from typing import Literal

type PlatformName = Literal[
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
    "kuaishou",
]
type PlatformScope = Literal[
    "all",
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
    "kuaishou",
]

PLATFORM_NAMES: tuple[PlatformName, ...] = (
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
    "kuaishou",
)
PLATFORM_SCOPES: tuple[PlatformScope, ...] = ("all", *PLATFORM_NAMES)

__all__ = ["PLATFORM_NAMES", "PLATFORM_SCOPES", "PlatformName", "PlatformScope"]
