"""TikHub 微博 Web/App Operation 与有证据的分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/weibo/web/fetch_search"
_DETAIL_PATH = "/api/v1/weibo/app/fetch_status_detail"
_COMMENTS_PATH = "/api/v1/weibo/app/fetch_status_comments"
_SUB_COMMENTS_PATH = "/api/v1/weibo/web_v2/fetch_post_sub_comments"

_SEARCH_TYPES = {
    "general": 1,
    "latest": 61,
    "hot": 60,
    "video": 64,
    "image": 63,
    "article": 21,
}
_TIME_SCOPES = {"all", "hour", "day", "week", "month"}
_COMMENT_SORT_TYPES = {
    "hot": 0,
    "latest": 1,
}


@dataclass(frozen=True, slots=True)
class WeiboRequest:
    """一次微博 Operation 的脱敏请求描述。"""

    method: Literal["GET"]
    path: str
    params: dict[str, object]
    body: None = None


@dataclass(frozen=True, slots=True)
class WeiboSearchPagination:
    """搜索 page 状态；结果列表由真实 cards/mblog 结构判断。"""

    next_page: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_page_observation(
        cls,
        *,
        current_page: int,
        has_results: bool,
    ) -> WeiboSearchPagination:
        if current_page < 1:
            raise ValueError("current_page 必须从 1 开始")
        if not has_results:
            return cls(current_page, False, "empty_page")
        return cls(current_page + 1, True)


@dataclass(frozen=True, slots=True)
class WeiboCommentPagination:
    """App 一级评论按官方 data.moreInfo.params.max_id 推进。"""

    next_max_id: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_max_id: str | None,
        body: dict[str, Any],
    ) -> WeiboCommentPagination:
        returned_max_id = _first_level_comment_max_id(body)
        if returned_max_id == "":
            return cls("", False, "provider_exhausted")
        if previous_max_id is not None and returned_max_id == previous_max_id:
            return cls(returned_max_id, False, "pagination_not_advanced")
        return cls(returned_max_id, True)


@dataclass(frozen=True, slots=True)
class WeiboSubCommentPagination:
    """二级评论只处理已由调用方可靠提取的 max_id，不猜响应 JSON path。"""

    next_max_id: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_returned_max_id(
        cls,
        *,
        previous_max_id: str,
        returned_max_id: str,
    ) -> WeiboSubCommentPagination:
        normalized = returned_max_id.strip()
        if normalized == "":
            return cls("", False, "cursor_unavailable")
        if normalized == previous_max_id:
            return cls(normalized, False, "pagination_not_advanced")
        return cls(normalized, True)


def build_search_request(
    *,
    keyword: str,
    page: int = 1,
    search_mode: str = "latest",
    time_scope: str = "all",
) -> WeiboRequest:
    """把规范化搜索参数映射到 TikHub 微博 Web 搜索。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    search_type = _choice(_SEARCH_TYPES, search_mode, "search_mode")
    if time_scope not in _TIME_SCOPES:
        allowed = ", ".join(sorted(_TIME_SCOPES))
        raise ValueError(f"time_scope 不支持: {time_scope}; 可选: {allowed}")

    params: dict[str, object] = {
        "keyword": normalized_keyword,
        "page": page,
        "search_type": search_type,
    }
    if time_scope != "all":
        params["time_scope"] = time_scope
    return WeiboRequest(method="GET", path=_SEARCH_PATH, params=params)


def build_status_detail_request(*, status_id: str) -> WeiboRequest:
    """构造微博 App 详情请求。"""
    return WeiboRequest(
        method="GET",
        path=_DETAIL_PATH,
        params={"status_id": _required_id(status_id, "status_id")},
    )


def build_status_comments_request(
    *,
    status_id: str,
    max_id: str | None = None,
    sort_mode: str = "latest",
) -> WeiboRequest:
    """构造微博 App 一级评论请求；首屏不发送 max_id。"""
    params: dict[str, object] = {
        "status_id": _required_id(status_id, "status_id"),
        "sort_type": _choice(_COMMENT_SORT_TYPES, sort_mode, "sort_mode"),
    }
    if max_id is not None and max_id != "":
        params["max_id"] = max_id
    return WeiboRequest(method="GET", path=_COMMENTS_PATH, params=params)


def build_status_sub_comments_request(
    *,
    root_comment_id: str,
    max_id: str = "",
) -> WeiboRequest:
    """构造微博 Web V2 二级评论请求；不覆盖可选 count。"""
    return WeiboRequest(
        method="GET",
        path=_SUB_COMMENTS_PATH,
        params={
            "id": _required_id(root_comment_id, "root_comment_id"),
            "max_id": max_id,
        },
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 Web Search 的 data.data.cards 提取含 mblog 的业务卡片。"""
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
        allowed = ", ".join(mapping)
        raise ValueError(f"{field_name} 不支持: {value}; 可选: {allowed}") from exc


def _required_id(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "WeiboCommentPagination",
    "WeiboRequest",
    "WeiboSearchPagination",
    "WeiboSubCommentPagination",
    "build_search_request",
    "build_status_comments_request",
    "build_status_detail_request",
    "build_status_sub_comments_request",
    "extract_search_items",
]
