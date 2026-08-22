"""Excel 导入 Profile 与平台值归一化规则。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from aima_ugc.contracts.platform import PlatformName

from .models import ExcelImportRowError

AIMA_MONITORING_EXCEL_V1 = "aima-monitoring-excel.v1"

_REQUIRED_HEADERS = (
    "媒体名称（中文）",
    "标题",
    "内文",
    "作者",
    "出版日期",
    "原文链接",
)

_FORMAL_PLATFORM_NAMES: dict[str, PlatformName] = {
    "xiaohongshu": "xiaohongshu",
    "douyin": "douyin",
    "weibo": "weibo",
    "bilibili": "bilibili",
    "kuaishou": "kuaishou",
}
_PLATFORM_SOURCE_KEYWORDS: tuple[tuple[str, PlatformName], ...] = (
    ("新浪微博", "weibo"),
    ("哔哩哔哩", "bilibili"),
    ("小红书", "xiaohongshu"),
    ("抖音", "douyin"),
    ("微博", "weibo"),
    ("快手", "kuaishou"),
    ("b站", "bilibili"),
)


@dataclass(frozen=True, slots=True)
class ExcelImportProfile:
    """描述一个受版本控制的源 Excel 结构。"""

    name: str
    default_sheet_name: str
    required_headers: tuple[str, ...]

    def resolve_platform(self, value: object) -> PlatformName:
        text = _non_empty_text(value)
        if text is None:
            raise ExcelImportRowError("platform_missing", "媒体名称（中文）不能为空")

        formal = _FORMAL_PLATFORM_NAMES.get(text)
        if formal is not None:
            return formal

        compact = re.sub(r"\s+", "", text.casefold())
        for keyword, platform in _PLATFORM_SOURCE_KEYWORDS:
            if keyword in compact:
                return platform

        raise ExcelImportRowError(
            "platform_unmapped",
            "媒体名称（中文）只能安全映射到系统五个平台机器标识",
        )


_PROFILE = ExcelImportProfile(
    name=AIMA_MONITORING_EXCEL_V1,
    default_sheet_name="文章",
    required_headers=_REQUIRED_HEADERS,
)


def get_excel_import_profile(name: str) -> ExcelImportProfile:
    """按显式版本名取得 Excel Profile；未知版本 fail closed。"""

    if name != _PROFILE.name:
        raise ValueError(f"不支持的 Excel Profile: {name}")
    return _PROFILE


def _non_empty_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
