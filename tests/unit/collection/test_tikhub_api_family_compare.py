"""TikHub API family 结果集合对照指标测试。"""

import pytest
from aima_ugc.adapters.providers.tikhub.api_family_compare import compare_stable_ids


def test_compare_stable_ids_records_counts_overlap_and_duplicates() -> None:
    result = compare_stable_ids(
        primary_ids=("a", "b", "b", "c"),
        candidate_ids=("b", "c", "d"),
    )

    assert result.primary_count == 4
    assert result.candidate_count == 3
    assert result.primary_unique_count == 3
    assert result.candidate_unique_count == 3
    assert result.primary_duplicate_count == 1
    assert result.candidate_duplicate_count == 0
    assert result.shared_count == 2
    assert result.primary_only_count == 1
    assert result.candidate_only_count == 1
    assert result.union_count == 4
    assert result.jaccard == 0.5
    assert result.same_unique_content is False
    assert result.shared_ids == ("b", "c")
    assert result.primary_only_ids == ("a",)
    assert result.candidate_only_ids == ("d",)


def test_compare_stable_ids_reports_exact_same_content_independent_of_order() -> None:
    result = compare_stable_ids(
        primary_ids=("content-2", "content-1"),
        candidate_ids=("content-1", "content-2"),
    )

    assert result.jaccard == 1.0
    assert result.same_unique_content is True


def test_compare_stable_ids_keeps_empty_result_inconclusive() -> None:
    result = compare_stable_ids(primary_ids=(), candidate_ids=())

    assert result.union_count == 0
    assert result.jaccard is None
    assert result.same_unique_content is False


def test_compare_stable_ids_rejects_blank_stable_id() -> None:
    with pytest.raises(ValueError, match="stable ID"):
        compare_stable_ids(primary_ids=("ok", " "), candidate_ids=("ok",))
