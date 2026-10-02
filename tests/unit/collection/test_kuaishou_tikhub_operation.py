"""Stage 7 快手 TikHub Operation 与分页行为测试。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    KuaishouCursorPagination,
    KuaishouUserPostsPagination,
    KuaishouUserSearchPagination,
    build_app_video_comments_request,
    build_app_video_sub_comments_request,
    build_search_request,
    build_user_posts_request,
    build_user_profile_request,
    build_user_search_request,
    build_video_comments_request,
    build_video_detail_request,
    build_video_sub_comments_request,
    build_web_video_comments_request,
    build_web_video_sub_comments_request,
    extract_comment_counts,
    extract_user_post_items,
    extract_user_profile,
    extract_user_search_items,
)


def test_search_v2_only_exposes_keyword_and_provider_cursor() -> None:
    first = build_search_request(keyword="爱玛")
    assert first.method == "GET"
    assert first.path == "/api/v1/kuaishou/app/search_video_v2"
    assert first.params == {"keyword": "爱玛", "pcursor": ""}

    next_page = build_search_request(keyword="爱玛", pcursor="cursor-2")
    assert next_page.params == {"keyword": "爱玛", "pcursor": "cursor-2"}
    assert "sort" not in next_page.params
    assert "time" not in next_page.params


def test_detail_uses_photo_id() -> None:
    request = build_video_detail_request(photo_id="photo-1")
    assert request.method == "GET"
    assert request.path == "/api/v1/kuaishou/app/fetch_one_video"
    assert request.params == {"photo_id": "photo-1"}


def test_account_profile_and_user_posts_use_documented_v2_contracts() -> None:
    profile = build_user_profile_request(user_id="3xfixtureeid")
    assert profile.path == "/api/v1/kuaishou/app/fetch_one_user_v2"
    assert profile.params == {"user_id": "3xfixtureeid"}

    first = build_user_posts_request(user_id="123456789")
    assert first.path == "/api/v1/kuaishou/app/fetch_user_post_v2"
    assert first.params == {
        "user_id": "123456789",
        "pcursor": "",
        "sort": "latest",
    }
    next_page = build_user_posts_request(
        user_id="123456789",
        pcursor="next-page",
    )
    assert next_page.params["pcursor"] == "next-page"
    with pytest.raises(ValueError, match="纯数字"):
        build_user_posts_request(user_id="3xfixtureeid")

    search = build_user_search_request(keyword="loveaima123", page=2)
    assert search.path == "/api/v1/kuaishou/app/search_user_v2"
    assert search.params == {
        "keyword": "loveaima123",
        "page": "2",
    }


def test_account_profile_and_posts_extractors_handle_nested_envelopes() -> None:
    body = {
        "data": {
            "result": {
                "feeds": [
                    {"feed": {"photoId": "photo-1"}},
                    {"ignored": True},
                ],
                "pcursor": "next-page",
            }
        }
    }
    # 坏作品不能静默过滤：保留原索引，由账号执行器记录 Mapper 失败与 partial。
    assert extract_user_post_items(body) == ({"feed": {"photoId": "photo-1"}}, {"ignored": True})
    pagination = KuaishouUserPostsPagination.from_response(
        previous_cursor="",
        body=body,
    )
    assert pagination.should_continue is True
    assert pagination.next_cursor == "next-page"

    profile = extract_user_profile(
        {"data": {"profile": {"userId": 123456789, "userName": "快手官号"}}}
    )
    assert profile["userId"] == 123456789

    search_body = {
        "data": {
            "mixFeeds": [
                {
                    "user": {
                        "userId": "123456789",
                        "kwaiId": "loveaima123",
                    }
                }
            ],
            "pcursor": "next-users",
        }
    }
    assert extract_user_search_items(search_body) == (
        {
            "user": {
                "userId": "123456789",
                "kwaiId": "loveaima123",
            }
        },
    )
    user_search = KuaishouUserSearchPagination.from_response(
        current_page=1,
        body=search_body,
    )
    assert user_search.should_continue is True
    assert user_search.next_page == 2


def test_comment_count_extractor_accepts_integer_and_numeric_text() -> None:
    assert extract_comment_counts({"data": {"commentCount": 12}}) == (12, None)
    assert extract_comment_counts({"data": {"comment_count": "13"}}) == (13, None)


def test_primary_comments_use_app_photo_id_and_pcursor() -> None:
    first = build_video_comments_request(photo_id="photo-1")
    assert first.method == "GET"
    assert first.path == "/api/v1/kuaishou/app/fetch_video_comment"
    assert first.params == {"photo_id": "photo-1", "pcursor": ""}

    next_page = build_video_comments_request(photo_id="photo-1", pcursor="cursor-2")
    assert next_page.params == {"photo_id": "photo-1", "pcursor": "cursor-2"}


def test_primary_sub_comments_use_app_root_cursor_and_count_contract() -> None:
    first = build_video_sub_comments_request(
        photo_id="photo-1",
        root_comment_id="comment-root",
    )
    assert first.method == "GET"
    assert first.path == "/api/v1/kuaishou/app/fetch_video_sub_comments"
    assert first.params == {
        "photo_id": "photo-1",
        "root_comment_id": "comment-root",
        "pcursor": "",
        "count": 8,
    }

    custom = build_video_sub_comments_request(
        photo_id="photo-1",
        root_comment_id="comment-root",
        pcursor="cursor-2",
        count=20,
    )
    assert custom.params["pcursor"] == "cursor-2"
    assert custom.params["count"] == 20


def test_explicit_app_builders_match_primary_comment_contract() -> None:
    assert build_app_video_comments_request(photo_id="photo-1") == build_video_comments_request(
        photo_id="photo-1"
    )
    assert build_app_video_sub_comments_request(
        photo_id="photo-1",
        root_comment_id="comment-root",
    ) == build_video_sub_comments_request(
        photo_id="photo-1",
        root_comment_id="comment-root",
    )

    with pytest.raises(ValueError, match="count"):
        build_app_video_sub_comments_request(
            photo_id="photo-1",
            root_comment_id="comment-root",
            count=0,
        )
    with pytest.raises(ValueError, match="count"):
        build_video_sub_comments_request(
            photo_id="photo-1",
            root_comment_id="comment-root",
            count=21,
        )


def test_web_comment_builders_remain_explicit_verified_backup_only() -> None:
    first = build_web_video_comments_request(photo_id="photo-1")
    assert first.path == "/api/v1/kuaishou/web/fetch_one_video_comment"
    assert first.params == {"photo_id": "photo-1", "pcursor": ""}
    assert "count" not in first.params

    sub = build_web_video_sub_comments_request(
        photo_id="photo-1",
        root_comment_id="comment-root",
    )
    assert sub.path == "/api/v1/kuaishou/web/fetch_one_video_sub_comment"
    assert sub.params == {
        "photo_id": "photo-1",
        "root_comment_id": "comment-root",
        "pcursor": "",
    }


def test_cursor_state_uses_verified_provider_terminal_sentinel() -> None:
    next_page = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="",
        returned_cursor="cursor-2",
    )
    assert next_page.should_continue is True
    assert next_page.next_cursor == "cursor-2"

    terminal_cursor = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="cursor-2",
        returned_cursor="no_more",
    )
    assert terminal_cursor.should_continue is False
    assert terminal_cursor.next_cursor == "no_more"
    assert terminal_cursor.stop_reason == "provider_exhausted"

    terminal_comment_page = KuaishouCursorPagination.from_response(
        previous_cursor="cursor-2",
        body={
            "data": {
                "rootComments": [{"commentId": "comment-1"}],
                "pcursor": "no_more",
            }
        },
        item_key="rootComments",
    )
    assert terminal_comment_page.should_continue is False
    assert terminal_comment_page.stop_reason == "provider_exhausted"

    terminal_posts_page = KuaishouUserPostsPagination.from_response(
        previous_cursor="cursor-2",
        body={
            "data": {
                "feeds": [{"photo_id": "photo-1"}],
                "pcursor": "no_more",
            }
        },
    )
    assert terminal_posts_page.should_continue is False
    assert terminal_posts_page.stop_reason == "provider_exhausted"

    unavailable = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="cursor-2",
        returned_cursor="",
    )
    assert unavailable.should_continue is False
    assert unavailable.stop_reason == "cursor_unavailable"

    stalled = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="cursor-2",
        returned_cursor="cursor-2",
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"


def test_empty_identifiers_fail_closed() -> None:
    with pytest.raises(ValueError, match="keyword"):
        build_search_request(keyword="  ")
    with pytest.raises(ValueError, match="photo_id"):
        build_video_detail_request(photo_id="")
