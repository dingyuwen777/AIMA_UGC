"""把词频映射确定性渲染为克制的中文 Editorial Word Cloud PNG。"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from .theme import ACCENT_BLUE, SECONDARY_TEXT_COLOR, TITLE_COLOR

_CANVAS_SIZE: Final = (1600, 900)
_MIN_FONT_SIZE: Final = 30
_MAX_FONT_SIZE: Final = 104
_PADDING: Final = 10
_COLORS: Final = (TITLE_COLOR, ACCENT_BLUE, SECONDARY_TEXT_COLOR)


def render_wordcloud_png(frequencies: Mapping[str, int], output_path: Path) -> Path:
    """按 sqrt 权重渲染稳定水平词云；无可用中文字体时明确失败。"""

    items = [(str(label).strip(), int(count)) for label, count in frequencies.items() if str(label).strip() and int(count) > 0]
    items.sort(key=lambda item: (-item[1], item[0]))
    font_path = resolve_cjk_font()
    image = Image.new("RGB", _CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(image)
    if not items:
        font = ImageFont.truetype(str(font_path), 48)
        message = "暂无可展示数据"
        bbox = draw.textbbox((0, 0), message, font=font)
        draw.text(
            ((_CANVAS_SIZE[0] - (bbox[2] - bbox[0])) / 2, (_CANVAS_SIZE[1] - (bbox[3] - bbox[1])) / 2),
            message,
            fill=f"#{SECONDARY_TEXT_COLOR}",
            font=font,
        )
        return _save_png(image, output_path)

    placed: list[tuple[int, int, int, int]] = []
    weights = [math.sqrt(count) for _, count in items]
    low, high = min(weights), max(weights)
    for rank, ((label, _count), weight) in enumerate(zip(items, weights, strict=True)):
        font_size = _font_size(weight, low=low, high=high)
        placement = None
        for candidate_size in range(font_size, _MIN_FONT_SIZE - 1, -4):
            font = ImageFont.truetype(str(font_path), candidate_size)
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            placement = _find_position(text_width, text_height, placed)
            if placement is not None:
                break
        if placement is None:
            continue
        x, y = placement
        color = _COLORS[min(rank * len(_COLORS) // max(1, len(items)), len(_COLORS) - 1)]
        draw.text((x, y), label, fill=f"#{color}", font=font)
        placed.append((x - _PADDING, y - _PADDING, x + text_width + _PADDING, y + text_height + _PADDING))

    if not placed:
        raise RuntimeError("词云布局失败：没有任何词条可放入画布")
    return _save_png(image, output_path)


def _save_png(image: Image.Image, output_path: Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True, dpi=(300, 300))
    image.close()
    return target


def resolve_cjk_font() -> Path:
    """解析系统 CJK 字体；不提交字体文件，也不静默使用缺字字体。"""

    configured = os.environ.get("AIMA_REPORT_CJK_FONT")
    candidates = ([Path(configured)] if configured else []) + list(_candidate_font_paths())
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError(
        "未找到可用中文字体。Windows 请安装/保留微软雅黑；Linux 请安装 Noto Sans CJK "
        "或 Source Han Sans，或通过 AIMA_REPORT_CJK_FONT 指向现有 CJK 字体文件。"
    )


def _candidate_font_paths() -> tuple[Path, ...]:
    return (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/opentype/adobe-source-han-sans/SourceHanSansSC-Regular.otf"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )


def _font_size(weight: float, *, low: float, high: float) -> int:
    if high <= low:
        return 64
    ratio = (weight - low) / (high - low)
    return round(_MIN_FONT_SIZE + ratio * (_MAX_FONT_SIZE - _MIN_FONT_SIZE))


def _find_position(width: int, height: int, placed: list[tuple[int, int, int, int]]) -> tuple[int, int] | None:
    canvas_width, canvas_height = _CANVAS_SIZE
    cx = canvas_width // 2
    cy = canvas_height // 2
    start_step = 0 if not placed else min(520, 72 * len(placed))
    for step in range(start_step, 900):
        angle = step * 0.58
        radius = 5 + step * 1.05
        x = round(cx + math.cos(angle) * radius - width / 2)
        y = round(cy + math.sin(angle) * radius * 0.56 - height / 2)
        rect = (x - _PADDING, y - _PADDING, x + width + _PADDING, y + height + _PADDING)
        if rect[0] < 22 or rect[1] < 22 or rect[2] > canvas_width - 22 or rect[3] > canvas_height - 22:
            continue
        if all(not _intersects(rect, other) for other in placed):
            return x, y
    return None


def _intersects(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> bool:
    return not (
        first[2] <= second[0]
        or first[0] >= second[2]
        or first[3] <= second[1]
        or first[1] >= second[3]
    )
