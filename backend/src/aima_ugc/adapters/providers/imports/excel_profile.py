"""Excel 导入 Profile 与平台值归一化规则。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ExcelImportRowError

AIMA_MONITORING_EXCEL_V1 = "aima-monitoring-excel.v1"

_REQUIRED_HEADERS = (
    "序号",
    "监测项名称",
    "文章编号",
    "标题",
    "内文",
    "媒体名称（中文）",
    "版面",
    "出版日期",
    "媒体类型",
    "作者",
    "全文情感",
    "原文链接",
    "粉丝数",
)

_PLATFORM_ALIASES = {
    "小红书": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "xhs": "xiaohongshu",
    "red": "xiaohongshu",
    "抖音": "douyin",
    "douyin": "douyin",
    "微博": "weibo",
    "新浪微博": "weibo",
    "weibo": "weibo",
    "b站": "bilibili",
    "哔哩哔哩": "bilibili",
    "bilibili": "bilibili",
    "快手": "kuaishou",
    "kuaishou": "kuaishou",
}
_PLATFORM_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class ExcelImportProfile:
    """描述一个受版本控制的源 Excel 结构。"""

    name: str
    default_sheet_name: str
    required_headers: tuple[str, ...]

    def resolve_platform(self, value: object) -> str:
        text = _non_empty_text(value)
        if text is None:
            raise ExcelImportRowError("platform_missing", "媒体名称（中文）不能为空")
        alias = _PLATFORM_ALIASES.get(text.casefold())
        if alias is not None:
            return alias
        candidate = re.sub(r"\s+", "_", text.casefold())
        if _PLATFORM_PATTERN.fullmatch(candidate):
            return candidate
        raise ExcelImportRowError(
            "platform_unmapped",
            "媒体名称（中文）无法安全映射为 Canonical platform",
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
