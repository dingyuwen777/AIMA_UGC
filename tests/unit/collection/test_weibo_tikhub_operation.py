"""Stage 7 微博 TikHub Operation 与分页行为测试。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.operations.weibo import (
    WeiboCommentPagination,
    WeiboSearchPagination,
    WeiboSubCommentPagination,
    build_search_request,
    build_status_comments_request,
    build_status_detail_request,
    build_status_sub_comments_request,
)


def test_search_request_maps_current_documented_business_modes() -> None:
    request = build_search_request(
        keyword="爱玛",
        page=2,
        search_mode="latest",
        time_scope="day",
    )

    assert request.method == "GET"
    assert request.path == "/api/v1/weibo/web/fetch_search"
    assert request.params == {
        "keyword": "爱玛",
        "page": 2,
        "search_type": 61,
        "time_scope": "day",
    }
    assert request.body is None


@pytest.mark.parametrize(
    ("search_mode", "expected"),
    [
        ("general", 1),
        ("latest", 61),
        ("hot", 60),
        ("video", 64),
        ("image", 63),
        ("article", 21),
    ],
)
def test_search_mode_mapping_matches_current_official_values(
    search_mode: str,
    expected: int,
) -> None:
    request = build_search_request(keyword="爱玛", search_mode=search_mode)
    assert request.params["search_type"] == expected


def test_search_defaults_to_latest_and_omits_all_time_scope() -> None:
    request = build_search_request(keyword="爱玛", time_scope="all")
    assert request.params == {"keyword": "爱玛", "page": 1, "search_type": 61}


def test_search_rejects_invalid_page_mode_or_time_scope() -> None:
    with pytest.raises(ValueError, match="page"):
        build_search_request(keyword="爱玛", page=0)
    with pytest.raises(ValueError, match="search_mode"):
        build_search_request(keyword="爱玛", search_mode="provider_private_value")
    with pytest.raises(ValueError, match="time_scope"):
        build_search_request(keyword="爱玛", time_scope="year")


def test_search_page_state_only_advances_from_observed_nonempty_page() -> None:
    next_page = WeiboSearchPagination.from_page_observation(current_page=1, has_results=True)
    assert next_page.should_continue is True
    assert next_page.next_page == 2
    assert next_page.stop_reason is None

    empty = WeiboSearchPagination.from_page_observation(current_page=2, has_results=False)
    assert empty.should_continue is False
    assert empty.next_page == 2
    assert empty.stop_reason == "empty_page"


def test_detail_and_first_level_comments_use_current_status_id_parameter() -> None:
    detail = build_status_detail_request(status_id="weibo-1")
    assert detail.method == "GET"
    assert detail.path == "/api/v1/weibo/app/fetch_status_detail"
    assert detail.params == {"status_id": "weibo-1"}

    first_page = build_status_comments_request(status_id="weibo-1")
    assert first_page.path == "/api/v1/weibo/app/fetch_status_comments"
    assert first_page.params == {"status_id": "weibo-1", "sort_type": 1}

    next_page = build_status_comments_request(
        status_id="weibo-1",
        max_id="cursor-2",
        sort_mode="hot",
    )
    assert next_page.params == {
        "status_id": "weibo-1",
        "max_id": "cursor-2",
        "sort_type": 0,
    }


def test_first_level_comment_pagination_uses_only_official_max_id_json_path() -> None:
    next_page = WeiboCommentPagination.from_response(
        previous_max_id=None,
        body={"data": {"moreInfo": {"params": {"max_id": "cursor-2"}}}},
    )
    assert next_page.should_continue is True
    assert next_page.next_max_id == "cursor-2"

    exhausted = WeiboCommentPagination.from_response(
        previous_max_id="cursor-2",
        body={"data": {"moreInfo": {"params": {"max_id": ""}}}},
    )
    assert exhausted.should_continue is False
    assert exhausted.stop_reason == "provider_exhausted"

    stalled = WeiboCommentPagination.from_response(
        previous_max_id="cursor-2",
        body={"data": {"moreInfo": {"params": {"max_id": "cursor-2"}}}},
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"


def test_sub_comments_request_keeps_provider_cursor_internal_and_omits_count_override() -> None:
    first_page = build_status_sub_comments_request(root_comment_id="comment-root")
    assert first_page.method == "GET"
    assert first_page.path == "/api/v1/weibo/web_v2/fetch_post_sub_comments"
    assert first_page.params == {"id": "comment-root", "max_id": ""}
    assert "count" not in first_page.params

    next_page = build_status_sub_comments_request(
        root_comment_id="comment-root",
        max_id="sub-cursor-2",
    )
    assert next_page.params == {"id": "comment-root", "max_id": "sub-cursor-2"}


def test_sub_comment_cursor_transition_does_not_guess_response_json_path() -> None:
    next_page = WeiboSubCommentPagination.from_returned_max_id(
        previous_max_id="",
        returned_max_id="sub-cursor-2",
    )
    assert next_page.should_continue is True
    assert next_page.next_max_id == "sub-cursor-2"

    unavailable = WeiboSubCommentPagination.from_returned_max_id(
        previous_max_id="sub-cursor-2",
        returned_max_id="",
    )
    assert unavailable.should_continue is False
    assert unavailable.stop_reason == "cursor_unavailable"

    stalled = WeiboSubCommentPagination.from_returned_max_id(
        previous_max_id="sub-cursor-2",
        returned_max_id="sub-cursor-2",
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"
