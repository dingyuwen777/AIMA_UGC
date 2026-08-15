"""Stage 7 B站 TikHub Operation 与分页行为测试。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.operations.bilibili import (
    BilibiliCursorPagination,
    BilibiliSearchPagination,
    build_reply_detail_request,
    build_search_request,
    build_video_comments_request,
    build_video_detail_request,
)


def test_search_maps_normalized_video_sort_and_starts_at_page_one() -> None:
    request = build_search_request(keyword="爱玛", sort_mode="latest", page=1)
    assert request.method == "GET"
    assert request.path == "/api/v1/bilibili/app/fetch_search_by_type"
    assert request.params == {
        "keyword": "爱玛",
        "search_type": "video",
        "order": "pubdate",
        "page": 1,
    }


@pytest.mark.parametrize(
    ("sort_mode", "expected"),
    [
        ("general", "totalrank"),
        ("latest", "pubdate"),
        ("play_count", "click"),
        ("danmaku_count", "dm"),
    ],
)
def test_search_sort_modes_use_documented_provider_values(sort_mode: str, expected: str) -> None:
    assert build_search_request(keyword="爱玛", sort_mode=sort_mode).params["order"] == expected


def test_search_page_state_does_not_guess_result_array_path() -> None:
    next_page = BilibiliSearchPagination.from_page_observation(current_page=1, has_results=True)
    assert next_page.should_continue is True
    assert next_page.next_page == 2

    empty = BilibiliSearchPagination.from_page_observation(current_page=2, has_results=False)
    assert empty.should_continue is False
    assert empty.stop_reason == "empty_page"


def test_video_detail_uses_bvid() -> None:
    request = build_video_detail_request(bvid="BV1example")
    assert request.method == "GET"
    assert request.path == "/api/v1/bilibili/app/fetch_one_video"
    assert request.params == {"bvid": "BV1example"}


def test_video_comments_use_video_oid_and_keep_pagination_provider_internal() -> None:
    first = build_video_comments_request(oid="123456")
    assert first.path == "/api/v1/bilibili/app/fetch_video_comments"
    assert first.params["oid"] == "123456"
    assert "pagination_str" not in first.params

    next_page = build_video_comments_request(oid="123456", pagination_str='{"offset":"next"}')
    assert next_page.params["pagination_str"] == '{"offset":"next"}'


def test_reply_detail_uses_root_and_next_offset_without_guessing_response_path() -> None:
    first = build_reply_detail_request(oid="123456", root="comment-root", next_offset=0)
    assert first.path == "/api/v1/bilibili/app/fetch_reply_detail"
    assert first.params["oid"] == "123456"
    assert first.params["root"] == "comment-root"
    assert first.params["next"] == 0

    cursor = BilibiliCursorPagination.from_returned_cursor(previous_cursor=0, returned_cursor=20)
    assert cursor.should_continue is True
    assert cursor.next_cursor == 20

    stalled = BilibiliCursorPagination.from_returned_cursor(previous_cursor=20, returned_cursor=20)
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"


def test_invalid_search_page_or_sort_fails_closed() -> None:
    with pytest.raises(ValueError, match="page"):
        build_search_request(keyword="爱玛", page=0)
    with pytest.raises(ValueError, match="sort_mode"):
        build_search_request(keyword="爱玛", sort_mode="provider_private_value")
