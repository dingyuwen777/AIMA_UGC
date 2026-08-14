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
        metadata = _find_mapping(body, required_any=("search_id", "search_session_id", "next_page"))
        page_data = _find_mapping(body, required_any=("items",))
        items = page_data.get("items")
        search_id = _string(metadata.get("search_id"))
        search_session_id = _string(metadata.get("search_session_id"))
        next_page = _integer(metadata.get("next_page"), default=current_page + 1)

        if not isinstance(items, list) or not items:
            return cls(next_page, search_id, search_session_id, (), False, "empty_page")

        item_ids = tuple(filter(None, (_search_item_id(item) for item in items)))
        if item_ids and item_ids == previous_item_ids:
            return cls(
                next_page,
                search_id,
                search_session_id,
                item_ids,
                False,
                "duplicate_page",
            )

        has_more = _first_value((page_data, metadata), "has_more")
        if has_more is False:
            return cls(
                next_page,
                search_id,
                search_session_id,
                item_ids,
                False,
                "provider_exhausted",
            )
        if next_page <= current_page:
            return cls(
                next_page,
                search_id,
                search_session_id,
                item_ids,
                False,
                "pagination_not_advanced",
            )

        return cls(next_page, search_id, search_session_id, item_ids, True)


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
        data = _find_mapping(body, required_any=("comments", "cursor", "index", "pageArea"))
        comments = data.get("comments")
        if not isinstance(comments, list) or not comments:
            return cls(previous_cursor, previous_index, page_area, False, "empty_page")

        cursor_value = data.get("cursor")
        cursor_mapping = cursor_value if isinstance(cursor_value, dict) else {}
        cursor = _string(cursor_mapping.get("cursor")) or _string(cursor_value) or ""
        index = _integer(
            cursor_mapping.get("index"),
            default=_integer(data.get("index"), default=previous_index),
        )
        next_page_area = (
            _string(data.get("pageArea")) or _string(data.get("page_area")) or page_area
        )

        if cursor == previous_cursor and index == previous_index:
            return cls(cursor, index, next_page_area, False, "pagination_not_advanced")
        if data.get("has_more") is False:
            return cls(cursor, index, next_page_area, False, "provider_exhausted")
        return cls(cursor, index, next_page_area, True)


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
        {
            "note_id": note_id,
            "comment_id": comment_id,
            "cursor": cursor,
            "index": index,
        },
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App V2 搜索响应中提取 item wrapper，不复制分页逻辑。"""
    page_data = _find_mapping(body, required_any=("items",))
    items = page_data.get("items")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def _find_mapping(body: dict[str, Any], *, required_any: tuple[str, ...]) -> dict[str, Any]:
    current: object = body
    fallback = body
    for _ in range(5):
        if not isinstance(current, dict):
            break
        fallback = current
        if any(key in current for key in required_any):
            return current
        nested = current.get("data")
        if not isinstance(nested, dict):
            break
        current = nested
    return fallback


def _first_value(mappings: tuple[dict[str, Any], ...], key: str) -> object:
    for mapping in mappings:
        if key in mapping:
            return mapping[key]
    return None


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
    except TypeError, ValueError:
        return default
