"""AI 不相关内容的人工相关性复核领域边界。"""

from __future__ import annotations

from dataclasses import dataclass


class ContentRelevanceReviewConflict(RuntimeError):
    """所选 Content 当前不是可人工纳入的 AI irrelevant 状态。"""


@dataclass(frozen=True, slots=True)
class ContentRelevanceReviewWriteSummary:
    """一次原子人工复核写入结果。"""

    requested_count: int
    reviewed_count: int
    already_reviewed_count: int


__all__ = ["ContentRelevanceReviewConflict", "ContentRelevanceReviewWriteSummary"]
