"""TikHub 抖音 Search V2 / App V3 Operation 与分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/douyin/search/fetch_video_search_v2"
_APP_V3_BASE = "/api/v1/douyin/app/v3"

_SORT_TYPES = {
    "general": "0",
    "most_liked": "1",
    "latest": "2",
}
_PUBLISH_TIMES = {
    "all": "0",
    "1d": "1",
    "7d": "7",
    "180d": "180",
}
_DURATIONS = {
    "all": "0",
    "under_1m": "0-1",
    "1_5m": "1-5",
    "over_5m": "5-10000",
}
_CONTENT_TYPES = {
    "all": "0",
    "video": "1",
    "image": "2",
    "article": "3",
}


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
        data = _find_mapping(body, required_any=("business_data", "cursor", "has_more"))
        items = extract_search_items(body)
        next_cursor = _integer(data.get("cursor"), default=current_cursor)
        search_id = _string(data.get("search_id")) or ""
        backtrace = _string(data.get("backtrace")) or ""

        if not items:
            return cls(next_cursor, search_id, backtrace, (), False, "empty_page")

        item_ids = tuple(filter(None, (_search_item_id(item) for item in items)))
        if _same_item_ids(item_ids, previous_item_ids):
            return cls(
                next_cursor,
                search_id,
                backtrace,
                item_ids,
                False,
                "duplicate_page",
            )
        if _provider_exhausted(data.get("has_more")):
            return cls(
                next_cursor,
                search_id,
                backtrace,
                item_ids,
                False,
                "provider_exhausted",
            )
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
    """App V3 评论/回复仅基于官方 cursor/has_more 的下一页状态。"""

    next_cursor: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: int,
        body: dict[str, Any],
    ) -> DouyinCursorPagination:
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
    """把规范化搜索业务参数映射到 TikHub Douyin Search V2 请求体。"""
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
    return DouyinRequest(method="POST", path=_SEARCH_PATH, params={}, body=body)


def build_video_detail_request(*, aweme_id: str) -> DouyinRequest:
    """构造 TikHub Douyin App V3 单作品详情请求。"""
    return DouyinRequest(
        method="GET",
        path=f"{_APP_V3_BASE}/fetch_one_video_v3",
        params={"aweme_id": _required_id(aweme_id, "aweme_id")},
    )


def build_video_comments_request(*, aweme_id: str, cursor: int = 0) -> DouyinRequest:
    """构造一级评论请求；不覆盖 TikHub 官方要求保持默认的 count。"""
    _nonnegative_cursor(cursor)
    return DouyinRequest(
        method="GET",
        path=f"{_APP_V3_BASE}/fetch_video_comments",
        params={"aweme_id": _required_id(aweme_id, "aweme_id"), "cursor": cursor},
    )


def build_video_comment_replies_request(
    *,
    item_id: str,
    comment_id: str,
    cursor: int = 0,
) -> DouyinRequest:
    """构造评论回复请求；不覆盖 TikHub 官方要求保持默认的 count。"""
    _nonnegative_cursor(cursor)
    return DouyinRequest(
        method="GET",
        path=f"{_APP_V3_BASE}/fetch_video_comment_replies",
        params={
            "item_id": _required_id(item_id, "item_id"),
            "comment_id": _required_id(comment_id, "comment_id"),
            "cursor": cursor,
        },
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 Search V2 响应中提取官方 business_data wrapper，不解释业务字段。"""
    data = _find_mapping(body, required_any=("business_data",))
    items = data.get("business_data")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def _choice(mapping: dict[str, str], value: str, field_name: str) -> str:
    try:
        return mapping[value]
    except KeyError as exc:
        allowed = ", ".join(mapping)
        raise ValueError(f"{field_name} 不支持: {value}; 可选: {allowed}") from exc


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
    if not isinstance(data, dict):
        return ""
    aweme_info = data.get("aweme_info")
    if not isinstance(aweme_info, dict):
        return ""
    return _string(aweme_info.get("aweme_id")) or ""


def _same_item_ids(current: tuple[str, ...], previous: tuple[str, ...]) -> bool:
    if not current or len(current) != len(previous):
        return False
    return set(current) == set(previous)


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
    "extract_search_items",
]
