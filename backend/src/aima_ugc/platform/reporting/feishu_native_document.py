"""把当前报告 Markdown 投影为飞书原生文档所需的顺序化内容块。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .chart_spec import ChartSpec

_FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.+)$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
_AIMA_COMMENT_RE = re.compile(r"^<!--\s*aima:[a-z0-9_-]+=[a-z0-9_-]+\s*-->$", re.IGNORECASE)
_AIMA_TABLE_STYLE_RE = re.compile(
    r"^<!--\s*aima:table-style=([a-z0-9_-]+)\s*-->$", re.IGNORECASE
)
_AIMA_LAYOUT_RE = re.compile(r"^<!--\s*aima:layout=([a-z0-9_-]+)\s*-->$", re.IGNORECASE)
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_COMPACT_DAILY_DIMENSIONS_PER_TABLE = 5


@dataclass(frozen=True, slots=True)
class FeishuNativeBlock:
    """一个按 Markdown 原顺序发布的飞书内容单元。"""

    kind: str
    text: str = ""
    level: int | None = None
    rows: tuple[tuple[str, ...], ...] = ()
    image_path: Path | None = None
    chart_index: int | None = None


@dataclass(frozen=True, slots=True)
class FeishuNativeDocument:
    """飞书原生重建输入；图表引用既有 Report Context 的规格，不重新统计。"""

    markdown_path: Path
    blocks: tuple[FeishuNativeBlock, ...]
    chart_specs: tuple[ChartSpec, ...]


def build_feishu_native_document(
    markdown_path: Path,
    chart_specs: tuple[ChartSpec, ...],
) -> FeishuNativeDocument:
    """解析项目受支持的报告 Markdown，而非实现通用 Markdown 渲染器。"""

    source = Path(markdown_path)
    if source.suffix.lower() != ".md":
        raise ValueError("飞书原生文档输入必须是 .md 文件")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not chart_specs:
        raise ValueError("飞书原生文档缺少报告图表规格")

    lines = source.read_text(encoding="utf-8").splitlines()
    blocks: list[FeishuNativeBlock] = []
    index = 0
    chart_index = 0
    table_style: str | None = None
    layout_style: str | None = None
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        style = _AIMA_TABLE_STYLE_RE.fullmatch(stripped)
        if style:
            table_style = style.group(1).lower()
            index += 1
            continue
        layout = _AIMA_LAYOUT_RE.fullmatch(stripped)
        if layout:
            layout_style = layout.group(1).lower()
            index += 1
            continue
        if _AIMA_COMMENT_RE.fullmatch(stripped):
            index += 1
            continue
        if (table_style is not None or layout_style is not None) and not _looks_like_table(
            lines, index
        ):
            raise ValueError("table-style 或 layout 后必须紧跟 Markdown 表格")
        fence = _FENCE_RE.match(line)
        if fence:
            content, index = _collect_fence(lines, index + 1)
            if fence.group(1).lower() == "mermaid":
                chart_index += 1
                if chart_index > len(chart_specs):
                    raise ValueError("报告 Markdown Mermaid 图表数量超过图表规格")
                blocks.append(FeishuNativeBlock(kind="chart", chart_index=chart_index))
            else:
                blocks.append(FeishuNativeBlock(kind="code", text=content))
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            blocks.append(
                FeishuNativeBlock(
                    kind="heading", text=heading.group(2).strip(), level=len(heading.group(1))
                )
            )
            index += 1
            continue
        image = _IMAGE_RE.match(stripped)
        if image:
            blocks.append(
                FeishuNativeBlock(
                    kind="image",
                    text=image.group(1).strip(),
                    image_path=_resolve_image(source.parent, image.group(2)),
                )
            )
            index += 1
            continue
        if _looks_like_table(lines, index):
            rows, index = _collect_table(lines, index)
            if table_style == "compact-daily":
                blocks.extend(
                    FeishuNativeBlock(kind="table", rows=matrix)
                    for matrix in _pivot_compact_daily_tables(rows)
                )
            elif layout_style in {"ranking-image-top8", "ranking-image-top10"}:
                top_n = 8 if layout_style.endswith("top8") else 10
                blocks.append(FeishuNativeBlock(kind="paragraph", text=f"Top {top_n}"))
                blocks.append(
                    FeishuNativeBlock(kind="table", rows=_ranking_top_table(rows, top_n=top_n))
                )
            else:
                blocks.append(FeishuNativeBlock(kind="table", rows=rows))
            table_style = None
            layout_style = None
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            blocks.append(FeishuNativeBlock(kind="bullet", text=bullet.group(1).strip()))
            index += 1
            continue
        numbered = _NUMBERED_RE.match(line)
        if numbered:
            blocks.append(FeishuNativeBlock(kind="numbered", text=numbered.group(0).strip()))
            index += 1
            continue
        if stripped == "---":
            blocks.append(FeishuNativeBlock(kind="divider"))
            index += 1
            continue
        if line.lstrip().startswith(">"):
            blocks.append(FeishuNativeBlock(kind="quote", text=line.lstrip()[1:].strip()))
            index += 1
            continue
        paragraph = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip() and not _starts_block(lines, index):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(FeishuNativeBlock(kind="paragraph", text=" ".join(paragraph)))

    if chart_index != len(chart_specs):
        raise ValueError("报告 Markdown Mermaid 图表数量与图表规格不一致")
    return FeishuNativeDocument(source, tuple(blocks), chart_specs)


def _collect_fence(lines: list[str], start: int) -> tuple[str, int]:
    collected: list[str] = []
    index = start
    while index < len(lines):
        if lines[index].strip() == "```":
            return "\n".join(collected), index + 1
        collected.append(lines[index])
        index += 1
    raise ValueError("Markdown 代码块没有闭合")


def _looks_like_table(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and "|" in lines[index]
        and bool(_TABLE_SEPARATOR_RE.match(lines[index + 1]))
    )


def _collect_table(lines: list[str], start: int) -> tuple[tuple[tuple[str, ...], ...], int]:
    rows = [_split_table_row(lines[start])]
    expected_width = len(rows[0])
    index = start + 2
    while index < len(lines) and lines[index].strip() and "|" in lines[index]:
        row = _split_table_row(lines[index])
        if len(row) != expected_width:
            raise ValueError("Markdown 表格列数不一致")
        rows.append(row)
        index += 1
    if expected_width < 1 or len(rows) < 2:
        raise ValueError("Markdown 表格必须包含表头和至少一行数据")
    return tuple(rows), index


def _split_table_row(line: str) -> tuple[str, ...]:
    """拆分 Markdown 表格行，并把空单元格投影为可显示的占位符。"""

    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return tuple(cell.strip() or "—" for cell in value.split("|"))


def _pivot_compact_daily_tables(
    rows: tuple[tuple[str, ...], ...],
) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """复用 Word 的首见顺序，将日期/维度/数量长表拆为最多五个维度的横向表。"""

    headers, *values = rows
    if len(headers) != 3 or not values:
        return (rows,)
    dates: list[str] = []
    dimensions: list[str] = []
    matrix_values: dict[tuple[str, str], str] = {}
    for day, dimension, value in values:
        if day not in dates:
            dates.append(day)
        if dimension not in dimensions:
            dimensions.append(dimension)
        matrix_values[(day, dimension)] = value
    if not dates or not dimensions:
        return (rows,)
    matrices: list[tuple[tuple[str, ...], ...]] = []
    for start in range(0, len(dimensions), _COMPACT_DAILY_DIMENSIONS_PER_TABLE):
        dimension_chunk = dimensions[start : start + _COMPACT_DAILY_DIMENSIONS_PER_TABLE]
        matrix_rows = [(headers[0], *dimension_chunk)]
        for day in dates:
            dimension_values = tuple(
                matrix_values.get((day, dimension), "—") for dimension in dimension_chunk
            )
            matrix_rows.append((day, *dimension_values))
        matrices.append(tuple(matrix_rows))
    return tuple(matrices)


def _ranking_top_table(
    rows: tuple[tuple[str, ...], ...], *, top_n: int
) -> tuple[tuple[str, ...], ...]:
    """投影 Word 的 Top Ranking：只保留同一排序的前 N 项，并显式写出排名列。"""

    headers, *values = rows
    if len(headers) < 3:
        return rows
    selected = values[:top_n]
    return (
        ("排名", *headers),
        *((f"{index:02d}", *value) for index, value in enumerate(selected, start=1)),
    )


def _starts_block(lines: list[str], index: int) -> bool:
    line = lines[index]
    return bool(
        _FENCE_RE.match(line)
        or _HEADING_RE.match(line)
        or _BULLET_RE.match(line)
        or _NUMBERED_RE.match(line)
        or _IMAGE_RE.match(line.strip())
        or _AIMA_COMMENT_RE.fullmatch(line.strip())
        or _looks_like_table(lines, index)
        or line.strip() == "---"
        or line.lstrip().startswith(">")
    )


def _resolve_image(asset_root: Path, raw_target: str) -> Path:
    target = raw_target.strip().strip("<>").strip()
    if not target or "://" in target or target.startswith("data:"):
        raise ValueError("飞书原生文档只支持报告目录内的本地 Markdown 图片")
    candidate = Path(target)
    if candidate.is_absolute():
        raise ValueError("飞书原生文档 Markdown 图片必须使用相对路径")
    root = asset_root.resolve()
    resolved = (root / candidate).resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise ValueError("飞书原生文档图片不存在或离开报告目录")
    return resolved
