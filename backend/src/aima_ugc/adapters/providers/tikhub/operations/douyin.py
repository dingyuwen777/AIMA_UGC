"""TikHub 抖音 Search V2 / App V3 Operation 与分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/douyin/search/fetch_video_search_v2"
_APP_V3_BASE = "/api/v1/douyin/app/v3"

_SORT_TYPES = {"general": "0", "most_liked": "1", "latest": "2"}
_PUBLISH_TIMES = {"all": "0", "1d": "1", "7d": "7", "180d": "180"}
_DURATIONS = {"all": "0", "under_1m": "0-1", "1_5m": "1-5", "over_5m": "5-10000"}
_CONTENT_TYPES = {"all": "0", "video": "1", "image": "2", "article": "3"}


@dataclass(frozen=True, slots=True)
class DouyinRequest:
    """一次抖音 Operation 的脱敏请求描述。"""

    method: Literal["GET", "POST"]
    path: str
    params: dict[str, object]
    body: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class DouyinSearchPagination:
    """Search V2 下一页状态与停止原因。"""

    next_cursor: int
    search_id: str
    backtrace: str
    item_ids: tuple[str, ...]
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        current_cursor: int,
        body: dict[str, Any],
        previous_item_ids: tuple[str, ...] = (),
    ) -> DouyinSearchPagination:
        data = _find_mapping(body, required_any=("business_data",))
        items = extract_search_items(body)
        business_config_raw = data.get("business_config")
        business_config = business_config_raw if isinstance(business_config_raw, dict) else {}
        next_page_raw = business_config.get("next_page")
        next_page = next_page_raw if isinstance(next_page_raw, dict) else {}
        next_cursor = _integer(
            next_page.get("cursor"),
            default=_integer(data.get("cursor"), default=current_cursor),
        )
        search_id = _string(next_page.get("search_id")) or _string(data.get("search_id")) or ""
        backtrace = (
            _string(business_config.get("backtrace")) or _string(data.get("backtrace")) or ""
        )
        has_more = (
            business_config.get("has_more")
            if "has_more" in business_config
            else data.get("has_more")
        )
        if not items:
            return cls(next_cursor, search_id, backtrace, (), False, "empty_page")
        item_ids = tuple(filter(None, (_search_item_id(item) for item in items)))
        if _same_item_ids(item_ids, previous_item_ids):
            return cls(next_cursor, search_id, backtrace, item_ids, False, "duplicate_page")
        if _provider_exhausted(has_more):
            return cls(next_cursor, search_id, backtrace, item_ids, False, "provider_exhausted")
        if next_cursor <= current_cursor:
            return cls(
                next_cursor,
                search_id,
                backtrace,
                item_ids,
                False,
                "pagination_not_advanced",
            )
        return cls(next_cursor, search_id, backtrace, item_ids, True)


@dataclass(frozen=True, slots=True)
class DouyinCursorPagination:
    """App V3 评论/回复仅基于真实 cursor/has_more 的下一页状态。"""

    next_cursor: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(cls, *, previous_cursor: int, body: dict[str, Any]) -> DouyinCursorPagination:
        data = _find_mapping(body, required_any=("cursor", "has_more"))
        next_cursor = _integer(data.get("cursor"), default=previous_cursor)
        if _provider_exhausted(data.get("has_more")):
            return cls(next_cursor, False, "provider_exhausted")
        if next_cursor <= previous_cursor:
            return cls(next_cursor, False, "pagination_not_advanced")
        return cls(next_cursor, True)


def build_video_search_request(
    *,
    keyword: str,
    cursor: int = 0,
    sort_mode: str = "general",
    published_within: str = "all",
    duration: str = "all",
    content_type: str = "all",
    search_id: str = "",
    backtrace: str = "",
) -> DouyinRequest:
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if cursor < 0:
        raise ValueError("cursor 不能为负数")
    body: dict[str, object] = {
        "keyword": normalized_keyword,
        "cursor": cursor,
        "sort_type": _choice(_SORT_TYPES, sort_mode, "sort_mode"),
        "publish_time": _choice(_PUBLISH_TIMES, published_within, "published_within"),
        "filter_duration": _choice(_DURATIONS, duration, "duration"),
        "content_type": _choice(_CONTENT_TYPES, content_type, "content_type"),
        "search_id": search_id,
        "backtrace": backtrace,
    }
    return DouyinRequest("POST", _SEARCH_PATH, {}, body)


def build_video_detail_request(*, aweme_id: str) -> DouyinRequest:
    return DouyinRequest(
        "GET",
        f"{_APP_V3_BASE}/fetch_one_video_v3",
        {"aweme_id": _required_id(aweme_id, "aweme_id")},
    )


def build_video_comments_request(*, aweme_id: str, cursor: int = 0) -> DouyinRequest:
    _nonnegative_cursor(cursor)
    return DouyinRequest(
        "GET",
        f"{_APP_V3_BASE}/fetch_video_comments",
        {"aweme_id": _required_id(aweme_id, "aweme_id"), "cursor": cursor},
    )


def build_video_comment_replies_request(
    *, item_id: str, comment_id: str, cursor: int = 0
) -> DouyinRequest:
    _nonnegative_cursor(cursor)
    return DouyinRequest(
        "GET",
        f"{_APP_V3_BASE}/fetch_video_comment_replies",
        {
            "item_id": _required_id(item_id, "item_id"),
            "comment_id": _required_id(comment_id, "comment_id"),
            "cursor": cursor,
        },
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    data = _find_mapping(body, required_any=("business_data",))
    items = data.get("business_data")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def extract_detail_item(body: dict[str, Any]) -> dict[str, Any]:
    """从真实 App V3 detail 响应提取 data.aweme_detail。"""
    data = body.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("aweme_detail"), dict):
        raise ValueError("抖音详情响应缺少 data.aweme_detail")
    return data["aweme_detail"]


def extract_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App V3 评论/回复响应提取 data.comments。"""
    data = body.get("data")
    if not isinstance(data, dict):
        return ()
    items = data.get("comments")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def _choice(mapping: dict[str, str], value: str, field_name: str) -> str:
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"{field_name} 不支持: {value}; 可选: {', '.join(mapping)}") from exc


def _required_id(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _nonnegative_cursor(cursor: int) -> None:
    if cursor < 0:
        raise ValueError("cursor 不能为负数")


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


def _search_item_id(item: dict[str, Any]) -> str:
    data = item.get("data")
    aweme_info = data.get("aweme_info") if isinstance(data, dict) else None
    return _string(aweme_info.get("aweme_id")) or "" if isinstance(aweme_info, dict) else ""


def _same_item_ids(current: tuple[str, ...], previous: tuple[str, ...]) -> bool:
    return bool(current) and len(current) == len(previous) and set(current) == set(previous)


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _integer(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _provider_exhausted(value: object) -> bool:
    return value is False or value == 0 or value == "0"


__all__ = [
    "DouyinCursorPagination",
    "DouyinRequest",
    "DouyinSearchPagination",
    "build_video_comment_replies_request",
    "build_video_comments_request",
    "build_video_detail_request",
    "build_video_search_request",
    "extract_comment_items",
    "extract_detail_item",
    "extract_search_items",
]
