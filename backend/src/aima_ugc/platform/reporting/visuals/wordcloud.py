"""把词频映射确定性渲染为克制的中文 Editorial Word Cloud PNG。"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .theme import ACCENT_BLUE, SECONDARY_TEXT_COLOR, TITLE_COLOR

_CANVAS_SIZE: Final = (1600, 900)
_MIN_FONT_SIZE: Final = 26
_MAX_FONT_SIZE: Final = 122
_MAX_WORDS: Final = 36
_PADDING: Final = 14
_OUTPUT_MARGIN: Final = 72
_MAX_FOCUS_SCALE: Final = 1.75
# 主体仍然使用蓝/蓝灰；少量青绿、柔紫和赭色只负责拉开层级，不做彩虹词云。
_PALETTE: Final = (
    TITLE_COLOR,
    ACCENT_BLUE,
    "238C8C",
    "6F6AA8",
    "56748D",
    "7C8A9A",
    "C47A32",
)


def render_wordcloud_png(frequencies: Mapping[str, int], output_path: Path) -> Path:
    """按 sqrt 权重渲染稳定水平词云；无可用中文字体时明确失败。"""

    items = [
        (str(label).strip(), int(count))
        for label, count in frequencies.items()
        if str(label).strip() and int(count) > 0
    ]
    items.sort(key=lambda item: (-item[1], item[0]))
    items = items[:_MAX_WORDS]
    font_path = resolve_cjk_font()
    bold_font_path = resolve_cjk_bold_font(font_path)
    image = Image.new("RGB", _CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(image)
    if not items:
        font = ImageFont.truetype(str(font_path), 48)
        message = "暂无可展示数据"
        bbox = draw.textbbox((0, 0), message, font=font)
        draw.text(
            (
                (_CANVAS_SIZE[0] - (bbox[2] - bbox[0])) / 2,
                (_CANVAS_SIZE[1] - (bbox[3] - bbox[1])) / 2,
            ),
            message,
            fill=f"#{SECONDARY_TEXT_COLOR}",
            font=font,
        )
        return _save_png(image, output_path)

    placed: list[tuple[int, int, int, int]] = []
    weights = [math.sqrt(count) for _, count in items]
    low, high = min(weights), max(weights)
    for rank, ((label, _count), weight) in enumerate(zip(items, weights, strict=True)):
        font_size = _font_size(weight, low=low, high=high, rank=rank)
        placement: (
            tuple[
                int,
                int,
                ImageFont.FreeTypeFont,
                tuple[int, int, int, int],
                tuple[int, int, int, int],
            ]
            | None
        ) = None
        for candidate_size in range(font_size, _MIN_FONT_SIZE - 1, -3):
            selected_font = bold_font_path if rank == 0 else font_path
            font = ImageFont.truetype(str(selected_font), candidate_size)
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = int(math.ceil(bbox[2] - bbox[0]))
            text_height = int(math.ceil(bbox[3] - bbox[1]))
            position = _find_position(text_width, text_height, placed)
            if position is None:
                continue
            x, y = position
            rect = (
                x - _PADDING,
                y - _PADDING,
                x + text_width + _PADDING,
                y + text_height + _PADDING,
            )
            placement = (x, y, font, bbox, rect)
            break
        if placement is None:
            continue
        x, y, font, bbox, rect = placement
        # textbbox 的 left/top 不一定为 0；把实际字形框锚定到布局矩形，避免大字号词互相压住。
        draw.text(
            (x - bbox[0], y - bbox[1]),
            label,
            fill=f"#{_color_for_rank(rank)}",
            font=font,
        )
        placed.append(rect)

    if not placed:
        raise RuntimeError("词云布局失败：没有任何词条可放入画布")
    focused = _focus_content(image)
    image.close()
    return _save_png(focused, output_path)


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


def resolve_cjk_bold_font(fallback: Path) -> Path:
    """优先为首要词寻找同族粗体；缺失时退回已验证可用的常规 CJK 字体。"""

    for path in _candidate_bold_font_paths():
        if path.is_file():
            return path
    return fallback


def _candidate_font_paths() -> tuple[Path, ...]:
    return (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/opentype/adobe-source-han-sans/SourceHanSansSC-Regular.otf"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )


def _candidate_bold_font_paths() -> tuple[Path, ...]:
    return (
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf"),
        Path("/usr/share/fonts/opentype/adobe-source-han-sans/SourceHanSansSC-Bold.otf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )


def _font_size(weight: float, *, low: float, high: float, rank: int) -> int:
    if high <= low:
        size = 64
    else:
        ratio = (weight - low) / (high - low)
        # sqrt 已经压缩极端频次；再用温和曲线，避免第一名吞掉整幅图。
        ratio = math.pow(ratio, 0.72)
        size = round(_MIN_FONT_SIZE + ratio * (_MAX_FONT_SIZE - _MIN_FONT_SIZE))
    if rank == 0:
        return max(size, 112)
    if rank == 1:
        return max(size, 72)
    if rank == 2:
        return max(size, 64)
    return size


def _color_for_rank(rank: int) -> str:
    if rank == 0:
        return _PALETTE[0]
    # 暖色只在少数次级词出现，避免蓝灰单调但不让颜色抢过信息层级。
    if rank in {4, 12, 23}:
        return _PALETTE[-1]
    cool_palette = _PALETTE[1:-1]
    return cool_palette[(rank * 2) % len(cool_palette)]


def _find_position(
    width: int,
    height: int,
    placed: list[tuple[int, int, int, int]],
) -> tuple[int, int] | None:
    canvas_width, canvas_height = _CANVAS_SIZE
    cx = canvas_width // 2
    cy = canvas_height // 2
    # 每个词都从视觉中心重新寻找最近空位，而不是按词序强制向外推。
    # 这样 5~12 个词也会形成有意图的紧凑簇，不会散成一圈显得廉价。
    for step in range(1700):
        angle = step * 0.52
        radius = 2 + step * 0.64
        x = round(cx + math.cos(angle) * radius - width / 2)
        y = round(cy + math.sin(angle) * radius * 0.54 - height / 2)
        rect = (
            x - _PADDING,
            y - _PADDING,
            x + width + _PADDING,
            y + height + _PADDING,
        )
        if (
            rect[0] < 22
            or rect[1] < 22
            or rect[2] > canvas_width - 22
            or rect[3] > canvas_height - 22
        ):
            continue
        if all(not _intersects(rect, other) for other in placed):
            return x, y
    return None


def _focus_content(image: Image.Image) -> Image.Image:
    """把紧凑词簇放大到稳定画布，避免少词词云被巨大空白包围。"""

    white = Image.new("RGB", image.size, "white")
    difference = ImageChops.difference(image, white).convert("L")
    bbox = difference.getbbox()
    white.close()
    difference.close()
    if bbox is None:
        return image.copy()

    left, top, right, bottom = bbox
    crop_padding = 32
    crop = image.crop(
        (
            max(0, left - crop_padding),
            max(0, top - crop_padding),
            min(image.width, right + crop_padding),
            min(image.height, bottom + crop_padding),
        )
    )
    target_width = _CANVAS_SIZE[0] - 2 * _OUTPUT_MARGIN
    target_height = _CANVAS_SIZE[1] - 2 * _OUTPUT_MARGIN
    scale = min(target_width / crop.width, target_height / crop.height, _MAX_FOCUS_SCALE)
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    crop.close()
    canvas = Image.new("RGB", _CANVAS_SIZE, "white")
    x = (_CANVAS_SIZE[0] - resized.width) // 2
    y = (_CANVAS_SIZE[1] - resized.height) // 2
    canvas.paste(resized, (x, y))
    resized.close()
    return canvas


def _intersects(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    return not (
        first[2] <= second[0]
        or first[0] >= second[2]
        or first[3] <= second[1]
        or first[1] >= second[3]
    )
