"""AIMA_UGC 唯一平台机器身份 Contract。"""

from typing import Literal, cast

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


def require_platform_name(value: str) -> PlatformName:
    """校验内部机器值已经是五个平台之一，不做任何别名或大小写转换。"""
    if value not in PLATFORM_NAMES:
        raise ValueError(f"非法平台机器标识: {value}")
    return cast(PlatformName, value)


def normalize_platform_name(value: str) -> PlatformName:
    """外部输入边界接受完整平台名称的大小写差异，并立即归一化为小写机器值。"""
    return require_platform_name(value.strip().casefold())


__all__ = [
    "PLATFORM_NAMES",
    "PLATFORM_SCOPES",
    "PlatformName",
    "PlatformScope",
    "normalize_platform_name",
    "require_platform_name",
]
