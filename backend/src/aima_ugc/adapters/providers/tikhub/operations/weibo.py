"""TikHub 微博 Web/App Operation 与有证据的分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/weibo/web/fetch_search"
_DETAIL_PATH = "/api/v1/weibo/app/fetch_status_detail"
_COMMENTS_PATH = "/api/v1/weibo/app/fetch_status_comments"
_SUB_COMMENTS_PATH = "/api/v1/weibo/web_v2/fetch_post_sub_comments"
_SEARCH_TYPES = {"general": 1, "latest": 61, "hot": 60, "video": 64, "image": 63, "article": 21}
_TIME_SCOPES = {"all", "hour", "day", "week", "month"}
_COMMENT_SORT_TYPES = {"hot": 0, "latest": 1}


@dataclass(frozen=True, slots=True)
class WeiboRequest:
    method: Literal["GET"]
    path: str
    params: dict[str, object]
    body: None = None


@dataclass(frozen=True, slots=True)
class WeiboSearchPagination:
    next_page: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_page_observation(
        cls, *, current_page: int, has_results: bool
    ) -> WeiboSearchPagination:
        if current_page < 1:
            raise ValueError("current_page 必须从 1 开始")
        if not has_results:
            return cls(current_page, False, "empty_page")
        return cls(current_page + 1, True)


@dataclass(frozen=True, slots=True)
class WeiboCommentPagination:
    next_max_id: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls, *, previous_max_id: str | None, body: dict[str, Any]
    ) -> WeiboCommentPagination:
        returned_max_id = _first_level_comment_max_id(body)
        if returned_max_id == "":
            return cls("", False, "provider_exhausted")
        if previous_max_id is not None and returned_max_id == previous_max_id:
            return cls(returned_max_id, False, "pagination_not_advanced")
        return cls(returned_max_id, True)


@dataclass(frozen=True, slots=True)
class WeiboSubCommentPagination:
    next_max_id: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_returned_max_id(
        cls, *, previous_max_id: str, returned_max_id: str
    ) -> WeiboSubCommentPagination:
        normalized = returned_max_id.strip()
        if normalized == "":
            return cls("", False, "cursor_unavailable")
        if normalized == previous_max_id:
            return cls(normalized, False, "pagination_not_advanced")
        return cls(normalized, True)


def build_search_request(
    *, keyword: str, page: int = 1, search_mode: str = "latest", time_scope: str = "all"
) -> WeiboRequest:
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    search_type = _choice(_SEARCH_TYPES, search_mode, "search_mode")
    if time_scope not in _TIME_SCOPES:
        raise ValueError(
            f"time_scope 不支持: {time_scope}; 可选: {', '.join(sorted(_TIME_SCOPES))}"
        )
    params: dict[str, object] = {
        "keyword": normalized_keyword,
        "page": page,
        "search_type": search_type,
    }
    if time_scope != "all":
        params["time_scope"] = time_scope
    return WeiboRequest("GET", _SEARCH_PATH, params)


def build_status_detail_request(*, status_id: str) -> WeiboRequest:
    return WeiboRequest("GET", _DETAIL_PATH, {"status_id": _required_id(status_id, "status_id")})


def build_status_comments_request(
    *, status_id: str, max_id: str | None = None, sort_mode: str = "latest"
) -> WeiboRequest:
    params: dict[str, object] = {
        "status_id": _required_id(status_id, "status_id"),
        "sort_type": _choice(_COMMENT_SORT_TYPES, sort_mode, "sort_mode"),
    }
    if max_id:
        params["max_id"] = max_id
    return WeiboRequest("GET", _COMMENTS_PATH, params)


def build_status_sub_comments_request(*, root_comment_id: str, max_id: str = "") -> WeiboRequest:
    return WeiboRequest(
        "GET",
        _SUB_COMMENTS_PATH,
        {"id": _required_id(root_comment_id, "root_comment_id"), "max_id": max_id},
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    outer = body.get("data")
    if not isinstance(outer, dict):
        return ()
    provider = outer.get("data")
    data = provider if isinstance(provider, dict) else outer
    cards = data.get("cards")
    if not isinstance(cards, list):
        return ()
    return tuple(
        card for card in cards if isinstance(card, dict) and isinstance(card.get("mblog"), dict)
    )


def extract_detail_item(body: dict[str, Any]) -> dict[str, Any]:
    """从真实 App Detail 的 data.detailInfo.status 提取微博对象。"""
    data = body.get("data")
    detail_info = data.get("detailInfo") if isinstance(data, dict) else None
    status = detail_info.get("status") if isinstance(detail_info, dict) else None
    if not isinstance(status, dict):
        raise ValueError("微博详情响应缺少 data.detailInfo.status")
    return status


def extract_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App 评论的 data.items[].data 提取评论对象。"""
    data = body.get("data")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return ()
    return tuple(
        item["data"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("data"), dict)
    )


def _first_level_comment_max_id(body: dict[str, Any]) -> str:
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("微博一级评论响应缺少 data")
    more_info = data.get("moreInfo")
    if not isinstance(more_info, dict):
        raise ValueError("微博一级评论响应缺少 data.moreInfo")
    params = more_info.get("params")
    if not isinstance(params, dict) or "max_id" not in params:
        raise ValueError("微博一级评论响应缺少官方 max_id 路径")
    return _string(params.get("max_id"))


def _choice(mapping: dict[str, int], value: str, field_name: str) -> int:
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"{field_name} 不支持: {value}; 可选: {', '.join(mapping)}") from exc


def _required_id(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _string(value: object) -> str:
    return "" if value is None else str(value).strip()


__all__ = [
    "WeiboCommentPagination",
    "WeiboRequest",
    "WeiboSearchPagination",
    "WeiboSubCommentPagination",
    "build_search_request",
    "build_status_comments_request",
    "build_status_detail_request",
    "build_status_sub_comments_request",
    "extract_comment_items",
    "extract_detail_item",
    "extract_search_items",
]
