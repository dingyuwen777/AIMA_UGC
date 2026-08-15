"""Stage 7 抖音 TikHub Operation 与分页行为测试。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.operations.douyin import (
    DouyinCursorPagination,
    DouyinSearchPagination,
    build_video_comment_replies_request,
    build_video_comments_request,
    build_video_detail_request,
    build_video_search_request,
    extract_search_items,
)


def test_search_request_maps_business_parameters_to_approved_v2_payload() -> None:
    request = build_video_search_request(
        keyword="爱玛",
        sort_mode="latest",
        published_within="7d",
        duration="under_1m",
        content_type="video",
    )

    assert request.method == "POST"
    assert request.path == "/api/v1/douyin/search/fetch_video_search_v2"
    assert request.params == {}
    assert request.body == {
        "keyword": "爱玛",
        "cursor": 0,
        "sort_type": "2",
        "publish_time": "7",
        "filter_duration": "0-1",
        "content_type": "1",
        "search_id": "",
        "backtrace": "",
    }


@pytest.mark.parametrize(
    ("sort_mode", "published_within", "duration", "content_type", "expected"),
    [
        ("general", "all", "all", "all", ("0", "0", "0", "0")),
        ("most_liked", "1d", "1_5m", "image", ("1", "1", "1-5", "2")),
        ("latest", "180d", "over_5m", "article", ("2", "180", "5-10000", "3")),
    ],
)
def test_search_business_choices_map_to_documented_provider_values(
    sort_mode: str,
    published_within: str,
    duration: str,
    content_type: str,
    expected: tuple[str, str, str, str],
) -> None:
    request = build_video_search_request(
        keyword="爱玛",
        sort_mode=sort_mode,
        published_within=published_within,
        duration=duration,
        content_type=content_type,
    )
    assert request.body is not None
    assert (
        request.body["sort_type"],
        request.body["publish_time"],
        request.body["filter_duration"],
        request.body["content_type"],
    ) == expected


def test_search_rejects_unknown_business_choice() -> None:
    with pytest.raises(ValueError, match="sort_mode"):
        build_video_search_request(keyword="爱玛", sort_mode="provider_private_value")


def test_search_pagination_preserves_provider_state_and_extracts_aweme_ids() -> None:
    body = {
        "data": {
            "business_data": [
                {"data": {"aweme_info": {"aweme_id": "aweme-1"}}},
                {"data": {"aweme_info": {"aweme_id": "aweme-2"}}},
            ],
            "cursor": 20,
            "has_more": 1,
            "search_id": "search-2",
            "backtrace": "backtrace-2",
        }
    }

    pagination = DouyinSearchPagination.from_response(current_cursor=0, body=body)

    assert pagination.should_continue is True
    assert pagination.next_cursor == 20
    assert pagination.search_id == "search-2"
    assert pagination.backtrace == "backtrace-2"
    assert pagination.item_ids == ("aweme-1", "aweme-2")
    assert len(extract_search_items(body)) == 2

    next_request = build_video_search_request(
        keyword="爱玛",
        cursor=pagination.next_cursor,
        search_id=pagination.search_id,
        backtrace=pagination.backtrace,
    )
    assert next_request.body is not None
    assert next_request.body["cursor"] == 20
    assert next_request.body["search_id"] == "search-2"
    assert next_request.body["backtrace"] == "backtrace-2"


def test_search_pagination_stops_on_empty_duplicate_exhausted_or_stalled_page() -> None:
    empty = DouyinSearchPagination.from_response(
        current_cursor=20,
        body={"data": {"business_data": [], "cursor": 40, "has_more": 1}},
    )
    assert empty.should_continue is False
    assert empty.stop_reason == "empty_page"

    duplicate = DouyinSearchPagination.from_response(
        current_cursor=20,
        previous_item_ids=("aweme-1",),
        body={
            "data": {
                "business_data": [{"data": {"aweme_info": {"aweme_id": "aweme-1"}}}],
                "cursor": 40,
                "has_more": 1,
            }
        },
    )
    assert duplicate.should_continue is False
    assert duplicate.stop_reason == "duplicate_page"

    exhausted = DouyinSearchPagination.from_response(
        current_cursor=20,
        body={
            "data": {
                "business_data": [{"data": {"aweme_info": {"aweme_id": "aweme-2"}}}],
                "cursor": 40,
                "has_more": 0,
            }
        },
    )
    assert exhausted.should_continue is False
    assert exhausted.stop_reason == "provider_exhausted"

    stalled = DouyinSearchPagination.from_response(
        current_cursor=20,
        body={
            "data": {
                "business_data": [{"data": {"aweme_info": {"aweme_id": "aweme-3"}}}],
                "cursor": 20,
                "has_more": 1,
            }
        },
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"


def test_search_duplicate_page_ignores_item_order() -> None:
    duplicate = DouyinSearchPagination.from_response(
        current_cursor=20,
        previous_item_ids=("aweme-1", "aweme-2"),
        body={
            "data": {
                "business_data": [
                    {"data": {"aweme_info": {"aweme_id": "aweme-2"}}},
                    {"data": {"aweme_info": {"aweme_id": "aweme-1"}}},
                ],
                "cursor": 40,
                "has_more": 1,
            }
        },
    )
    assert duplicate.should_continue is False
    assert duplicate.stop_reason == "duplicate_page"


def test_detail_comments_and_replies_use_approved_v3_endpoints_without_count_override() -> None:
    detail = build_video_detail_request(aweme_id="aweme-1")
    assert detail.method == "GET"
    assert detail.path == "/api/v1/douyin/app/v3/fetch_one_video_v3"
    assert detail.params == {"aweme_id": "aweme-1"}
    assert detail.body is None

    comments = build_video_comments_request(aweme_id="aweme-1", cursor=0)
    assert comments.method == "GET"
    assert comments.path == "/api/v1/douyin/app/v3/fetch_video_comments"
    assert comments.params == {"aweme_id": "aweme-1", "cursor": 0}
    assert "count" not in comments.params

    replies = build_video_comment_replies_request(
        item_id="aweme-1",
        comment_id="comment-1",
        cursor=0,
    )
    assert replies.method == "GET"
    assert replies.path == "/api/v1/douyin/app/v3/fetch_video_comment_replies"
    assert replies.params == {
        "item_id": "aweme-1",
        "comment_id": "comment-1",
        "cursor": 0,
    }
    assert "count" not in replies.params


def test_comment_cursor_pagination_uses_only_documented_cursor_and_has_more_facts() -> None:
    next_page = DouyinCursorPagination.from_response(
        previous_cursor=0,
        body={"data": {"cursor": 20, "has_more": 1}},
    )
    assert next_page.should_continue is True
    assert next_page.next_cursor == 20

    exhausted = DouyinCursorPagination.from_response(
        previous_cursor=20,
        body={"data": {"cursor": 40, "has_more": 0}},
    )
    assert exhausted.should_continue is False
    assert exhausted.stop_reason == "provider_exhausted"

    stalled = DouyinCursorPagination.from_response(
        previous_cursor=20,
        body={"data": {"cursor": 20, "has_more": 1}},
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"
