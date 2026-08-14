"""TikHub 小红书 App V2 Operation 与分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_BASE = "/api/v1/xiaohongshu/app_v2"


@dataclass(frozen=True, slots=True)
class XhsRequest:
    """一次小红书 Operation 的脱敏请求描述。"""

    path: str
    params: dict[str, object]


@dataclass(frozen=True, slots=True)
class XhsSearchPagination:
    """搜索下一页状态和停止原因。"""

    next_page: int
    search_id: str | None
    search_session_id: str | None
    item_ids: tuple[str, ...]
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        current_page: int,
        body: dict[str, Any],
        previous_item_ids: tuple[str, ...] = (),
    ) -> XhsSearchPagination:
        data = _payload(body)
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return cls(current_page + 1, _string(data.get("search_id")), _string(data.get("search_session_id")), (), False, "empty_page")
        item_ids = tuple(filter(None, (_search_item_id(item) for item in items)))
        if item_ids and item_ids == previous_item_ids:
            return cls(current_page + 1, _string(data.get("search_id")), _string(data.get("search_session_id")), item_ids, False, "duplicate_page")
        has_more = data.get("has_more")
        if has_more is False:
            return cls(current_page + 1, _string(data.get("search_id")), _string(data.get("search_session_id")), item_ids, False, "provider_exhausted")
        return cls(current_page + 1, _string(data.get("search_id")), _string(data.get("search_session_id")), item_ids, True)


@dataclass(frozen=True, slots=True)
class XhsCommentPagination:
    """评论下一页状态和停止原因。"""

    cursor: str
    index: int
    page_area: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: str,
        previous_index: int,
        page_area: str,
        body: dict[str, Any],
    ) -> XhsCommentPagination:
        data = _payload(body)
        comments = data.get("comments")
        if not isinstance(comments, list) or not comments:
            return cls(previous_cursor, previous_index, page_area, False, "empty_page")
        cursor = _string(data.get("cursor")) or ""
        index = _integer(data.get("index"), default=previous_index)
        if cursor == previous_cursor and index == previous_index:
            return cls(cursor, index, page_area, False, "pagination_not_advanced")
        if data.get("has_more") is False:
            return cls(cursor, index, page_area, False, "provider_exhausted")
        return cls(cursor, index, page_area, True)


def build_search_notes_request(
    *,
    keyword: str,
    page: int,
    sort_type: str,
    time_filter: str,
    note_type: str = "不限",
    source: str = "explore_feed",
    search_id: str | None = None,
    search_session_id: str | None = None,
) -> XhsRequest:
    params: dict[str, object] = {
        "keyword": keyword,
        "page": page,
        "sort_type": sort_type,
        "note_type": note_type,
        "time_filter": time_filter,
        "source": source,
    }
    if search_id:
        params["search_id"] = search_id
    if search_session_id:
        params["search_session_id"] = search_session_id
    return XhsRequest(f"{_BASE}/search_notes", params)


def build_image_detail_request(*, note_id: str) -> XhsRequest:
    return XhsRequest(f"{_BASE}/get_image_note_detail", {"note_id": note_id})


def build_video_detail_request(*, note_id: str) -> XhsRequest:
    return XhsRequest(f"{_BASE}/get_video_note_detail", {"note_id": note_id})


def build_note_comments_request(
    *, note_id: str, cursor: str = "", index: int = 0, page_area: str = "UNFOLDED"
) -> XhsRequest:
    return XhsRequest(
        f"{_BASE}/get_note_comments",
        {
            "note_id": note_id,
            "cursor": cursor,
            "index": index,
            "pageArea": page_area,
            "sort_strategy": "latest_v2",
        },
    )


def build_sub_comments_request(
    *, note_id: str, comment_id: str, cursor: str = "", index: int = 1
) -> XhsRequest:
    return XhsRequest(
        f"{_BASE}/get_note_sub_comments",
        {"note_id": note_id, "comment_id": comment_id, "cursor": cursor, "index": index},
    )


def _payload(body: dict[str, Any]) -> dict[str, Any]:
    current: object = body
    for _ in range(3):
        if not isinstance(current, dict):
            return {}
        nested = current.get("data")
        if not isinstance(nested, dict):
            return current
        current = nested
    return current if isinstance(current, dict) else {}


def _search_item_id(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    note = item.get("note")
    if isinstance(note, dict):
        return _string(note.get("id") or note.get("note_id")) or ""
    return _string(item.get("id") or item.get("note_id")) or ""


def _string(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def _integer(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
