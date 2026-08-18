"""Stage 1-7 全面整改的纯不变量回归。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aima_ugc.adapters.providers.tikhub.capabilities import (
    DOUYIN_TIKHUB_CAPABILITY,
    WEIBO_TIKHUB_CAPABILITY,
    XHS_TIKHUB_CAPABILITY,
)
from aima_ugc.bootstrap.collection_scope import (
    _coverage_for_stop,
    _stable_item_locator,
    _technical_partial_stop,
)
from aima_ugc.bootstrap.scheduler import (
    _scheduled_job_timeout_seconds,
    _validate_search_config,
)


def _search(capability):  # type: ignore[no-untyped-def]
    operation = capability.operation("keyword_search")
    assert operation is not None
    return operation


def test_technical_pagination_stop_never_claims_complete_without_provider_terminal() -> None:
    for reason in (
        "pagination_not_advanced",
        "cursor_unavailable",
        "response_data_unavailable",
        "items_unavailable",
        "duplicate_page",
        "page_limit",
    ):
        assert _coverage_for_stop(reason, None, 20) == "partial"
        assert _technical_partial_stop(reason) is True

    assert _coverage_for_stop("provider_exhausted", None, 20) == "complete"
    assert _coverage_for_stop("empty_page", None, 20) == "complete"


def test_scheduled_job_deadline_tracks_next_slot_instead_of_fixed_300_seconds() -> None:
    scheduled_for = datetime(2026, 8, 18, 0, 0, tzinfo=UTC)
    next_run_at = datetime(2026, 8, 18, 6, 0, tzinfo=UTC)

    assert _scheduled_job_timeout_seconds(scheduled_for, next_run_at) == 6 * 60 * 60
    assert _scheduled_job_timeout_seconds(scheduled_for, next_run_at) != 300


def test_scheduled_job_deadline_rejects_non_forward_slot() -> None:
    scheduled_for = datetime(2026, 8, 18, 6, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="晚于"):
        _scheduled_job_timeout_seconds(scheduled_for, scheduled_for)


def test_live_locator_is_stable_for_same_raw_item_and_changes_with_raw_identity() -> None:
    first = {"id": "content-1", "title": "A", "nested": {"count": 1}}
    reordered = {"nested": {"count": 1}, "title": "A", "id": "content-1"}
    changed = {"id": "content-2", "title": "A", "nested": {"count": 1}}

    locator = _stable_item_locator("search_notes", "content", first)
    assert locator == _stable_item_locator("search_notes", "content", reordered)
    assert locator != _stable_item_locator("search_notes", "content", changed)
    assert "items[" not in locator


def test_xhs_live_and_douyin_article_are_not_exposed_without_full_mapper_detail_support() -> None:
    assert "live" not in _search(XHS_TIKHUB_CAPABILITY).supported_content_types
    assert "article" not in _search(DOUYIN_TIKHUB_CAPABILITY).supported_content_types


def test_weibo_does_not_expose_fake_independent_content_type_dimension() -> None:
    search = _search(WEIBO_TIKHUB_CAPABILITY)
    assert search.supported_content_types == ()
    with pytest.raises(ValueError, match="content_type"):
        _validate_search_config(
            WEIBO_TIKHUB_CAPABILITY,
            {"sort_mode": "latest", "content_type": "video"},
        )


def test_douyin_duration_capability_round_trips_plan_validation() -> None:
    _validate_search_config(
        DOUYIN_TIKHUB_CAPABILITY,
        {
            "sort_mode": "latest",
            "published_within": "7d",
            "duration": "1_5m",
            "content_type": "video",
        },
    )
    with pytest.raises(ValueError, match="duration"):
        _validate_search_config(DOUYIN_TIKHUB_CAPABILITY, {"duration": "unsupported"})

# Temporary trigger v2 for the registered Stage 5B corrective runner; the runner removes this line.
