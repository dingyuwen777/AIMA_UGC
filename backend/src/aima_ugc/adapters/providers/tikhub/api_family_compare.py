"""TikHub 同业务 API family 的稳定 ID 集合比较。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiFamilySetComparison:
    """一次主接口与候选接口的结果集合比较，不包含 Provider 私有字段。"""

    primary_count: int
    candidate_count: int
    primary_unique_count: int
    candidate_unique_count: int
    primary_duplicate_count: int
    candidate_duplicate_count: int
    shared_count: int
    primary_only_count: int
    candidate_only_count: int
    union_count: int
    jaccard: float | None
    same_unique_content: bool
    shared_ids: tuple[str, ...]
    primary_only_ids: tuple[str, ...]
    candidate_only_ids: tuple[str, ...]


def compare_stable_ids(
    *,
    primary_ids: Iterable[str],
    candidate_ids: Iterable[str],
) -> ApiFamilySetComparison:
    """比较两套 API 的稳定内容/评论 ID；空并集保持 inconclusive，不伪装成完全一致。"""
    primary = _normalized_ids(primary_ids)
    candidate = _normalized_ids(candidate_ids)
    primary_set = set(primary)
    candidate_set = set(candidate)

    shared = tuple(sorted(primary_set & candidate_set))
    primary_only = tuple(sorted(primary_set - candidate_set))
    candidate_only = tuple(sorted(candidate_set - primary_set))
    union_count = len(primary_set | candidate_set)
    jaccard = len(shared) / union_count if union_count else None

    return ApiFamilySetComparison(
        primary_count=len(primary),
        candidate_count=len(candidate),
        primary_unique_count=len(primary_set),
        candidate_unique_count=len(candidate_set),
        primary_duplicate_count=len(primary) - len(primary_set),
        candidate_duplicate_count=len(candidate) - len(candidate_set),
        shared_count=len(shared),
        primary_only_count=len(primary_only),
        candidate_only_count=len(candidate_only),
        union_count=union_count,
        jaccard=jaccard,
        same_unique_content=union_count > 0 and primary_set == candidate_set,
        shared_ids=shared,
        primary_only_ids=primary_only,
        candidate_only_ids=candidate_only,
    )


def _normalized_ids(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        text = value.strip()
        if not text:
            raise ValueError("stable ID 不能为空")
        normalized.append(text)
    return tuple(normalized)


__all__ = ["ApiFamilySetComparison", "compare_stable_ids"]
