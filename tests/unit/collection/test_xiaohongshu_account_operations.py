"""小红书指定账号 Discovery 所需 TikHub App V2 Operation 行为测试。"""

from __future__ import annotations

from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu_accounts import (
    XiaohongshuUserNotesPagination,
    XiaohongshuUserSearchPagination,
    build_search_users_request,
    build_user_info_request,
    build_user_posted_notes_request,
    extract_user_posted_note_items,
    extract_user_search_items,
)


def test_user_search_request_and_pagination_keep_search_id() -> None:
    """用户搜索必须复用 App V2 search_id 翻页，并拒绝重复页。"""
    request = build_search_users_request(keyword="49328786266", page=1)
    assert request.path == "/api/v1/xiaohongshu/app_v2/search_users"
    assert request.params == {
        "keyword": "49328786266",
        "page": 1,
        "source": "explore_feed",
    }

    body = {
        "data": {
            "data": {
                "users": [
                    {
                        "user_id": "user-aima",
                        "red_id": "49328786266",
                        "nickname": "爱玛电动车",
                    }
                ],
                "has_more": True,
            },
            "search_id": "user-search-1",
            "next_page": 2,
        }
    }
    items = extract_user_search_items(body)
    assert len(items) == 1
    pagination = XiaohongshuUserSearchPagination.from_response(current_page=1, body=body)
    assert pagination.should_continue is True
    assert pagination.next_page == 2
    assert pagination.search_id == "user-search-1"
    assert pagination.item_ids == ("user-aima",)

    next_request = build_search_users_request(
        keyword="49328786266",
        page=pagination.next_page,
        search_id=pagination.search_id,
    )
    assert next_request.params["search_id"] == "user-search-1"

    duplicate = XiaohongshuUserSearchPagination.from_response(
        current_page=2,
        previous_item_ids=("user-aima",),
        body=body,
    )
    assert duplicate.should_continue is False
    assert duplicate.stop_reason == "duplicate_page"


def test_user_info_and_posted_notes_requests_use_approved_app_v2_endpoints() -> None:
    """用户详情和已发布笔记必须使用当前批准的 App V2 endpoint。"""
    user_info = build_user_info_request(user_id="user-aima")
    assert user_info.path == "/api/v1/xiaohongshu/app_v2/get_user_info"
    assert user_info.params == {"user_id": "user-aima"}

    notes = build_user_posted_notes_request(user_id="user-aima", cursor="")
    assert notes.path == "/api/v1/xiaohongshu/app_v2/get_user_posted_notes"
    assert notes.params == {"user_id": "user-aima", "cursor": ""}


def test_user_posted_notes_cursor_uses_last_note_cursor_and_stops_safely() -> None:
    """用户笔记 cursor 必须从真实列表推进，并防重复 cursor 与 Provider 耗尽。"""
    body = {
        "data": {
            "data": {
                "notes": [
                    {"note_id": "note-1", "cursor": "cursor-1"},
                    {"note_id": "note-2", "cursor": "cursor-2"},
                ],
                "has_more": True,
            }
        }
    }
    items = extract_user_posted_note_items(body)
    assert [item["note_id"] for item in items] == ["note-1", "note-2"]

    pagination = XiaohongshuUserNotesPagination.from_response(previous_cursor="", body=body)
    assert pagination.should_continue is True
    assert pagination.next_cursor == "cursor-2"
    assert pagination.item_ids == ("note-1", "note-2")

    stalled = XiaohongshuUserNotesPagination.from_response(
        previous_cursor="cursor-2",
        body=body,
    )
    assert stalled.should_continue is False
    assert stalled.stop_reason == "pagination_not_advanced"

    exhausted = XiaohongshuUserNotesPagination.from_response(
        previous_cursor="",
        body={
            "data": {
                "data": {
                    "notes": [{"note_id": "note-3", "cursor": "cursor-3"}],
                    "has_more": False,
                }
            }
        },
    )
    assert exhausted.should_continue is False
    assert exhausted.stop_reason == "provider_exhausted"
