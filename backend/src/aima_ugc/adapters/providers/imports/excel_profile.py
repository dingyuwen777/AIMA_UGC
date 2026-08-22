"""Excel 导入 Profile 与平台值归一化规则。"""

from __future__ import annotations

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

_PLATFORM_LABELS: dict[str, PlatformName] = {
    "小红书": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "抖音": "douyin",
    "douyin": "douyin",
    "微博": "weibo",
    "新浪微博": "weibo",
    "weibo": "weibo",
    "B站": "bilibili",
    "哔哩哔哩": "bilibili",
    "bilibili": "bilibili",
    "快手": "kuaishou",
    "kuaishou": "kuaishou",
}


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
        platform = _PLATFORM_LABELS.get(text)
        if platform is not None:
            return platform
        raise ExcelImportRowError(
            "platform_unmapped",
            "媒体名称（中文）只能映射到系统五个平台机器标识",
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
