"""Stage 7 快手 TikHub Operation 与分页行为测试。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    KuaishouCursorPagination,
    build_app_video_comments_request,
    build_app_video_sub_comments_request,
    build_search_request,
    build_video_comments_request,
    build_video_detail_request,
    build_video_sub_comments_request,
    build_web_video_comments_request,
    build_web_video_sub_comments_request,
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


def test_cursor_state_does_not_guess_response_json_path_or_provider_sentinels() -> None:
    next_page = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="",
        returned_cursor="cursor-2",
    )
    assert next_page.should_continue is True
    assert next_page.next_cursor == "cursor-2"

    unknown_nonempty_cursor = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="cursor-2",
        returned_cursor="no_more",
    )
    assert unknown_nonempty_cursor.should_continue is True
    assert unknown_nonempty_cursor.next_cursor == "no_more"
    assert unknown_nonempty_cursor.stop_reason is None

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
