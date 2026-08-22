"""Stage 6 小红书 TikHub App V2 Operation 行为测试。"""

from __future__ import annotations

import json
from pathlib import Path

from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import (
    XiaohongshuCommentPagination,
    XiaohongshuSearchPagination,
    build_image_detail_request,
    build_note_comments_request,
    build_search_notes_request,
    build_sub_comments_request,
    build_video_detail_request,
    extract_search_items,
)

_FIXTURE = Path("tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json")


def _search_fixture() -> dict[str, object]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_search_request_and_real_fixture_pagination_keep_session_state() -> None:
    request = build_search_notes_request(
        keyword="爱玛",
        page=1,
        sort_type="time_descending",
        time_filter="一天内",
    )
    assert request.path == "/api/v1/xiaohongshu/app_v2/search_notes"
    assert request.params["keyword"] == "爱玛"
    assert request.params["page"] == 1
    assert "search_id" not in request.params

    body = _search_fixture()
    pagination = XiaohongshuSearchPagination.from_response(current_page=1, body=body)
    assert pagination.should_continue is True
    assert pagination.next_page == 2
    assert pagination.search_id == "search-fixture-1"
    assert pagination.search_session_id == "session-fixture-1"
    assert pagination.item_ids == ("note-fixture-1", "note-fixture-2")
    assert len(extract_search_items(body)) == 2

    next_request = build_search_notes_request(
        keyword="爱玛",
        page=pagination.next_page,
        sort_type="time_descending",
        time_filter="一天内",
        search_id=pagination.search_id,
        search_session_id=pagination.search_session_id,
    )
    assert next_request.params["search_id"] == "search-fixture-1"
    assert next_request.params["search_session_id"] == "session-fixture-1"


def test_search_pagination_stops_on_empty_or_nonadvancing_page() -> None:
    empty = XiaohongshuSearchPagination.from_response(
        current_page=2,
        body={"data": {"data": {"items": []}, "next_page": 3}},
    )
    assert empty.should_continue is False
    assert empty.stop_reason == "empty_page"

    nonadvancing = XiaohongshuSearchPagination.from_response(
        current_page=2,
        previous_item_ids=("note-1",),
        body={
            "data": {
                "data": {"items": [{"note": {"id": "note-1"}}]},
                "next_page": 3,
            }
        },
    )
    assert nonadvancing.should_continue is False
    assert nonadvancing.stop_reason == "duplicate_page"

    stalled = XiaohongshuSearchPagination.from_response(
        current_page=2,
        body={
            "data": {
                "data": {"items": [{"note": {"id": "note-2"}}]},
                "next_page": 2,
            }
        },
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"


def test_detail_and_comment_requests_use_approved_app_v2_endpoints() -> None:
    assert build_image_detail_request(note_id="note-1").path.endswith("/get_image_note_detail")
    assert build_video_detail_request(note_id="note-1").path.endswith("/get_video_note_detail")
    assert build_note_comments_request(note_id="note-1").path.endswith("/get_note_comments")
    assert build_sub_comments_request(note_id="note-1", comment_id="comment-1").path.endswith(
        "/get_note_sub_comments"
    )


def test_comment_pagination_preserves_cursor_index_and_page_area() -> None:
    pagination = XiaohongshuCommentPagination.from_response(
        previous_cursor="",
        previous_index=0,
        page_area="UNFOLDED",
        body={
            "data": {
                "data": {
                    "cursor": "cursor-2",
                    "index": 20,
                    "pageArea": "FOLDED",
                    "has_more": True,
                    "comments": [{"id": "comment-1"}],
                }
            }
        },
    )
    assert pagination.should_continue is True
    assert pagination.cursor == "cursor-2"
    assert pagination.index == 20
    assert pagination.page_area == "FOLDED"

    sub_comment_cursor = XiaohongshuCommentPagination.from_response(
        previous_cursor="",
        previous_index=1,
        page_area="UNFOLDED",
        body={
            "data": {
                "data": {
                    "cursor": {"cursor": "child-cursor", "index": 3},
                    "comments": [{"id": "comment-child"}],
                }
            }
        },
    )
    assert sub_comment_cursor.cursor == "child-cursor"
    assert sub_comment_cursor.index == 3

    stalled = XiaohongshuCommentPagination.from_response(
        previous_cursor="cursor-2",
        previous_index=20,
        page_area="UNFOLDED",
        body={
            "data": {
                "data": {
                    "cursor": "cursor-2",
                    "index": 20,
                    "has_more": True,
                    "comments": [{"id": "comment-2"}],
                }
            }
        },
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"
