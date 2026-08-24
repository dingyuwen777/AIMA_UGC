"""内容人工相关性复核领域边界。"""

from __future__ import annotations

from dataclasses import dataclass


class ContentRelevanceReviewConflict(RuntimeError):
    """所选 Content 当前状态不允许请求的人工相关性操作。"""


@dataclass(frozen=True, slots=True)
class ContentRelevanceReviewWriteSummary:
    """一次原子人工相关性操作的写入结果。"""

    requested_count: int
    changed_count: int
    unchanged_count: int


__all__ = ["ContentRelevanceReviewConflict", "ContentRelevanceReviewWriteSummary"]
