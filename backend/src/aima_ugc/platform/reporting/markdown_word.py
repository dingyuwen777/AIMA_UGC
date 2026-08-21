"""把本项目报告 Markdown 转为不依赖外部转换器的 DOCX。"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path

from .chart_spec import ChartSpec
from .docx_package import verify_docx
from .visual_docx import ReportDocxBuilder

_FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.+)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_PIE_ITEM_RE = re.compile(r'^\s*"(.*)"\s*:\s*(-?\d+(?:\.\d+)?)\s*$')
_XY_SERIES_RE = re.compile(r"^\s*(line|bar)\s*\[(.*)]\s*$")
_Y_AXIS_RE = re.compile(r'^\s*y-axis\s+"[^"]*"\s+(-?\d+(?:\.\d+)?)\s*-->\s*(-?\d+(?:\.\d+)?)\s*$')
_IMAGE_RE = re.compile(r"^!\[([^\]]*)]\(([^)]+)\)\s*$")
_AIMA_COMMENT_RE = re.compile(r"^<!--\s*aima:([a-z0-9_-]+)=([a-z0-9_-]+)\s*-->$", re.IGNORECASE)
_SERIES_META_PREFIX = "%% series "
_BAR_DIRECTION_META_PREFIX = "%% bar-direction "


@dataclass(frozen=True, slots=True)
class WordConversionSummary:
    """Markdown 转 DOCX 的最小可观察结果。"""

    markdown_path: Path
    output_path: Path
    paragraph_count: int
    table_count: int
    chart_count: int
    image_count: int = 0


def convert_markdown_to_docx(markdown_path: Path, output_path: Path) -> WordConversionSummary:
    """转换报告 Markdown；Mermaid 支持 pie 及 xychart/xychart-beta。"""

    source = Path(markdown_path)
    target = Path(output_path)
    if source.suffix.lower() != ".md":
        raise ValueError("Word 转换输入必须是 .md 文件")
    if target.suffix.lower() != ".docx":
        raise ValueError("Word 转换输出必须是 .docx 文件")
    if not source.is_file():
        raise FileNotFoundError(source)

    builder = ReportDocxBuilder()
    _parse_markdown(source.read_text(encoding="utf-8"), builder, asset_root=source.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    builder.save(target)
    verify_docx(
        target,
        expected_charts=builder.chart_count,
        expected_images=builder.image_count,
    )
    return WordConversionSummary(
        markdown_path=source,
        output_path=target,
        paragraph_count=builder.paragraph_count,
        table_count=builder.table_count,
        chart_count=builder.chart_count,
        image_count=builder.image_count,
    )


def _parse_markdown(markdown: str, builder: ReportDocxBuilder, *, asset_root: Path) -> None:
    lines = markdown.splitlines()
    index = 0
    table_style: str | None = None
    chart_presentation: str | None = None
    layout_style: str | None = None
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        metadata = _parse_aima_comment(line.strip())
        if metadata is not None:
            key, value = metadata
            if key == "table-style":
                if table_style is not None:
                    raise ValueError("连续 table-style 元数据没有对应 Markdown 表格")
                table_style = value
            elif key == "chart-presentation":
                if chart_presentation is not None:
                    raise ValueError("连续 chart-presentation 元数据没有对应 Mermaid 图表")
                chart_presentation = value
            elif key == "layout":
                if layout_style is not None:
                    raise ValueError("连续 layout 元数据没有对应视觉组合")
                layout_style = value
            else:
                raise ValueError(f"不支持的 AIMA Markdown 元数据: {key}")
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            if layout_style is not None:
                raise ValueError("layout 后必须紧跟其声明的 Markdown 视觉组合")
            language = fence.group(1).lower()
            block, index = _collect_fence(lines, index + 1)
            if language == "mermaid":
                spec = _parse_mermaid(block)
                _add_chart_with_presentation(builder, spec, chart_presentation)
                chart_presentation = None
            else:
                if chart_presentation is not None:
                    raise ValueError("chart-presentation 后必须紧跟 Mermaid 图表")
                builder.add_code_block(block)
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
            level = len(heading.group(1))
            builder.add_paragraph(heading.group(2).strip(), style=f"Heading{level}")
            index += 1
            continue

        image = _IMAGE_RE.match(line.strip())
        if image:
            _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
            image_path = _resolve_markdown_image(asset_root, image.group(2))
            builder.add_image(image_path, alt_text=image.group(1).strip())
            index += 1
            continue

        if line.lstrip().startswith(">"):
            _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
            builder.add_paragraph(line.lstrip()[1:].lstrip(), italic=True)
            index += 1
            continue

        if _looks_like_table(lines, index):
            if chart_presentation is not None:
                raise ValueError("chart-presentation 后必须紧跟 Mermaid 图表")
            headers, rows, after_table = _collect_table(lines, index)
            if layout_style is not None:
                index = _render_layout_table(
                    lines,
                    after_table,
                    builder=builder,
                    asset_root=asset_root,
                    layout_style=layout_style,
                    table_style=table_style,
                    headers=headers,
                    rows=rows,
                )
                table_style = None
                layout_style = None
                continue
            if table_style is None or table_style == "editorial":
                builder.add_table(headers, rows)
            elif table_style == "ranking":
                builder.add_ranking(headers, rows)
            elif table_style == "kpi":
                builder.add_kpi_table(headers, rows)
            elif table_style == "compact-daily":
                builder.add_compact_daily(headers, rows)
            else:
                raise ValueError(f"不支持的 Word 表格样式: {table_style}")
            table_style = None
            index = after_table
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
            builder.add_paragraph("• " + bullet.group(1).strip())
            index += 1
            continue

        numbered = _NUMBERED_RE.match(line)
        if numbered:
            _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
            builder.add_paragraph(line.strip())
            index += 1
            continue

        if line.strip() == "---":
            _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
            builder.add_separator()
            index += 1
            continue

        _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)
        paragraph_lines = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not _starts_block(lines, index):
            paragraph_lines.append(lines[index].strip())
            index += 1
        builder.add_paragraph(" ".join(paragraph_lines))

    _ensure_no_pending_metadata(table_style, chart_presentation, layout_style)


def _render_layout_table(
    lines: list[str],
    after_table: int,
    *,
    builder: ReportDocxBuilder,
    asset_root: Path,
    layout_style: str,
    table_style: str | None,
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
) -> int:
    if table_style != "ranking" and layout_style in {
        "primary-overview",
        "ranking-chart",
        "ranking-image",
    }:
        raise ValueError(f"{layout_style} 必须与 table-style=ranking 配合")
    visual_index = _next_nonempty_index(lines, after_table)
    if layout_style == "primary-overview":
        image, next_index = _consume_image(lines, visual_index, asset_root=asset_root)
        builder.add_primary_overview(
            headers,
            rows,
            image_path=image[0],
            alt_text=image[1],
        )
        return next_index
    if layout_style == "ranking-image":
        image, next_index = _consume_image(lines, visual_index, asset_root=asset_root)
        builder.add_ranking_visual(
            headers,
            rows,
            top_n=10,
            image_path=image[0],
            alt_text=image[1],
        )
        return next_index
    if layout_style == "ranking-chart":
        spec, next_index = _consume_mermaid(lines, visual_index)
        builder.add_ranking_visual(headers, rows, top_n=8, chart=spec)
        return next_index
    if layout_style == "table-chart":
        spec, next_index = _consume_mermaid(lines, visual_index)
        builder.add_table_visual(headers, rows, chart=spec)
        return next_index
    raise ValueError(f"不支持的 Word 组合布局: {layout_style}")


def _consume_image(
    lines: list[str],
    index: int,
    *,
    asset_root: Path,
) -> tuple[tuple[Path, str], int]:
    if index >= len(lines):
        raise ValueError("组合布局缺少 Markdown 图片")
    image = _IMAGE_RE.match(lines[index].strip())
    if image is None:
        raise ValueError("组合布局要求表格后紧跟 Markdown 图片")
    return (
        (_resolve_markdown_image(asset_root, image.group(2)), image.group(1).strip()),
        index + 1,
    )


def _consume_mermaid(lines: list[str], index: int) -> tuple[ChartSpec, int]:
    if index >= len(lines):
        raise ValueError("组合布局缺少 Mermaid 图表")
    fence = _FENCE_RE.match(lines[index])
    if fence is None or fence.group(1).lower() != "mermaid":
        raise ValueError("组合布局要求表格后紧跟 Mermaid 图表")
    block, next_index = _collect_fence(lines, index + 1)
    return _parse_mermaid(block), next_index


def _next_nonempty_index(lines: list[str], start: int) -> int:
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _parse_aima_comment(line: str) -> tuple[str, str] | None:
    match = _AIMA_COMMENT_RE.fullmatch(line)
    if match is None:
        return None
    return match.group(1).lower(), match.group(2).lower()


def _ensure_no_pending_metadata(
    table_style: str | None,
    chart_presentation: str | None,
    layout_style: str | None,
) -> None:
    if table_style is not None:
        raise ValueError("table-style 后必须紧跟 Markdown 表格")
    if chart_presentation is not None:
        raise ValueError("chart-presentation 后必须紧跟 Mermaid 图表")
    if layout_style is not None:
        raise ValueError("layout 后必须紧跟其声明的 Markdown 视觉组合")


def _resolve_markdown_image(asset_root: Path, raw_target: str) -> Path:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not target:
        raise ValueError("Markdown 图片路径为空")
    if "://" in target or target.startswith("data:"):
        raise ValueError("Word 报告不支持远程或 data: Markdown 图片")
    candidate = Path(target)
    if candidate.is_absolute():
        raise ValueError("Word 报告 Markdown 图片必须使用相对路径")
    root = asset_root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("Markdown 图片路径不能离开报告目录")
    return resolved


def _add_chart_with_presentation(
    builder: ReportDocxBuilder,
    spec: ChartSpec,
    presentation: str | None,
) -> None:
    if presentation is None or presentation == "default":
        builder.add_chart(spec)
        return
    if spec.kind != "line":
        raise ValueError(f"{presentation} 仅支持折线图")
    if presentation == "sentiment-split":
        _add_sentiment_split(builder, spec)
        return
    if presentation == "dominant-split":
        _add_dominant_split(builder, spec)
        return
    raise ValueError(f"不支持的 Word 图表展示方式: {presentation}")


def _add_sentiment_split(builder: ReportDocxBuilder, spec: ChartSpec) -> None:
    names = spec.series_names or tuple(f"系列 {index}" for index in range(1, len(spec.series) + 1))
    main_names = {"正面", "中性"}
    low_names = {"负面", "混合"}
    main_indices = [index for index, name in enumerate(names) if name in main_names]
    low_indices = [index for index, name in enumerate(names) if name in low_names]
    other_indices = [
        index
        for index, name in enumerate(names)
        if name not in main_names and name not in low_names
    ]
    main_indices.extend(other_indices)
    groups = (("主趋势", main_indices), ("低量级趋势", low_indices))
    rendered = 0
    for suffix, indices in groups:
        if _add_compact_group(builder, spec, names, suffix, indices):
            rendered += 1
    if rendered == 0:
        builder.add_chart(spec)


def _add_dominant_split(builder: ReportDocxBuilder, spec: ChartSpec) -> None:
    names = spec.series_names or tuple(f"系列 {index}" for index in range(1, len(spec.series) + 1))
    active = [
        index for index, values in enumerate(spec.series) if any(value != 0 for value in values)
    ]
    if len(active) <= 4:
        builder.add_compact_chart(spec)
        return
    groups: list[tuple[str, list[int]]] = [("主序列", [active[0]])]
    remainder = active[1:]
    for start in range(0, len(remainder), 4):
        chunk = remainder[start : start + 4]
        groups.append((f"次序列 {start // 4 + 1}", chunk))
    for suffix, indices in groups:
        _add_compact_group(builder, spec, names, suffix, indices)


def _add_compact_group(
    builder: ReportDocxBuilder,
    spec: ChartSpec,
    names: tuple[str, ...],
    suffix: str,
    indices: list[int],
) -> bool:
    if not indices:
        return False
    group_series = tuple(spec.series[index] for index in indices)
    if not any(any(value != 0 for value in values) for values in group_series):
        return False
    group_names = tuple(names[index] for index in indices)
    max_value = max((value for values in group_series for value in values), default=0.0)
    y_max = max(1.0, max_value + max(1.0, math.ceil(max(0.0, max_value) / 10.0)))
    builder.add_compact_chart(
        replace(
            spec,
            title=f"{spec.title} · {suffix}",
            series=group_series,
            series_names=group_names,
            y_max=y_max,
        )
    )
    return True


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
        or _IMAGE_RE.match(line.strip())
        or _AIMA_COMMENT_RE.fullmatch(line.strip())
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
        if stripped.startswith("%%"):
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
        series_names=("数量",),
        pie_labels=tuple(labels),
    )


def _parse_mermaid_xy(lines: list[str]) -> ChartSpec:
    title = ""
    categories: tuple[str, ...] = ()
    series: list[tuple[float, ...]] = []
    kinds: set[str] = set()
    series_names: tuple[str, ...] = ()
    y_min = 0.0
    y_max: float | None = None
    bar_direction: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("title "):
            title = stripped.removeprefix("title ").strip().strip('"')
            continue
        if stripped.startswith(_SERIES_META_PREFIX):
            raw = stripped.removeprefix(_SERIES_META_PREFIX).strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("无法解析 Mermaid series 元数据") from exc
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("Mermaid series 元数据必须是字符串数组")
            series_names = tuple(parsed)
            continue
        if stripped.startswith(_BAR_DIRECTION_META_PREFIX):
            value = stripped.removeprefix(_BAR_DIRECTION_META_PREFIX).strip().lower()
            if value not in {"horizontal", "vertical"}:
                raise ValueError("Mermaid bar-direction 只支持 horizontal 或 vertical")
            bar_direction = "bar" if value == "horizontal" else "col"
            continue
        if stripped.startswith("%%"):
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
            raw_values = [part.strip() for part in series_match.group(2).split(",") if part.strip()]
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
    if series_names and len(series_names) != len(series):
        raise ValueError("Mermaid series 名称数量与数据序列数量不一致")
    if not series_names:
        series_names = tuple(f"系列 {index}" for index in range(1, len(series) + 1))
    kind = next(iter(kinds))
    if bar_direction is not None and kind != "bar":
        raise ValueError("bar-direction 只能用于 bar 图表")
    return ChartSpec(
        kind=kind,
        title=title,
        categories=categories,
        series=tuple(series),
        series_names=series_names,
        y_min=y_min,
        y_max=y_max,
        bar_direction=(
            bar_direction if bar_direction is not None else ("bar" if kind == "bar" else "col")
        ),
    )
