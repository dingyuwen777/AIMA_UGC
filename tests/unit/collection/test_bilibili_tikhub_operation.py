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


def test_search_uses_official_cursor_and_numeric_sort_values() -> None:
    first = build_search_request(keyword="爱玛", sort_mode="latest")
    assert first.method == "GET"
    assert first.path == "/api/v1/bilibili/app/fetch_search_by_type"
    assert first.params == {
        "keyword": "爱玛",
        "search_type": "video",
        "order": 1,
    }
    assert "page" not in first.params

    next_page = build_search_request(keyword="爱玛", sort_mode="latest", cursor="cursor-next")
    assert next_page.params == {
        "keyword": "爱玛",
        "search_type": "video",
        "order": 1,
        "cursor": "cursor-next",
    }


def test_search_keeps_general_as_the_existing_default_sort() -> None:
    request = build_search_request(keyword="爱玛")
    assert request.params["order"] == 0


@pytest.mark.parametrize(
    ("sort_mode", "expected"),
    [
        ("general", 0),
        ("latest", 1),
        ("play_count", 2),
        ("danmaku_count", 3),
    ],
)
def test_search_sort_modes_use_current_official_provider_values(
    sort_mode: str,
    expected: int,
) -> None:
    assert build_search_request(keyword="爱玛", sort_mode=sort_mode).params["order"] == expected


def test_search_cursor_state_uses_official_response_path_and_stops_safely() -> None:
    next_page = BilibiliSearchPagination.from_response(
        previous_cursor=None,
        body={"data": {"data": {"pagination": {"next": "cursor-2"}}}},
    )
    assert next_page.should_continue is True
    assert next_page.next_cursor == "cursor-2"

    exhausted = BilibiliSearchPagination.from_response(
        previous_cursor="cursor-2",
        body={"data": {"data": {}}},
    )
    assert exhausted.should_continue is False
    assert exhausted.next_cursor == ""
    assert exhausted.stop_reason == "provider_exhausted"

    stalled = BilibiliSearchPagination.from_response(
        previous_cursor="cursor-2",
        body={"data": {"data": {"pagination": {"next": "cursor-2"}}}},
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"


def test_video_detail_accepts_exactly_one_official_video_id() -> None:
    by_bv = build_video_detail_request(bv_id="BV1example")
    assert by_bv.method == "GET"
    assert by_bv.path == "/api/v1/bilibili/app/fetch_one_video"
    assert by_bv.params == {"bv_id": "BV1example"}

    by_av = build_video_detail_request(av_id="123456")
    assert by_av.params == {"av_id": "123456"}

    with pytest.raises(ValueError, match="二选一"):
        build_video_detail_request()
    with pytest.raises(ValueError, match="二选一"):
        build_video_detail_request(av_id="123456", bv_id="BV1example")


def test_video_comments_use_official_video_id_sort_and_next_offset() -> None:
    first = build_video_comments_request(bv_id="BV1example", sort_mode="latest")
    assert first.path == "/api/v1/bilibili/app/fetch_video_comments"
    assert first.params == {"bv_id": "BV1example", "mode": 2}

    next_page = build_video_comments_request(
        av_id="123456",
        sort_mode="hot",
        next_offset=20,
    )
    assert next_page.params == {
        "av_id": "123456",
        "mode": 3,
        "next_offset": 20,
    }

    with pytest.raises(ValueError, match="sort_mode"):
        build_video_comments_request(bv_id="BV1example", sort_mode="provider_private_value")


def test_reply_detail_uses_root_video_id_and_next_offset_without_page_size_override() -> None:
    first = build_reply_detail_request(root="comment-root", bv_id="BV1example")
    assert first.path == "/api/v1/bilibili/app/fetch_reply_detail"
    assert first.params == {
        "root": "comment-root",
        "bv_id": "BV1example",
    }

    next_page = build_reply_detail_request(
        root="comment-root",
        av_id="123456",
        next_offset=20,
    )
    assert next_page.params == {
        "root": "comment-root",
        "av_id": "123456",
        "next_offset": 20,
    }
    assert "ps" not in next_page.params


def test_returned_comment_offset_state_does_not_guess_response_path() -> None:
    cursor = BilibiliCursorPagination.from_returned_cursor(
        previous_cursor=0,
        returned_cursor=20,
    )
    assert cursor.should_continue is True
    assert cursor.next_cursor == 20

    stalled = BilibiliCursorPagination.from_returned_cursor(
        previous_cursor=20,
        returned_cursor=20,
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"

    regressed = BilibiliCursorPagination.from_returned_cursor(
        previous_cursor=20,
        returned_cursor=10,
    )
    assert regressed.should_continue is False
    assert regressed.stop_reason == "pagination_not_advanced"


def test_invalid_search_and_offset_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="sort_mode"):
        build_search_request(keyword="爱玛", sort_mode="provider_private_value")
    with pytest.raises(ValueError, match="search_type"):
        build_search_request(keyword="爱玛", search_type="article")
    with pytest.raises(ValueError, match="next_offset"):
        build_video_comments_request(bv_id="BV1example", next_offset=-1)
    with pytest.raises(ValueError, match="next_offset"):
        build_reply_detail_request(root="comment-root", bv_id="BV1example", next_offset=-1)
