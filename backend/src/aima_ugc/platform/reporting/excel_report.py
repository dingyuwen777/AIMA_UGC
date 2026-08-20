"""从统一数据 Excel 生成只读 Markdown/Word 舆情报告。"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from .markdown_word import WordConversionSummary, convert_markdown_to_docx

_BEIJING = ZoneInfo("Asia/Shanghai")
_CONTENT_SHEET = "内容"
_LABEL_SHEET = "标签明细"
_COMMENT_SHEET = "评论"
_REQUIRED_CONTENT_HEADERS = (
    "平台",
    "发布时间",
    "命中关键词",
    "情感标签",
    "一级标签",
    "二级标签",
)
_REQUIRED_LABEL_HEADERS = ("平台", "情感标签", "一级标签", "二级标签")
_REQUIRED_COMMENT_HEADERS = ("平台",)
_TEMPLATE_TOKEN_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
_KEYWORD_SPLIT_RE = re.compile(r"[；;\n]+")
_PRIMARY_CHART_LIMIT = 8
_SECONDARY_CHART_LIMIT = 10
_KEYWORD_CHART_LIMIT = 12


@dataclass(frozen=True, slots=True)
class ReportGenerationSummary:
    """一次 Excel → Markdown → Word 报告生成结果。"""

    source_excel_path: Path
    template_path: Path
    markdown_path: Path
    word_path: Path
    content_rows: int
    label_rows: int
    comment_rows: int
    start_date: str | None
    end_date: str | None
    word_chart_count: int


@dataclass(slots=True)
class _ReportStats:
    content_rows: int
    label_rows: int
    comment_rows: int
    platform_counts: Counter[str]
    comment_platform_counts: Counter[str]
    sentiment_counts: Counter[str]
    primary_counts: Counter[str]
    secondary_counts: Counter[str]
    label_pair_counts: Counter[tuple[str, str]]
    keyword_counts: Counter[str]
    daily_content: Counter[date]
    daily_platform: dict[date, Counter[str]]
    daily_sentiment: dict[date, Counter[str]]
    daily_primary: dict[date, Counter[str]]
    daily_secondary: dict[date, Counter[str]]
    quality_counts: Counter[str]
    start_date: date | None
    end_date: date | None


def generate_excel_report(
    *,
    input_path: Path,
    output_dir: Path,
    template_path: Path,
    markdown_name: str = "report.md",
    word_name: str = "report.docx",
    generated_at: datetime | None = None,
) -> ReportGenerationSummary:
    """只读统一 Excel，按 Markdown 模板生成报告并转换为 Word。"""

    source_path = Path(input_path)
    template = Path(template_path)
    target_dir = Path(output_dir)
    if source_path.suffix.lower() != ".xlsx":
        raise ValueError("报告输入必须是 .xlsx 文件")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if template.suffix.lower() != ".md":
        raise ValueError("报告模板必须是 .md 文件")
    if not template.is_file():
        raise FileNotFoundError(template)
    if Path(markdown_name).name != markdown_name or not markdown_name.lower().endswith(".md"):
        raise ValueError("markdown_name 必须是当前目录下的 .md 文件名")
    if Path(word_name).name != word_name or not word_name.lower().endswith(".docx"):
        raise ValueError("word_name 必须是当前目录下的 .docx 文件名")

    stats = _collect_stats(source_path)
    actual_generated_at = generated_at or datetime.now(_BEIJING)
    replacements = _build_template_replacements(
        stats,
        source_path=source_path,
        generated_at=actual_generated_at,
    )
    template_text = template.read_text(encoding="utf-8")
    markdown = _render_template(template_text, replacements)

    target_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = target_dir / markdown_name
    word_path = target_dir / word_name
    _atomic_write_text(markdown_path, markdown)
    word_summary: WordConversionSummary = convert_markdown_to_docx(markdown_path, word_path)

    return ReportGenerationSummary(
        source_excel_path=source_path,
        template_path=template,
        markdown_path=markdown_path,
        word_path=word_path,
        content_rows=stats.content_rows,
        label_rows=stats.label_rows,
        comment_rows=stats.comment_rows,
        start_date=stats.start_date.isoformat() if stats.start_date is not None else None,
        end_date=stats.end_date.isoformat() if stats.end_date is not None else None,
        word_chart_count=word_summary.chart_count,
    )


def _collect_stats(path: Path) -> _ReportStats:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        expected = {_CONTENT_SHEET, _LABEL_SHEET, _COMMENT_SHEET}
        missing_sheets = expected.difference(workbook.sheetnames)
        if missing_sheets:
            raise ValueError(f"统一 Excel 缺少 Sheet: {'、'.join(sorted(missing_sheets))}")

        platform_counts: Counter[str] = Counter()
        comment_platform_counts: Counter[str] = Counter()
        sentiment_counts: Counter[str] = Counter()
        primary_counts: Counter[str] = Counter()
        secondary_counts: Counter[str] = Counter()
        label_pair_counts: Counter[tuple[str, str]] = Counter()
        keyword_counts: Counter[str] = Counter()
        daily_content: Counter[date] = Counter()
        daily_platform: defaultdict[date, Counter[str]] = defaultdict(Counter)
        daily_sentiment: defaultdict[date, Counter[str]] = defaultdict(Counter)
        daily_primary: defaultdict[date, Counter[str]] = defaultdict(Counter)
        daily_secondary: defaultdict[date, Counter[str]] = defaultdict(Counter)
        quality_counts: Counter[str] = Counter()

        content_rows = 0
        content_sheet = workbook[_CONTENT_SHEET]
        content_headers = _header_index(content_sheet, _REQUIRED_CONTENT_HEADERS)
        for row in content_sheet.iter_rows(min_row=2, values_only=True):
            if _row_is_empty(row):
                continue
            content_rows += 1
            platform = _clean_text(_row_value(row, content_headers, "平台"))
            if platform is None:
                quality_counts["内容缺失平台"] += 1
                platform = "（未填写）"
            platform_counts[platform] += 1

            sentiment = _clean_text(_row_value(row, content_headers, "情感标签"))
            if sentiment is None:
                quality_counts["内容缺失情感标签"] += 1
            else:
                sentiment_counts[sentiment] += 1

            primary_labels = _split_multiline(_row_value(row, content_headers, "一级标签"))
            secondary_labels = _split_multiline(_row_value(row, content_headers, "二级标签"))
            if not primary_labels:
                quality_counts["内容缺失一级标签"] += 1
            if not secondary_labels:
                quality_counts["内容缺失二级标签"] += 1
            if len(primary_labels) != len(secondary_labels):
                quality_counts["内容一级二级标签行数不一致"] += 1

            keywords = _split_keywords(_row_value(row, content_headers, "命中关键词"))
            if not keywords:
                quality_counts["内容缺失命中关键词"] += 1
            else:
                keyword_counts.update(dict.fromkeys(keywords, 1))

            raw_published_at = _row_value(row, content_headers, "发布时间")
            published_date, invalid_date = _parse_date(raw_published_at)
            if raw_published_at is None or _clean_text(raw_published_at) is None:
                quality_counts["内容缺失发布时间"] += 1
            elif invalid_date:
                quality_counts["内容发布时间无法解析"] += 1
            if published_date is None:
                continue

            daily_content[published_date] += 1
            daily_platform[published_date][platform] += 1
            if sentiment is not None:
                daily_sentiment[published_date][sentiment] += 1
            daily_primary[published_date].update(primary_labels)
            daily_secondary[published_date].update(secondary_labels)

        label_rows = 0
        label_sheet = workbook[_LABEL_SHEET]
        label_headers = _header_index(label_sheet, _REQUIRED_LABEL_HEADERS)
        for row in label_sheet.iter_rows(min_row=2, values_only=True):
            if _row_is_empty(row):
                continue
            label_rows += 1
            primary = _clean_text(_row_value(row, label_headers, "一级标签"))
            secondary = _clean_text(_row_value(row, label_headers, "二级标签"))
            if primary is None:
                quality_counts["标签明细缺失一级标签"] += 1
            else:
                primary_counts[primary] += 1
            if secondary is None:
                quality_counts["标签明细缺失二级标签"] += 1
            else:
                secondary_counts[secondary] += 1
            if primary is not None and secondary is not None:
                label_pair_counts[(primary, secondary)] += 1

        comment_rows = 0
        comment_sheet = workbook[_COMMENT_SHEET]
        comment_headers = _header_index(comment_sheet, _REQUIRED_COMMENT_HEADERS)
        for row in comment_sheet.iter_rows(min_row=2, values_only=True):
            if _row_is_empty(row):
                continue
            comment_rows += 1
            platform = _clean_text(_row_value(row, comment_headers, "平台"))
            if platform is None:
                quality_counts["评论缺失平台"] += 1
                platform = "（未填写）"
            comment_platform_counts[platform] += 1

        dates = sorted(daily_content)
        return _ReportStats(
            content_rows=content_rows,
            label_rows=label_rows,
            comment_rows=comment_rows,
            platform_counts=platform_counts,
            comment_platform_counts=comment_platform_counts,
            sentiment_counts=sentiment_counts,
            primary_counts=primary_counts,
            secondary_counts=secondary_counts,
            label_pair_counts=label_pair_counts,
            keyword_counts=keyword_counts,
            daily_content=daily_content,
            daily_platform=dict(daily_platform),
            daily_sentiment=dict(daily_sentiment),
            daily_primary=dict(daily_primary),
            daily_secondary=dict(daily_secondary),
            quality_counts=quality_counts,
            start_date=dates[0] if dates else None,
            end_date=dates[-1] if dates else None,
        )
    finally:
        workbook.close()


def _header_index(sheet: Any, required: Sequence[str]) -> dict[str, int]:
    header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header_row is None:
        raise ValueError(f"Sheet {sheet.title} 没有表头")
    index: dict[str, int] = {}
    for position, value in enumerate(header_row):
        if isinstance(value, str) and value not in index:
            index[value] = position
    missing = [name for name in required if name not in index]
    if missing:
        raise ValueError(f"Sheet {sheet.title} 缺少表头: {'、'.join(missing)}")
    return index


def _row_value(row: Sequence[Any], header_index: Mapping[str, int], name: str) -> Any:
    position = header_index[name]
    return row[position] if position < len(row) else None


def _row_is_empty(row: Sequence[Any]) -> bool:
    return all(value is None or (isinstance(value, str) and not value.strip()) for value in row)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    text = str(value).strip()
    return text or None


def _split_multiline(value: Any) -> tuple[str, ...]:
    text = _clean_text(value)
    if text is None:
        return ()
    return tuple(part.strip() for part in text.splitlines() if part.strip())


def _split_keywords(value: Any) -> tuple[str, ...]:
    text = _clean_text(value)
    if text is None:
        return ()
    return tuple(part.strip() for part in _KEYWORD_SPLIT_RE.split(text) if part.strip())


def _parse_date(value: Any) -> tuple[date | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, datetime):
        return value.date(), False
    if isinstance(value, date):
        return value, False
    text = str(value).strip()
    if not text:
        return None, False
    candidates = (text, text[:19], text[:10])
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate).date(), False
        except ValueError:
            try:
                return date.fromisoformat(candidate), False
            except ValueError:
                continue
    return None, True


def _build_template_replacements(
    stats: _ReportStats,
    *,
    source_path: Path,
    generated_at: datetime,
) -> dict[str, str]:
    start = stats.start_date.isoformat() if stats.start_date is not None else "无有效日期"
    end = stats.end_date.isoformat() if stats.end_date is not None else "无有效日期"
    overview = _markdown_table(
        ("指标", "数量/范围"),
        (
            ("内容总量", stats.content_rows),
            ("评论总量", stats.comment_rows),
            ("标签对总量", stats.label_rows),
            ("平台数", len(stats.platform_counts)),
            ("一级标签数", len(stats.primary_counts)),
            ("二级标签数", len(stats.secondary_counts)),
            ("数据日期范围", f"{start} ~ {end}"),
        ),
    )
    quality_rows = [(name, count) for name, count in _sorted_counter(stats.quality_counts)]
    if not quality_rows:
        quality_rows = [("未发现统计字段缺失/异常", 0)]

    platform_rows: list[tuple[object, ...]] = []
    for platform, count in _sorted_counter(stats.platform_counts):
        platform_rows.append(
            (
                platform,
                count,
                _percentage(count, stats.content_rows),
                stats.comment_platform_counts.get(platform, 0),
            )
        )

    primary_rows = [
        (label, count, _percentage(count, stats.label_rows))
        for label, count in _sorted_counter(stats.primary_counts)
    ]
    secondary_rows = [
        (label, count, _percentage(count, stats.label_rows))
        for label, count in _sorted_counter(stats.secondary_counts)
    ]
    sentiment_rows = [
        (label, count, _percentage(count, stats.content_rows))
        for label, count in _sorted_counter(stats.sentiment_counts)
    ]
    keyword_rows = [
        (label, count, _percentage(count, stats.content_rows))
        for label, count in _sorted_counter(stats.keyword_counts)
    ]
    pair_rows = [
        (primary, secondary, count, _percentage(count, stats.label_rows))
        for (primary, secondary), count in sorted(
            stats.label_pair_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]

    dates = sorted(stats.daily_content)
    platform_series = [label for label, _ in _sorted_counter(stats.platform_counts)]
    sentiment_series = [label for label, _ in _sorted_counter(stats.sentiment_counts)]
    primary_series = [label for label, _ in _sorted_counter(stats.primary_counts)][
        :_PRIMARY_CHART_LIMIT
    ]
    secondary_series = [label for label, _ in _sorted_counter(stats.secondary_counts)][
        :_SECONDARY_CHART_LIMIT
    ]

    return {
        "GENERATED_AT": _format_generated_at(generated_at),
        "SOURCE_FILE": _markdown_inline(str(source_path)),
        "OVERVIEW_TABLE": overview,
        "DATA_QUALITY_TABLE": _markdown_table(("数据完整性检查", "数量"), quality_rows),
        "PLATFORM_TABLE": _markdown_table(("平台", "内容量", "内容占比", "评论量"), platform_rows),
        "PLATFORM_PIE_CHART": _mermaid_pie("各平台内容占比", stats.platform_counts),
        "PLATFORM_DAILY_LEGEND": _series_legend(platform_series),
        "PLATFORM_DAILY_CHART": _mermaid_daily_lines(
            "各平台每日内容量",
            dates,
            platform_series,
            stats.daily_platform,
        ),
        "PLATFORM_DAILY_TABLE": _daily_long_table("平台", dates, stats.daily_platform),
        "SENTIMENT_TABLE": _markdown_table(("情感标签", "内容量", "内容占比"), sentiment_rows),
        "SENTIMENT_PIE_CHART": _mermaid_pie("情感标签占比", stats.sentiment_counts),
        "SENTIMENT_DAILY_LEGEND": _series_legend(sentiment_series),
        "SENTIMENT_DAILY_CHART": _mermaid_daily_lines(
            "情感标签每日趋势",
            dates,
            sentiment_series,
            stats.daily_sentiment,
        ),
        "SENTIMENT_DAILY_TABLE": _daily_long_table("情感标签", dates, stats.daily_sentiment),
        "PRIMARY_TABLE": _markdown_table(("一级标签", "标签对数量", "标签对占比"), primary_rows),
        "PRIMARY_BAR_CHART": _mermaid_bar(
            "一级标签 Top 分布",
            _top_counter(stats.primary_counts, _PRIMARY_CHART_LIMIT),
        ),
        "PRIMARY_DAILY_LEGEND": _series_legend(primary_series),
        "PRIMARY_DAILY_CHART": _mermaid_daily_lines(
            "一级标签每日趋势（Top 序列）",
            dates,
            primary_series,
            stats.daily_primary,
        ),
        "PRIMARY_DAILY_TABLE": _daily_long_table("一级标签", dates, stats.daily_primary),
        "SECONDARY_TABLE": _markdown_table(
            ("二级标签", "标签对数量", "标签对占比"), secondary_rows
        ),
        "SECONDARY_BAR_CHART": _mermaid_bar(
            "二级标签 Top 分布",
            _top_counter(stats.secondary_counts, _SECONDARY_CHART_LIMIT),
        ),
        "SECONDARY_DAILY_LEGEND": _series_legend(secondary_series),
        "SECONDARY_DAILY_CHART": _mermaid_daily_lines(
            "二级标签每日趋势（Top 序列）",
            dates,
            secondary_series,
            stats.daily_secondary,
        ),
        "SECONDARY_DAILY_TABLE": _daily_long_table("二级标签", dates, stats.daily_secondary),
        "LABEL_PAIR_TABLE": _markdown_table(
            ("一级标签", "二级标签", "标签对数量", "标签对占比"), pair_rows
        ),
        "KEYWORD_TABLE": _markdown_table(("命中关键词", "内容量", "内容占比"), keyword_rows),
        "KEYWORD_BAR_CHART": _mermaid_bar(
            "命中关键词 Top 分布",
            _top_counter(stats.keyword_counts, _KEYWORD_CHART_LIMIT),
        ),
    }


def _render_template(template: str, replacements: Mapping[str, str]) -> str:
    tokens = set(_TEMPLATE_TOKEN_RE.findall(template))
    unknown = sorted(tokens.difference(replacements))
    if unknown:
        raise ValueError(f"报告模板包含未知占位符: {'、'.join(unknown)}")
    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace("{{" + token + "}}", value)
    leftovers = _TEMPLATE_TOKEN_RE.findall(rendered)
    if leftovers:
        raise ValueError(f"报告模板存在未替换占位符: {'、'.join(sorted(set(leftovers)))}")
    return rendered.rstrip() + "\n"


def _markdown_table(headers: Sequence[object], rows: Iterable[Sequence[object]]) -> str:
    normalized_rows = [tuple(_markdown_cell(value) for value in row) for row in rows]
    header = "| " + " | ".join(_markdown_cell(value) for value in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    if not normalized_rows:
        empty = tuple("暂无数据" if index == 0 else "" for index in range(len(headers)))
        normalized_rows = [empty]
    body = ["| " + " | ".join(row) + " |" for row in normalized_rows]
    return "\n".join((header, separator, *body))


def _markdown_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _markdown_inline(value: str) -> str:
    return value.replace("`", "\\`").replace("|", "\\|")


def _percentage(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.00%"
    return f"{numerator / denominator * 100:.2f}%"


def _sorted_counter(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _top_counter(counter: Counter[str], limit: int) -> Counter[str]:
    return Counter(dict(_sorted_counter(counter)[:limit]))


def _series_legend(series: Sequence[str]) -> str:
    if not series:
        return "图例：暂无可展示序列。"
    parts = [
        f"**{index}** = {_markdown_inline(label)}" for index, label in enumerate(series, start=1)
    ]
    return "图例：" + "；".join(parts) + "。"


def _mermaid_pie(title: str, counter: Counter[str]) -> str:
    items = _sorted_counter(counter)
    if not items:
        return "暂无可展示图表。"
    lines = ["```mermaid", "pie showData", f"    title {_mermaid_text(title)}"]
    lines.extend(f'    "{_mermaid_text(label)}" : {count}' for label, count in items)
    lines.append("```")
    return "\n".join(lines)


def _mermaid_bar(title: str, counter: Counter[str]) -> str:
    items = _sorted_counter(counter)
    if not items:
        return "暂无可展示图表。"
    labels = [label for label, _ in items]
    values = [count for _, count in items]
    return _mermaid_xychart(title, labels, [values], kind="bar")


def _mermaid_daily_lines(
    title: str,
    dates: Sequence[date],
    series: Sequence[str],
    values: Mapping[date, Counter[str]],
) -> str:
    if not dates or not series:
        return "暂无可展示图表。"
    matrix = [[values.get(day, Counter()).get(label, 0) for day in dates] for label in series]
    return _mermaid_xychart(title, [day.isoformat() for day in dates], matrix, kind="line")


def _mermaid_xychart(
    title: str,
    categories: Sequence[str],
    series_values: Sequence[Sequence[int]],
    *,
    kind: str,
) -> str:
    if kind not in {"bar", "line"}:
        raise ValueError(kind)
    max_value = max((value for series in series_values for value in series), default=0)
    y_max = max(1, max_value + max(1, (max_value + 9) // 10))
    quoted_categories = ", ".join(f'"{_mermaid_text(label)}"' for label in categories)
    lines = [
        "```mermaid",
        "xychart",
        f'    title "{_mermaid_text(title)}"',
        f"    x-axis [{quoted_categories}]",
        f'    y-axis "数量" 0 --> {y_max}',
    ]
    for values in series_values:
        serialized = ", ".join(str(value) for value in values)
        lines.append(f"    {kind} [{serialized}]")
    lines.append("```")
    return "\n".join(lines)


def _daily_long_table(
    dimension_name: str,
    dates: Sequence[date],
    values: Mapping[date, Counter[str]],
) -> str:
    rows: list[tuple[object, ...]] = []
    for day in dates:
        for label, count in _sorted_counter(values.get(day, Counter())):
            if count > 0:
                rows.append((day.isoformat(), label, count))
    return _markdown_table(("日期", dimension_name, "数量"), rows)


def _mermaid_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'").replace("\n", " ")


def _format_generated_at(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(_BEIJING)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
