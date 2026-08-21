"""报告 Markdown 与 Word 图表之间的 Provider-neutral 中间结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """本报告支持的最小图表规格。"""

    kind: str
    title: str
    categories: tuple[str, ...]
    series: tuple[tuple[float, ...], ...]
    series_names: tuple[str, ...] = ()
    pie_labels: tuple[str, ...] = ()
    y_min: float = 0.0
    y_max: float | None = None
    bar_direction: str = "col"
