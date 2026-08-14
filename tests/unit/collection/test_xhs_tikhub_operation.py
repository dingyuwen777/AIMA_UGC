"""Stage 6 小红书 TikHub App V2 Operation 行为测试。"""

from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import (
    XhsCommentPagination,
    XhsSearchPagination,
    build_image_detail_request,
    build_note_comments_request,
    build_search_notes_request,
    build_sub_comments_request,
    build_video_detail_request,
)


def test_search_request_and_pagination_keep_session_state() -> None:
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

    pagination = XhsSearchPagination.from_response(
        current_page=1,
        body={
            "data": {
                "data": {
                    "search_id": "search-1",
                    "search_session_id": "session-1",
                    "has_more": True,
                    "items": [{"note": {"id": "note-1"}}],
                }
            }
        },
    )
    assert pagination.should_continue is True
    assert pagination.next_page == 2
    assert pagination.search_id == "search-1"
    assert pagination.search_session_id == "session-1"

    next_request = build_search_notes_request(
        keyword="爱玛",
        page=pagination.next_page,
        sort_type="time_descending",
        time_filter="一天内",
        search_id=pagination.search_id,
        search_session_id=pagination.search_session_id,
    )
    assert next_request.params["search_id"] == "search-1"
    assert next_request.params["search_session_id"] == "session-1"


def test_search_pagination_stops_on_empty_or_nonadvancing_page() -> None:
    empty = XhsSearchPagination.from_response(
        current_page=2,
        body={"data": {"data": {"has_more": True, "items": []}}},
    )
    assert empty.should_continue is False
    assert empty.stop_reason == "empty_page"

    nonadvancing = XhsSearchPagination.from_response(
        current_page=2,
        previous_item_ids=("note-1",),
        body={
            "data": {
                "data": {
                    "has_more": True,
                    "items": [{"note": {"id": "note-1"}}],
                }
            }
        },
    )
    assert nonadvancing.should_continue is False
    assert nonadvancing.stop_reason == "duplicate_page"


def test_detail_and_comment_requests_use_approved_app_v2_endpoints() -> None:
    assert build_image_detail_request(note_id="note-1").path.endswith("/get_image_note_detail")
    assert build_video_detail_request(note_id="note-1").path.endswith("/get_video_note_detail")
    assert build_note_comments_request(note_id="note-1").path.endswith("/get_note_comments")
    assert build_sub_comments_request(note_id="note-1", comment_id="comment-1").path.endswith(
        "/get_note_sub_comments"
    )


def test_comment_pagination_preserves_cursor_index_and_page_area() -> None:
    pagination = XhsCommentPagination.from_response(
        previous_cursor="",
        previous_index=0,
        page_area="UNFOLDED",
        body={
            "data": {
                "data": {
                    "cursor": "cursor-2",
                    "index": 20,
                    "has_more": True,
                    "comments": [{"id": "comment-1"}],
                }
            }
        },
    )
    assert pagination.should_continue is True
    assert pagination.cursor == "cursor-2"
    assert pagination.index == 20
    assert pagination.page_area == "UNFOLDED"

    stalled = XhsCommentPagination.from_response(
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
