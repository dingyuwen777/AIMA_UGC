"""把报告图表规格渲染为可嵌入 Word 的 PNG。"""

from __future__ import annotations

import binascii
import math
import struct
import zlib
from dataclasses import dataclass
from typing import Final

_PALETTE: Final = (
    (40, 116, 166),
    (238, 154, 0),
    (90, 167, 76),
    (213, 94, 0),
    (156, 117, 95),
    (130, 130, 130),
    (187, 100, 178),
    (23, 190, 207),
    (255, 127, 14),
    (44, 160, 44),
    (214, 39, 40),
    (148, 103, 189),
)


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """Word 图表渲染所需的最小中间结构。"""

    kind: str
    title: str
    categories: tuple[str, ...]
    series: tuple[tuple[float, ...], ...]
    pie_labels: tuple[str, ...] = ()
    y_min: float = 0.0
    y_max: float | None = None


def render_chart_png(spec: ChartSpec) -> tuple[bytes, int, int]:
    """把受支持图表规格渲染成无外部字体依赖的 RGB PNG。"""

    canvas = _Canvas(1200, 640)
    if spec.kind == "pie":
        _draw_pie(canvas, spec)
    elif spec.kind == "bar":
        _draw_bar(canvas, spec)
    elif spec.kind == "line":
        _draw_line(canvas, spec)
    else:
        raise ValueError(f"不支持的图表类型: {spec.kind}")
    return canvas.to_png(), canvas.width, canvas.height


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray([255]) * (width * height * 3)

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = (y * self.width + x) * 3
        self.pixels[offset : offset + 3] = bytes(color)

    def fill_rect(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
    ) -> None:
        x0, x1 = sorted((max(0, x0), min(self.width, x1)))
        y0, y1 = sorted((max(0, y0), min(self.height, y1)))
        span = bytes(color) * max(0, x1 - x0)
        for y in range(y0, y1):
            offset = (y * self.width + x0) * 3
            self.pixels[offset : offset + len(span)] = span

    def line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
        *,
        thickness: int = 2,
    ) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        error = dx + dy
        radius = max(0, thickness // 2)
        while True:
            self.fill_rect(
                x0 - radius,
                y0 - radius,
                x0 + radius + 1,
                y0 + radius + 1,
                color,
            )
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * error
            if e2 >= dy:
                error += dy
                x0 += sx
            if e2 <= dx:
                error += dx
                y0 += sy

    def circle(self, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        rr = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            dy = y - cy
            limit = int(math.sqrt(max(0, rr - dy * dy)))
            self.fill_rect(cx - limit, y, cx + limit + 1, y + 1, color)

    def to_png(self) -> bytes:
        raw = bytearray()
        row_size = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * row_size
            raw.extend(self.pixels[start : start + row_size])
        return b"".join(
            (
                b"\x89PNG\r\n\x1a\n",
                _png_chunk(
                    b"IHDR",
                    struct.pack(
                        ">IIBBBBB",
                        self.width,
                        self.height,
                        8,
                        2,
                        0,
                        0,
                        0,
                    ),
                ),
                _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=6)),
                _png_chunk(b"IEND", b""),
            )
        )


def _draw_plot_frame(canvas: _Canvas) -> tuple[int, int, int, int]:
    left, top, right, bottom = 90, 45, canvas.width - 45, canvas.height - 70
    grid = (225, 230, 235)
    axis = (80, 90, 100)
    for step in range(6):
        y = top + int((bottom - top) * step / 5)
        canvas.line(left, y, right, y, grid, thickness=1)
    canvas.line(left, top, left, bottom, axis, thickness=2)
    canvas.line(left, bottom, right, bottom, axis, thickness=2)
    return left, top, right, bottom


def _draw_line(canvas: _Canvas, spec: ChartSpec) -> None:
    left, top, right, bottom = _draw_plot_frame(canvas)
    y_min, y_max = _resolved_y_range(spec)
    count = len(spec.categories)
    x_positions = [left + int((right - left) * index / max(1, count - 1)) for index in range(count)]
    for series_index, values in enumerate(spec.series):
        color = _PALETTE[series_index % len(_PALETTE)]
        points: list[tuple[int, int]] = []
        for x, value in zip(x_positions, values, strict=True):
            y = _value_to_y(value, y_min, y_max, top, bottom)
            points.append((x, y))
        for first, second in zip(points, points[1:], strict=False):
            canvas.line(*first, *second, color, thickness=4)
        for x, y in points:
            canvas.circle(x, y, 5, color)


def _draw_bar(canvas: _Canvas, spec: ChartSpec) -> None:
    left, top, right, bottom = _draw_plot_frame(canvas)
    y_min, y_max = _resolved_y_range(spec)
    values = spec.series[0]
    count = len(values)
    slot = (right - left) / max(1, count)
    bar_width = max(8, int(slot * 0.62))
    for index, value in enumerate(values):
        center = left + int(slot * (index + 0.5))
        y = _value_to_y(value, y_min, y_max, top, bottom)
        color = _PALETTE[index % len(_PALETTE)]
        canvas.fill_rect(
            center - bar_width // 2,
            y,
            center + bar_width // 2,
            bottom,
            color,
        )


def _draw_pie(canvas: _Canvas, spec: ChartSpec) -> None:
    values = spec.series[0]
    total = sum(max(0.0, value) for value in values)
    if total <= 0:
        _draw_plot_frame(canvas)
        return
    cx, cy, radius = 430, canvas.height // 2, 230
    cumulative: list[float] = []
    running = 0.0
    for value in values:
        running += max(0.0, value) / total * math.tau
        cumulative.append(running)
    rr = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        dy = y - cy
        for x in range(cx - radius, cx + radius + 1):
            dx = x - cx
            if dx * dx + dy * dy > rr:
                continue
            angle = math.atan2(dy, dx)
            if angle < 0:
                angle += math.tau
            slice_index = 0
            while slice_index < len(cumulative) - 1 and angle > cumulative[slice_index]:
                slice_index += 1
            canvas.set_pixel(x, y, _PALETTE[slice_index % len(_PALETTE)])

    # 图内只保留颜色顺序；文字图例由 Word 表格承载，避免依赖本机中文字库。
    box_x = 760
    for index in range(min(len(values), 12)):
        y = 105 + index * 38
        canvas.fill_rect(
            box_x,
            y,
            box_x + 30,
            y + 22,
            _PALETTE[index % len(_PALETTE)],
        )
        canvas.fill_rect(box_x + 42, y + 7, 1110, y + 13, (215, 220, 225))


def _resolved_y_range(spec: ChartSpec) -> tuple[float, float]:
    values = [value for series in spec.series for value in series]
    data_max = max(values, default=1.0)
    y_min = spec.y_min
    y_max = spec.y_max if spec.y_max is not None else max(1.0, data_max)
    if y_max <= y_min:
        y_max = y_min + 1.0
    return y_min, y_max


def _value_to_y(
    value: float,
    y_min: float,
    y_max: float,
    top: int,
    bottom: int,
) -> int:
    ratio = (value - y_min) / (y_max - y_min)
    ratio = min(1.0, max(0.0, ratio))
    return bottom - int((bottom - top) * ratio)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind)
    crc = binascii.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)
