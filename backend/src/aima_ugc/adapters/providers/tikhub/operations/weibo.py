"""TikHub 微博 Web/App Operation 与有证据的分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/weibo/web/fetch_search"
_APP_SEARCH_CANDIDATE_PATH = "/api/v1/weibo/app/fetch_search_all"
_DETAIL_PATH = "/api/v1/weibo/app/fetch_status_detail"
_COMMENTS_PATH = "/api/v1/weibo/app/fetch_status_comments"
_WEB_COMMENTS_CANDIDATE_PATH = "/api/v1/weibo/web_v2/fetch_post_comments"
_SUB_COMMENTS_PATH = "/api/v1/weibo/web_v2/fetch_post_sub_comments"
_USER_SEARCH_PATH = "/api/v1/weibo/web_v2/fetch_user_search"
_USER_POSTS_PATH = "/api/v1/weibo/web_v2/fetch_user_posts"
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


@dataclass(frozen=True, slots=True)
class WeiboUserPostsPagination:
    """用户作品用页号遍历；非空页的空 since_id 不是耗尽证据。"""

    next_since_id: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls, *, previous_since_id: str, body: dict[str, Any]
    ) -> WeiboUserPostsPagination:
        container, items = _find_user_posts_container(body)
        if container is None:
            return cls(previous_since_id, False, "response_data_unavailable")
        if not items:
            return cls("", False, "empty_page")
        returned = _string(container.get("since_id"))
        if not returned:
            # 真实 Web V2 非空页常返回空 since_id，下一页仍有不同作品。
            return cls("", True)
        if returned == previous_since_id:
            return cls(returned, False, "pagination_not_advanced")
        return cls(returned, True)


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


def build_app_search_candidate_request(
    *, keyword: str, page: int = 1, search_mode: str = "latest"
) -> WeiboRequest:
    """构造 App 综合搜索 A/B 候选；不伪造 Web 专属 time_scope，也不进入自动 fallback。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    return WeiboRequest(
        "GET",
        _APP_SEARCH_CANDIDATE_PATH,
        {
            "query": normalized_keyword,
            "page": page,
            "search_type": _choice(_SEARCH_TYPES, search_mode, "search_mode"),
        },
    )


def build_user_search_request(
    *, query: str, page: int = 1, nickname: str | None = None
) -> WeiboRequest:
    """构造 Web V2 用户搜索，用于把昵称解析为稳定 UID。"""

    if page < 1:
        raise ValueError("page 必须从 1 开始")
    normalized_query = _required_id(query, "query")
    params: dict[str, object] = {"query": normalized_query, "page": page}
    if nickname is not None:
        params["nickname"] = _required_id(nickname, "nickname")
    return WeiboRequest("GET", _USER_SEARCH_PATH, params)


def build_user_posts_request(
    *, uid: str, page: int = 1, since_id: str = "", feature: int = 3
) -> WeiboRequest:
    """构造 Web V2 用户历史微博请求；feature=3 保留完整卡片字段。"""

    if page < 1:
        raise ValueError("page 必须从 1 开始")
    if isinstance(feature, bool) or not isinstance(feature, int) or feature not in range(4):
        raise ValueError("feature 必须是 0 到 3 的整数")
    params: dict[str, object] = {
        "uid": _required_id(uid, "uid"),
        "page": page,
        "feature": feature,
    }
    normalized_since_id = since_id.strip()
    if normalized_since_id:
        params["since_id"] = normalized_since_id
    return WeiboRequest("GET", _USER_POSTS_PATH, params)


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


def build_web_status_comments_candidate_request(
    *, status_id: str, max_id: str = "", count: int = 10
) -> WeiboRequest:
    """构造 Web V2 一级评论 A/B 候选；显式调用且不会替代 App 主链。"""
    if count < 1:
        raise ValueError("count 必须大于 0")
    return WeiboRequest(
        "GET",
        _WEB_COMMENTS_CANDIDATE_PATH,
        {
            "id": _required_id(status_id, "status_id"),
            "count": count,
            "max_id": max_id,
        },
    )


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
        card for card in cards if isinstance(card, dict) and _has_stable_id(card.get("mblog"))
    )


def extract_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 Web V2 用户搜索常见 envelope 提取含 UID 的候选。"""

    return _find_user_search_items(body)


def extract_user_post_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 Web V2 用户历史微博 envelope 提取可映射的微博卡片。"""

    container, items = _find_user_posts_container(body)
    if container is None:
        raise ValueError("weibo 账号作品响应缺少有效作品列表")
    return items


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
        if isinstance(item, dict) and _has_stable_id(item.get("data"))
    )


def _has_stable_id(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return any(_string(value.get(key)) for key in ("idstr", "mid", "id"))


def _first_level_comment_max_id(body: dict[str, Any]) -> str:
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("微博一级评论响应缺少 data")
    more_info = data.get("moreInfo")
    if more_info is None:
        return ""
    if not isinstance(more_info, dict):
        raise ValueError("微博一级评论响应 data.moreInfo 类型非法")
    params = more_info.get("params")
    if not isinstance(params, dict) or "max_id" not in params:
        raise ValueError("微博一级评论响应缺少官方 max_id 路径")
    return _string(params.get("max_id"))


def _find_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    queue: list[dict[str, Any]] = [body]
    seen: set[int] = set()
    for _ in range(64):
        if not queue:
            break
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        for key in ("users", "user_list", "userList", "cards", "items", "data", "list"):
            value = current.get(key)
            if isinstance(value, list):
                items = tuple(
                    item for item in value if isinstance(item, dict) and _is_user_search_item(item)
                )
                if items:
                    return items
            elif isinstance(value, dict):
                queue.append(value)
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return ()


def _find_user_posts_container(
    body: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], ...]]:
    queue: list[dict[str, Any]] = [body]
    seen: set[int] = set()
    for _ in range(64):
        if not queue:
            break
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        for key in ("statuses", "mblogs", "cards", "items", "list", "data"):
            value = current.get(key)
            if not isinstance(value, list):
                continue
            # 坏项保留索引并交给 Mapper/账号失败账本，不把过滤后集合当结束证据。
            items = tuple(item if isinstance(item, dict) else {} for item in value)
            if isinstance(value, list):
                return current, items
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return None, ()


def _is_user_search_item(item: dict[str, Any]) -> bool:
    candidate = item.get("user")
    if not isinstance(candidate, dict):
        candidate = item.get("userInfo")
    if not isinstance(candidate, dict):
        candidate = item
    uid = _string(candidate.get("uid") or candidate.get("user_id") or candidate.get("id"))
    identity_keys = ("screen_name", "nickname", "nick_name", "profile_url")
    return bool(uid and any(key in candidate for key in identity_keys))


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
    "WeiboUserPostsPagination",
    "build_app_search_candidate_request",
    "build_search_request",
    "build_status_comments_request",
    "build_status_detail_request",
    "build_status_sub_comments_request",
    "build_user_posts_request",
    "build_user_search_request",
    "build_web_status_comments_candidate_request",
    "extract_comment_items",
    "extract_detail_item",
    "extract_search_items",
    "extract_user_post_items",
    "extract_user_search_items",
]
