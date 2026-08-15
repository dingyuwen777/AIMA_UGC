"""TikHub 快手 App/Web Operation 与保守 pcursor 状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/kuaishou/app/search_video_v2"
_DETAIL_PATH = "/api/v1/kuaishou/app/fetch_one_video"
_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_comment"
_SUB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_sub_comment"


@dataclass(frozen=True, slots=True)
class KuaishouRequest:
    method: Literal["GET"]
    path: str
    params: dict[str, object]
    body: None = None


@dataclass(frozen=True, slots=True)
class KuaishouCursorPagination:
    next_cursor: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_returned_cursor(
        cls,
        *,
        previous_cursor: str,
        returned_cursor: str | None,
    ) -> KuaishouCursorPagination:
        if returned_cursor is None:
            return cls(previous_cursor, False, "cursor_unavailable")
        normalized = returned_cursor.strip()
        if normalized == "":
            return cls("", False, "cursor_unavailable")
        if normalized == previous_cursor:
            return cls(normalized, False, "pagination_not_advanced")
        return cls(normalized, True)


@dataclass(frozen=True, slots=True)
class KuaishouSearchPagination:
    """Search V2 按真实 data.pcursor 推进，不猜 Provider 私有终止哨兵。"""

    next_cursor: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: str,
        body: dict[str, Any],
    ) -> KuaishouSearchPagination:
        data = body.get("data")
        if not isinstance(data, dict):
            return cls(previous_cursor, False, "response_data_unavailable")
        items = data.get("mixFeeds")
        if not isinstance(items, list) or not items:
            return cls(previous_cursor, False, "empty_page")
        returned = data.get("pcursor")
        if returned is None:
            return cls(previous_cursor, False, "cursor_unavailable")
        normalized = str(returned).strip()
        if not normalized:
            return cls("", False, "cursor_unavailable")
        if normalized == previous_cursor:
            return cls(normalized, False, "pagination_not_advanced")
        return cls(normalized, True)


def build_search_request(*, keyword: str, pcursor: str = "") -> KuaishouRequest:
    normalized_keyword = _required_text(keyword, "keyword")
    return KuaishouRequest(
        method="GET",
        path=_SEARCH_PATH,
        params={"keyword": normalized_keyword, "pcursor": pcursor},
    )


def build_video_detail_request(*, photo_id: str) -> KuaishouRequest:
    return KuaishouRequest(
        method="GET",
        path=_DETAIL_PATH,
        params={"photo_id": _required_text(photo_id, "photo_id")},
    )


def build_video_comments_request(*, photo_id: str, pcursor: str = "") -> KuaishouRequest:
    return KuaishouRequest(
        method="GET",
        path=_COMMENTS_PATH,
        params={"photo_id": _required_text(photo_id, "photo_id"), "pcursor": pcursor},
    )


def build_video_sub_comments_request(
    *,
    photo_id: str,
    root_comment_id: str,
    pcursor: str = "",
) -> KuaishouRequest:
    return KuaishouRequest(
        method="GET",
        path=_SUB_COMMENTS_PATH,
        params={
            "photo_id": _required_text(photo_id, "photo_id"),
            "root_comment_id": _required_text(root_comment_id, "root_comment_id"),
            "pcursor": pcursor,
        },
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App Search V2 的 data.mixFeeds 提取含 feed 的业务 item。"""
    data = body.get("data")
    if not isinstance(data, dict):
        return ()
    items = data.get("mixFeeds")
    if not isinstance(items, list):
        return ()
    return tuple(
        item for item in items if isinstance(item, dict) and isinstance(item.get("feed"), dict)
    )


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


__all__ = [
    "KuaishouCursorPagination",
    "KuaishouRequest",
    "KuaishouSearchPagination",
    "build_search_request",
    "build_video_comments_request",
    "build_video_detail_request",
    "build_video_sub_comments_request",
    "extract_search_items",
]
