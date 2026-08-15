"""Stage 7 快手 TikHub Operation 与分页行为测试。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    KuaishouCursorPagination,
    build_search_request,
    build_video_comments_request,
    build_video_detail_request,
    build_video_sub_comments_request,
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


def test_web_comments_use_photo_id_and_pcursor_without_business_page_size() -> None:
    first = build_video_comments_request(photo_id="photo-1")
    assert first.path == "/api/v1/kuaishou/web/fetch_one_video_comment"
    assert first.params == {"photo_id": "photo-1", "pcursor": ""}

    next_page = build_video_comments_request(photo_id="photo-1", pcursor="cursor-2")
    assert next_page.params == {"photo_id": "photo-1", "pcursor": "cursor-2"}
    assert "count" not in next_page.params


def test_web_sub_comments_use_root_comment_id_and_pcursor() -> None:
    first = build_video_sub_comments_request(
        photo_id="photo-1",
        root_comment_id="comment-root",
    )
    assert first.path == "/api/v1/kuaishou/web/fetch_one_video_sub_comment"
    assert first.params == {
        "photo_id": "photo-1",
        "root_comment_id": "comment-root",
        "pcursor": "",
    }


def test_cursor_state_does_not_guess_response_json_path() -> None:
    next_page = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="",
        returned_cursor="cursor-2",
    )
    assert next_page.should_continue is True
    assert next_page.next_cursor == "cursor-2"

    exhausted = KuaishouCursorPagination.from_returned_cursor(
        previous_cursor="cursor-2",
        returned_cursor="no_more",
    )
    assert exhausted.should_continue is False
    assert exhausted.stop_reason == "provider_exhausted"

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
