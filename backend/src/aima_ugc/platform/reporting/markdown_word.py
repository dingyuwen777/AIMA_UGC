"""把本项目报告 Markdown 转为不依赖外部转换器的 DOCX。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .chart_png import ChartSpec
from .docx_package import DocxBuilder, verify_docx

_FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.+)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_PIE_ITEM_RE = re.compile(r'^\s*"(.*)"\s*:\s*(-?\d+(?:\.\d+)?)\s*$')
_XY_SERIES_RE = re.compile(r"^\s*(line|bar)\s*\[(.*)]\s*$")
_Y_AXIS_RE = re.compile(
    r'^\s*y-axis\s+"[^"]*"\s+(-?\d+(?:\.\d+)?)\s*-->\s*(-?\d+(?:\.\d+)?)\s*$'
)


@dataclass(frozen=True, slots=True)
class WordConversionSummary:
    """Markdown 转 DOCX 的最小可观察结果。"""

    markdown_path: Path
    output_path: Path
    paragraph_count: int
    table_count: int
    chart_count: int


def convert_markdown_to_docx(markdown_path: Path, output_path: Path) -> WordConversionSummary:
    """转换报告 Markdown；Mermaid 支持本报告使用的 pie/xychart。"""

    source = Path(markdown_path)
    target = Path(output_path)
    if source.suffix.lower() != ".md":
        raise ValueError("Word 转换输入必须是 .md 文件")
    if target.suffix.lower() != ".docx":
        raise ValueError("Word 转换输出必须是 .docx 文件")
    if not source.is_file():
        raise FileNotFoundError(source)

    builder = DocxBuilder()
    _parse_markdown(source.read_text(encoding="utf-8"), builder)
    target.parent.mkdir(parents=True, exist_ok=True)
    builder.save(target)
    verify_docx(target, expected_charts=builder.chart_count)
    return WordConversionSummary(
        markdown_path=source,
        output_path=target,
        paragraph_count=builder.paragraph_count,
        table_count=builder.table_count,
        chart_count=builder.chart_count,
    )


def _parse_markdown(markdown: str, builder: DocxBuilder) -> None:
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            language = fence.group(1).lower()
            block, index = _collect_fence(lines, index + 1)
            if language == "mermaid":
                builder.add_chart(_parse_mermaid(block))
            else:
                builder.add_code_block(block)
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            builder.add_paragraph(heading.group(2).strip(), style=f"Heading{level}")
            index += 1
            continue

        if line.lstrip().startswith(">"):
            builder.add_paragraph(line.lstrip()[1:].lstrip(), italic=True)
            index += 1
            continue

        if _looks_like_table(lines, index):
            headers, rows, index = _collect_table(lines, index)
            builder.add_table(headers, rows)
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            builder.add_paragraph("• " + bullet.group(1).strip())
            index += 1
            continue

        numbered = _NUMBERED_RE.match(line)
        if numbered:
            builder.add_paragraph(line.strip())
            index += 1
            continue

        if line.strip() == "---":
            builder.add_paragraph("―" * 24, align="center")
            index += 1
            continue

        paragraph_lines = [line.strip()]
        index += 1
        while (
            index < len(lines)
            and lines[index].strip()
            and not _starts_block(lines, index)
        ):
            paragraph_lines.append(lines[index].strip())
            index += 1
        builder.add_paragraph(" ".join(paragraph_lines))


def _collect_fence(lines: list[str], start: int) -> tuple[str, int]:
    block: list[str] = []
    index = start
    while index < len(lines):
        if lines[index].strip() == "```":
            return "\n".join(block), index + 1
        block.append(lines[index])
        index += 1
    raise ValueError("Markdown 代码块没有闭合")


def _looks_like_table(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and "|" in lines[index]
        and bool(_TABLE_SEPARATOR_RE.match(lines[index + 1]))
    )


def _collect_table(
    lines: list[str],
    start: int,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], int]:
    headers = _split_table_row(lines[start])
    index = start + 2
    rows: list[tuple[str, ...]] = []
    while index < len(lines) and lines[index].strip() and "|" in lines[index]:
        row = _split_table_row(lines[index])
        if len(row) != len(headers):
            raise ValueError("Markdown 表格列数不一致")
        rows.append(row)
        index += 1
    return headers, tuple(rows), index


def _split_table_row(line: str) -> tuple[str, ...]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return tuple(cells)


def _starts_block(lines: list[str], index: int) -> bool:
    line = lines[index]
    return bool(
        _FENCE_RE.match(line)
        or _HEADING_RE.match(line)
        or _BULLET_RE.match(line)
        or _NUMBERED_RE.match(line)
        or line.lstrip().startswith(">")
        or line.strip() == "---"
        or _looks_like_table(lines, index)
    )


def _parse_mermaid(block: str) -> ChartSpec:
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Mermaid 图表为空")
    first = lines[0].strip()
    if first.startswith("pie"):
        return _parse_mermaid_pie(lines)
    if first in {"xychart", "xychart-beta"}:
        return _parse_mermaid_xy(lines)
    raise ValueError(f"不支持的 Mermaid 图表类型: {first}")


def _parse_mermaid_pie(lines: list[str]) -> ChartSpec:
    title = ""
    labels: list[str] = []
    values: list[float] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("title "):
            title = stripped.removeprefix("title ").strip().strip('"')
            continue
        match = _PIE_ITEM_RE.match(line)
        if match:
            labels.append(match.group(1))
            values.append(float(match.group(2)))
            continue
        raise ValueError(f"无法解析 Mermaid pie 行: {stripped}")
    if not labels:
        raise ValueError("Mermaid pie 没有数据")
    return ChartSpec(
        kind="pie",
        title=title,
        categories=tuple(labels),
        series=(tuple(values),),
        pie_labels=tuple(labels),
    )


def _parse_mermaid_xy(lines: list[str]) -> ChartSpec:
    title = ""
    categories: tuple[str, ...] = ()
    series: list[tuple[float, ...]] = []
    kinds: set[str] = set()
    y_min = 0.0
    y_max: float | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("title "):
            title = stripped.removeprefix("title ").strip().strip('"')
            continue
        if stripped.startswith("x-axis "):
            raw = stripped.removeprefix("x-axis ").strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("无法解析 Mermaid x-axis") from exc
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("Mermaid x-axis 必须是字符串数组")
            categories = tuple(parsed)
            continue
        y_match = _Y_AXIS_RE.match(line)
        if y_match:
            y_min = float(y_match.group(1))
            y_max = float(y_match.group(2))
            continue
        series_match = _XY_SERIES_RE.match(line)
        if series_match:
            kinds.add(series_match.group(1))
            raw_values = [
                part.strip()
                for part in series_match.group(2).split(",")
                if part.strip()
            ]
            try:
                parsed_values = tuple(float(value) for value in raw_values)
            except ValueError as exc:
                raise ValueError("Mermaid xychart 序列包含非数字") from exc
            series.append(parsed_values)
            continue
        raise ValueError(f"无法解析 Mermaid xychart 行: {stripped}")
    if not categories or not series:
        raise ValueError("Mermaid xychart 缺少 x-axis 或数据序列")
    if len(kinds) != 1:
        raise ValueError("同一 Mermaid xychart 不支持混合 line/bar")
    if any(len(values) != len(categories) for values in series):
        raise ValueError("Mermaid xychart 序列长度与 x-axis 不一致")
    return ChartSpec(
        kind=next(iter(kinds)),
        title=title,
        categories=categories,
        series=tuple(series),
        y_min=y_min,
        y_max=y_max,
    )
