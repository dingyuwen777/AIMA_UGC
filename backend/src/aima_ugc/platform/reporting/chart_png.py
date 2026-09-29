"""把报告图表规格渲染为适合飞书原生文档的高保真 PNG。"""

from __future__ import annotations

import math
from io import BytesIO
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from .chart_spec import ChartSpec
from .visuals.wordcloud import resolve_cjk_bold_font, resolve_cjk_font

_CANVAS_SIZE: Final = (1800, 1000)
_PALETTE: Final = (
    "#2F6FBE",
    "#7697C8",
    "#9BAEC7",
    "#5176A8",
    "#A6B5C9",
    "#D18A4B",
    "#5B9D83",
    "#8A77B6",
)
_GRID: Final = "#D9DEE7"
_AXIS: Final = "#667085"
_TEXT: Final = "#172033"


def render_chart_png(spec: ChartSpec) -> tuple[bytes, int, int]:
    """完整绘制标题、坐标轴、标签和图例，避免飞书图中只剩简化线条。"""

    if spec.kind not in {"pie", "bar", "line"}:
        raise ValueError(f"不支持的图表类型: {spec.kind}")
    if not spec.categories or not spec.series:
        raise ValueError("图表缺少分类或数据序列")
    if any(len(values) != len(spec.categories) for values in spec.series):
        raise ValueError("图表数据序列长度与分类数量不一致")

    font_path = resolve_cjk_font()
    bold_font_path = resolve_cjk_bold_font(font_path)
    image = Image.new("RGB", _CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(image)
    fonts = _Fonts(font_path, bold_font_path)
    _draw_title(draw, spec.title, fonts)
    if spec.kind == "pie":
        _draw_pie(draw, spec, fonts)
    elif spec.kind == "line":
        _draw_line(draw, spec, fonts)
    else:
        _draw_bar(draw, spec, fonts)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True, dpi=(240, 240))
    image.close()
    return output.getvalue(), *_CANVAS_SIZE


class _Fonts:
    """同一张图只创建所需字号，保证中文标签均由真实 CJK 字体绘制。"""

    def __init__(self, regular_path: object, bold_path: object) -> None:
        self.title = ImageFont.truetype(str(bold_path), 46)
        self.label = ImageFont.truetype(str(regular_path), 28)
        self.small = ImageFont.truetype(str(regular_path), 24)
        self.value = ImageFont.truetype(str(bold_path), 27)


def _draw_title(draw: ImageDraw.ImageDraw, title: str, fonts: _Fonts) -> None:
    draw.text((_CANVAS_SIZE[0] // 2, 54), title, fill=_TEXT, font=fonts.title, anchor="ma")


def _draw_line(draw: ImageDraw.ImageDraw, spec: ChartSpec, fonts: _Fonts) -> None:
    left, top, right, bottom, y_min, y_max = _draw_axes(draw, spec, fonts)
    count = len(spec.categories)
    positions = [left + round((right - left) * index / max(1, count - 1)) for index in range(count)]
    for series_index, values in enumerate(spec.series):
        color = _PALETTE[series_index % len(_PALETTE)]
        points = [
            (x, _value_to_y(value, y_min, y_max, top, bottom))
            for x, value in zip(positions, values, strict=True)
        ]
        draw.line(points, fill=color, width=8, joint="curve")
        for x, y in points:
            draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=color, outline="white", width=3)
        for (x, y), value in zip(points, values, strict=True):
            draw.text((x, y - 24), _format_number(value), fill=_TEXT, font=fonts.value, anchor="ms")
    _draw_x_labels(draw, spec.categories, positions, bottom, fonts)
    _draw_series_legend(draw, spec, fonts)


def _draw_bar(draw: ImageDraw.ImageDraw, spec: ChartSpec, fonts: _Fonts) -> None:
    if spec.bar_direction == "bar":
        _draw_horizontal_bar(draw, spec, fonts)
        return
    left, top, right, bottom, y_min, y_max = _draw_axes(draw, spec, fonts)
    count = len(spec.categories)
    series_count = len(spec.series)
    slot = (right - left) / max(1, count)
    group_width = min(slot * 0.76, 160)
    bar_width = max(10, round(group_width / series_count))
    positions: list[int] = []
    for category_index in range(count):
        center = left + round(slot * (category_index + 0.5))
        positions.append(center)
        for series_index, values in enumerate(spec.series):
            value = values[category_index]
            x0 = round(center - group_width / 2 + series_index * bar_width)
            x1 = x0 + bar_width - 4
            y = _value_to_y(value, y_min, y_max, top, bottom)
            color = _PALETTE[series_index % len(_PALETTE)]
            draw.rectangle((x0, y, x1, bottom), fill=color)
            draw.text(
                ((x0 + x1) // 2, y - 14),
                _format_number(value),
                fill=_TEXT,
                font=fonts.small,
                anchor="ms",
            )
    _draw_x_labels(draw, spec.categories, positions, bottom, fonts)
    _draw_series_legend(draw, spec, fonts)


def _draw_horizontal_bar(draw: ImageDraw.ImageDraw, spec: ChartSpec, fonts: _Fonts) -> None:
    """按 Word 的 barDir=bar 语义绘制横向排名条，类别从上到下排列而非挤在横轴。"""

    y_min, y_max = _resolved_y_range(spec)
    left, top, right, bottom = 510, 145, 1710, 860
    tick_values = [y_min + (y_max - y_min) * index / 5 for index in range(6)]
    for value in tick_values:
        x = left + round((right - left) * (value - y_min) / (y_max - y_min))
        draw.line((x, top, x, bottom), fill=_GRID, width=2)
        draw.text(
            (x, bottom + 22),
            _format_number(value),
            fill=_TEXT,
            font=fonts.small,
            anchor="ma",
        )
    draw.line((left, top, left, bottom), fill=_AXIS, width=3)
    draw.line((left, bottom, right, bottom), fill=_AXIS, width=3)

    category_count = len(spec.categories)
    series_count = len(spec.series)
    slot_height = (bottom - top) / max(1, category_count)
    group_height = min(slot_height * 0.72, 70)
    bar_height = max(8, round(group_height / series_count))
    for category_index, category in enumerate(spec.categories):
        center_y = top + round(slot_height * (category_index + 0.5))
        draw.text(
            (left - 22, center_y),
            _short_category_label(category),
            fill=_TEXT,
            font=fonts.small,
            anchor="rm",
        )
        for series_index, values in enumerate(spec.series):
            value = values[category_index]
            y0 = round(center_y - group_height / 2 + series_index * bar_height)
            y1 = y0 + bar_height - 3
            x = left + round((right - left) * (value - y_min) / (y_max - y_min))
            color = _PALETTE[series_index % len(_PALETTE)]
            draw.rectangle((left, y0, x, y1), fill=color)
            value_x = min(right - 8, x + 12)
            anchor = "lm" if value_x < right - 70 else "rm"
            draw.text(
                (value_x, (y0 + y1) // 2),
                _format_number(value),
                fill=_TEXT,
                font=fonts.small,
                anchor=anchor,
            )
    _draw_series_legend(draw, spec, fonts)


def _draw_axes(
    draw: ImageDraw.ImageDraw, spec: ChartSpec, fonts: _Fonts
) -> tuple[int, int, int, int, float, float]:
    y_min, y_max = _resolved_y_range(spec)
    tick_values = [y_min + (y_max - y_min) * index / 5 for index in range(6)]
    max_tick_width = max(
        _text_size(draw, _format_number(value), fonts.label)[0] for value in tick_values
    )
    left, top, right, bottom = max_tick_width + 72, 135, 1710, 825
    for value in tick_values:
        y = _value_to_y(value, y_min, y_max, top, bottom)
        draw.line((left, y, right, y), fill=_GRID, width=2)
        draw.text((left - 20, y), _format_number(value), fill=_TEXT, font=fonts.label, anchor="rm")
    draw.line((left, top, left, bottom), fill=_AXIS, width=3)
    draw.line((left, bottom, right, bottom), fill=_AXIS, width=3)
    return left, top, right, bottom, y_min, y_max


def _draw_x_labels(
    draw: ImageDraw.ImageDraw,
    labels: tuple[str, ...],
    positions: list[int],
    bottom: int,
    fonts: _Fonts,
) -> None:
    for label, x in zip(labels, positions, strict=True):
        draw.line((x, bottom, x, bottom + 12), fill=_AXIS, width=2)
        draw.text((x, bottom + 32), label, fill=_TEXT, font=fonts.label, anchor="ma")


def _draw_series_legend(draw: ImageDraw.ImageDraw, spec: ChartSpec, fonts: _Fonts) -> None:
    if len(spec.series) < 2:
        return
    names = spec.series_names or tuple(f"系列{index}" for index in range(1, len(spec.series) + 1))
    x = 1710
    for index, name in enumerate(names):
        y = 125 + index * 38
        draw.rectangle((x - 180, y, x - 156, y + 24), fill=_PALETTE[index % len(_PALETTE)])
        draw.text((x - 146, y + 12), name, fill=_TEXT, font=fonts.small, anchor="lm")


def _draw_pie(draw: ImageDraw.ImageDraw, spec: ChartSpec, fonts: _Fonts) -> None:
    values = spec.series[0]
    labels = spec.pie_labels or spec.categories
    total = sum(max(0.0, value) for value in values)
    if total <= 0:
        draw.text(
            (_CANVAS_SIZE[0] // 2, 500),
            "暂无可展示数据",
            fill=_AXIS,
            font=fonts.label,
            anchor="mm",
        )
        return
    center = (720, 540)
    radius = 300
    start = -90.0
    slices: list[tuple[float, float]] = []
    for value in values:
        sweep = max(0.0, value) / total * 360
        end = start + sweep
        slices.append((start, end))
        start = end
    box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    for index, (start_angle, end_angle) in enumerate(slices):
        draw.pieslice(
            box,
            start_angle,
            end_angle,
            fill=_PALETTE[index % len(_PALETTE)],
            outline="white",
            width=4,
        )
    for (start_angle, end_angle), label, value in zip(slices, labels, values, strict=True):
        angle = math.radians((start_angle + end_angle) / 2)
        line_start = (
            center[0] + math.cos(angle) * radius * 0.82,
            center[1] + math.sin(angle) * radius * 0.82,
        )
        line_end = (
            center[0] + math.cos(angle) * radius * 1.16,
            center[1] + math.sin(angle) * radius * 1.16,
        )
        draw.line((line_start, line_end), fill=_AXIS, width=2)
        anchor = "lm" if math.cos(angle) >= 0 else "rm"
        text_x = line_end[0] + (14 if anchor == "lm" else -14)
        draw.multiline_text(
            (text_x, line_end[1]),
            f"{label}\n{value / total:.2%}",
            fill=_TEXT,
            font=fonts.label,
            anchor=anchor,
            align="center",
            spacing=4,
        )
    legend_x, legend_y = 1310, 270
    for index, label in enumerate(labels):
        y = legend_y + index * 58
        draw.rectangle((legend_x, y, legend_x + 26, y + 26), fill=_PALETTE[index % len(_PALETTE)])
        draw.text((legend_x + 40, y + 13), label, fill=_TEXT, font=fonts.label, anchor="lm")


def _resolved_y_range(spec: ChartSpec) -> tuple[float, float]:
    values = [value for series in spec.series for value in series]
    data_max = max(values, default=1.0)
    y_min = min(spec.y_min, 0.0)
    requested_max = spec.y_max if spec.y_max is not None else data_max
    y_max = _nice_upper_bound(max(requested_max, data_max))
    if y_max <= y_min:
        y_max = y_min + 1.0
    return y_min, y_max


def _nice_upper_bound(value: float) -> float:
    if value <= 1:
        return 1.0
    magnitude = 10.0 ** math.floor(math.log10(value))
    return math.ceil(value / magnitude) * magnitude


def _value_to_y(value: float, y_min: float, y_max: float, top: int, bottom: int) -> int:
    ratio = min(1.0, max(0.0, (value - y_min) / (y_max - y_min)))
    return bottom - round((bottom - top) * ratio)


def _format_number(value: float) -> str:
    if math.isclose(value, round(value)):
        return f"{round(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _short_category_label(value: str) -> str:
    """横向排名图给左侧标签留出稳定宽度，避免长标签压到绘图区。"""

    return value if len(value) <= 20 else f"{value[:19]}…"


def _text_size(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
