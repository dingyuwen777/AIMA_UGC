"""代表性评论报告区块的数据模型与 Markdown 投影。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPRESENTATIVE_GROUP_ORDER: tuple[tuple[str, str, str], ...] = (
    ("小红书", "正面", "小红书正面评价"),
    ("小红书", "负面", "小红书负面评价"),
    ("抖音", "正面", "抖音正面评价"),
    ("抖音", "负面", "抖音负面评价"),
)

REPRESENTATIVE_TABLE_HEADERS: tuple[str, ...] = (
    "原文链接",
    "截图",
    "评论内容",
    "一级标签",
    "二级标签",
    "行动建议",
    "处理进展",
)


@dataclass(frozen=True, slots=True)
class RepresentativeReportRow:
    """报告第 6 节的一行；不改变原始 Excel 或飞书筛选结果。"""

    platform: str
    sentiment: str
    content_id: str
    content_url: str
    comment_text: str
    primary_label: str
    secondary_label: str
    action_advice: str
    screenshot_path: Path | None = None
    processing_progress: str = ""
    link_text: str = ""


def build_representative_section(
    rows: tuple[RepresentativeReportRow, ...] | list[RepresentativeReportRow] = (),
    *,
    report_root: Path | None = None,
) -> str:
    """将代表性结果投影成报告末尾的 Markdown 区块。

    ``report_root`` 用于把截图路径转成报告目录内的相对路径；路径不存在时截图单元格
    保持为空，不让单条截图失败阻断整份报告。
    """

    sections = ["## 6. 代表性评论与关联页面"]
    for platform, sentiment, title in REPRESENTATIVE_GROUP_ORDER:
        sections.extend((f"### 6.{_subsection_number(platform, sentiment)} {title}", ""))
        group_rows = [
            row
            for row in rows
            if row.platform == platform and row.sentiment == sentiment
        ]
        rendered_rows = tuple(
            _render_row(row, report_root=report_root) for row in group_rows[:10]
        )
        if not rendered_rows:
            rendered_rows = (("暂无数据", "", "", "", "", "", ""),)
        sections.append(_markdown_table(REPRESENTATIVE_TABLE_HEADERS, rendered_rows))
        sections.append("")
    return "\n".join(sections).rstrip()


def _subsection_number(platform: str, sentiment: str) -> int:
    for index, (known_platform, known_sentiment, _) in enumerate(
        REPRESENTATIVE_GROUP_ORDER, start=1
    ):
        if (platform, sentiment) == (known_platform, known_sentiment):
            return index
    raise ValueError(f"未知代表性分组: {platform}/{sentiment}")


def _render_row(
    row: RepresentativeReportRow,
    *,
    report_root: Path | None,
) -> tuple[str, ...]:
    link_label = row.link_text.strip() or row.content_url.strip() or row.content_id.strip()
    link = _markdown_link(link_label, row.content_url)
    if not link:
        link = _markdown_cell(row.content_id)
    screenshot = ""
    if (
        row.screenshot_path is not None
        and row.screenshot_path.is_file()
        and report_root is not None
    ):
        try:
            relative = row.screenshot_path.resolve().relative_to(report_root.resolve())
        except ValueError:
            relative = None
        if relative is not None:
            screenshot = f"![截图]({relative.as_posix()})"
    return (
        link,
        screenshot,
        "",
        format_representative_labels(row.primary_label),
        format_representative_labels(row.secondary_label),
        row.action_advice,
        row.processing_progress,
    )


def _markdown_link(label: str, url: str) -> str:
    value = url.strip()
    if not value:
        return ""
    # Markdown 链接允许中文 URL；只对右括号进行编码，避免破坏表格语法。
    return f"[{label}]({value.replace(')', '%29')})"


def _markdown_table(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
) -> str:
    lines = [
        "| " + " | ".join(_markdown_cell(value) for value in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_markdown_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _markdown_cell(value: str) -> str:
    normalized = str(value).replace("\r\n", "\n").replace("\r", "\n")
    # 飞书文本块不会把 HTML <br> 渲染成换行，使用中文分号保持可读性。
    normalized = re.sub(r"<br\s*/?>", "；", normalized, flags=re.IGNORECASE)
    normalized = normalized.replace("\n", "；")
    return normalized.replace("\\", "\\\\").replace("|", "\\|")


def format_representative_labels(value: str) -> str:
    """按飞书多选字段的语义展示标签：拆分、去重并保留输入顺序。"""

    raw_values = re.split(
        r"(?:\r?\n|<br\s*/?>|[,，、;；])+",
        str(value),
        flags=re.IGNORECASE,
    )
    labels: list[str] = []
    for raw_value in raw_values:
        label = _collapse_adjacent_repeated_label(raw_value.strip())
        if label and label not in labels:
            labels.append(label)
    return "、".join(labels)


def _collapse_adjacent_repeated_label(value: str) -> str:
    """修复少数导出器把同一个多选值无分隔地拼接两次的结果。"""

    if not value:
        return ""
    for unit_length in range(1, len(value) // 2 + 1):
        if len(value) % unit_length:
            continue
        repetitions = len(value) // unit_length
        if repetitions >= 2 and value == value[:unit_length] * repetitions:
            return value[:unit_length]
    return value


def normalize_representative_content_url(platform: str, value: str) -> str:
    """把已知的失效小红书旧路径改成网页端当前的笔记路径。"""

    url = str(value).strip()
    if platform != "小红书" or not url:
        return url
    parsed = urlsplit(url)
    if parsed.hostname not in {"xiaohongshu.com", "www.xiaohongshu.com"}:
        return url
    prefix = "/discovery/item/"
    if not parsed.path.startswith(prefix):
        return url
    normalized_path = "/explore/" + parsed.path[len(prefix) :]
    return urlunsplit(parsed._replace(path=normalized_path))


__all__ = [
    "REPRESENTATIVE_GROUP_ORDER",
    "REPRESENTATIVE_TABLE_HEADERS",
    "RepresentativeReportRow",
    "build_representative_section",
    "format_representative_labels",
    "normalize_representative_content_url",
]
