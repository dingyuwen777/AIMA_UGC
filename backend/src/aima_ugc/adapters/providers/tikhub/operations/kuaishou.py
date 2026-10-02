"""TikHub 快手 App 主 Operation、Web 已验证备用 Operation 与 pcursor 状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/kuaishou/app/search_video_v2"
_COMPREHENSIVE_SEARCH_CANDIDATE_PATH = "/api/v1/kuaishou/app/search_comprehensive"
_DETAIL_PATH = "/api/v1/kuaishou/app/fetch_one_video"
_APP_COMMENTS_PATH = "/api/v1/kuaishou/app/fetch_video_comment"
_APP_SUB_COMMENTS_PATH = "/api/v1/kuaishou/app/fetch_video_sub_comments"
_WEB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_comment"
_WEB_SUB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_sub_comment"
_USER_PROFILE_PATH = "/api/v1/kuaishou/app/fetch_one_user_v2"
_USER_POSTS_PATH = "/api/v1/kuaishou/app/fetch_user_post_v2"
_USER_SEARCH_PATH = "/api/v1/kuaishou/app/search_user_v2"
_TERMINAL_PCURSORS = frozenset({"no_more"})
_COMPREHENSIVE_SORT_TYPES = {
    "general": "all",
    "latest": "newest",
    "most_liked": "most_likes",
}
_COMPREHENSIVE_PUBLISH_TIMES = {
    "all": "all",
    "day": "one_day",
    "week": "one_week",
    "month": "one_month",
}
_COMPREHENSIVE_DURATIONS = {
    "all": "all",
    "under_1m": "under_1_min",
    "1_5m": "1_to_5_min",
    "over_5m": "over_5_min",
}


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
        if _is_terminal_pcursor(normalized):
            return cls(normalized, False, "provider_exhausted")
        if normalized == previous_cursor:
            return cls(normalized, False, "pagination_not_advanced")
        return cls(normalized, True)

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: str,
        body: dict[str, Any],
        item_key: str,
    ) -> KuaishouCursorPagination:
        """按真实 App 主链/Web 备用链共有的 data.<item_key>/pcursor 推进分页。"""
        data = body.get("data")
        if not isinstance(data, dict):
            return cls(previous_cursor, False, "response_data_unavailable")
        items = data.get(item_key)
        if not isinstance(items, list):
            return cls(previous_cursor, False, "items_unavailable")
        returned = data.get("pcursor")
        next_cursor = str(returned).strip() if returned is not None else previous_cursor
        if not items:
            return cls(next_cursor, False, "empty_page")
        if returned is None or not next_cursor:
            return cls(previous_cursor, False, "cursor_unavailable")
        if _is_terminal_pcursor(next_cursor):
            return cls(next_cursor, False, "provider_exhausted")
        if next_cursor == previous_cursor:
            return cls(next_cursor, False, "pagination_not_advanced")
        return cls(next_cursor, True)


@dataclass(frozen=True, slots=True)
class KuaishouSearchPagination:
    """Search V2 按真实 data.pcursor 推进，并识别已验证的结束游标。"""

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
        if _is_terminal_pcursor(normalized):
            return cls(normalized, False, "provider_exhausted")
        if normalized == previous_cursor:
            return cls(normalized, False, "pagination_not_advanced")
        return cls(normalized, True)


@dataclass(frozen=True, slots=True)
class KuaishouUserPostsPagination:
    """用户作品 V2 按响应中的 pcursor 推进。"""

    next_cursor: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: str,
        body: dict[str, Any],
    ) -> KuaishouUserPostsPagination:
        container, items = _find_user_posts_container(body)
        if container is None:
            return cls(previous_cursor, False, "response_data_unavailable")
        returned = container.get("pcursor")
        next_cursor = str(returned).strip() if returned is not None else previous_cursor
        if not items:
            return cls(next_cursor, False, "empty_page")
        if returned is None or not next_cursor:
            return cls(previous_cursor, False, "cursor_unavailable")
        if _is_terminal_pcursor(next_cursor):
            return cls(next_cursor, False, "provider_exhausted")
        if next_cursor == previous_cursor:
            return cls(next_cursor, False, "pagination_not_advanced")
        return cls(next_cursor, True)


@dataclass(frozen=True, slots=True)
class KuaishouUserSearchPagination:
    """用户搜索 V2 使用官方页号参数，响应游标仅用于识别耗尽。"""

    next_page: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        current_page: int,
        body: dict[str, Any],
    ) -> KuaishouUserSearchPagination:
        container, items = _find_user_search_container(body)
        if container is None:
            return cls(current_page, False, "response_data_unavailable")
        returned = container.get("pcursor")
        next_cursor = str(returned).strip() if returned is not None else ""
        if not items:
            return cls(current_page, False, "empty_page")
        if _is_terminal_pcursor(next_cursor) or container.get("has_more") is False:
            return cls(current_page, False, "provider_exhausted")
        return cls(current_page + 1, True)


def build_search_request(*, keyword: str, pcursor: str = "") -> KuaishouRequest:
    normalized_keyword = _required_text(keyword, "keyword")
    return KuaishouRequest(
        method="GET",
        path=_SEARCH_PATH,
        params={"keyword": normalized_keyword, "pcursor": pcursor},
    )


def build_comprehensive_search_candidate_request(
    *,
    keyword: str,
    pcursor: str = "",
    sort_mode: str = "general",
    publish_time: str = "all",
    duration: str = "all",
) -> KuaishouRequest:
    """构造 App 综合搜索 A/B 候选；语义含非视频对象，不能视为 Web 或视频搜索等价备用。"""
    return KuaishouRequest(
        method="GET",
        path=_COMPREHENSIVE_SEARCH_CANDIDATE_PATH,
        params={
            "keyword": _required_text(keyword, "keyword"),
            "pcursor": pcursor,
            "sort_type": _choice(_COMPREHENSIVE_SORT_TYPES, sort_mode, "sort_mode"),
            "publish_time": _choice(_COMPREHENSIVE_PUBLISH_TIMES, publish_time, "publish_time"),
            "duration": _choice(_COMPREHENSIVE_DURATIONS, duration, "duration"),
        },
    )


def build_video_detail_request(*, photo_id: str) -> KuaishouRequest:
    return KuaishouRequest(
        method="GET",
        path=_DETAIL_PATH,
        params={"photo_id": _required_text(photo_id, "photo_id")},
    )


def build_user_profile_request(*, user_id: str) -> KuaishouRequest:
    """构造快手用户 V2 资料调用；支持主页 eid 或纯数字 userId。"""
    return KuaishouRequest(
        method="GET",
        path=_USER_PROFILE_PATH,
        params={"user_id": _required_text(user_id, "user_id")},
    )


def build_user_search_request(*, keyword: str, page: int = 1) -> KuaishouRequest:
    """构造快手用户 V2 搜索，用于快手号/昵称解析数字 userId。"""
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("page 必须是正整数")
    return KuaishouRequest(
        method="GET",
        path=_USER_SEARCH_PATH,
        params={
            "keyword": _required_text(keyword, "keyword"),
            "page": str(page),
        },
    )


def build_user_posts_request(
    *,
    user_id: str,
    pcursor: str = "",
    sort: Literal["latest", "hot"] = "latest",
) -> KuaishouRequest:
    """构造快手用户作品 V2 调用；该接口要求纯数字 userId。"""
    normalized_user_id = _required_text(user_id, "user_id")
    if not normalized_user_id.isdigit():
        raise ValueError("快手用户作品接口 user_id 必须是纯数字")
    if sort not in {"latest", "hot"}:
        raise ValueError("sort 只能是 latest 或 hot")
    return KuaishouRequest(
        method="GET",
        path=_USER_POSTS_PATH,
        params={"user_id": normalized_user_id, "pcursor": pcursor, "sort": sort},
    )


def build_app_video_comments_request(*, photo_id: str, pcursor: str = "") -> KuaishouRequest:
    """构造已批准的 Kuaishou App 一级评论主请求。"""
    return KuaishouRequest(
        method="GET",
        path=_APP_COMMENTS_PATH,
        params={"photo_id": _required_text(photo_id, "photo_id"), "pcursor": pcursor},
    )


def build_app_video_sub_comments_request(
    *,
    photo_id: str,
    root_comment_id: str,
    pcursor: str = "",
    count: int = 8,
) -> KuaishouRequest:
    """构造已批准的 Kuaishou App 二级回复主请求。"""
    if count < 1 or count > 20:
        raise ValueError("count 必须在 1..20 之间")
    return KuaishouRequest(
        method="GET",
        path=_APP_SUB_COMMENTS_PATH,
        params={
            "photo_id": _required_text(photo_id, "photo_id"),
            "root_comment_id": _required_text(root_comment_id, "root_comment_id"),
            "pcursor": pcursor,
            "count": count,
        },
    )


def build_video_comments_request(*, photo_id: str, pcursor: str = "") -> KuaishouRequest:
    """构造当前生产主链一级评论请求；首版固定使用 App，不自动回退 Web。"""
    return build_app_video_comments_request(photo_id=photo_id, pcursor=pcursor)


def build_video_sub_comments_request(
    *,
    photo_id: str,
    root_comment_id: str,
    pcursor: str = "",
    count: int = 8,
) -> KuaishouRequest:
    """构造当前生产主链二级评论请求；首版固定使用 App，不自动回退 Web。"""
    return build_app_video_sub_comments_request(
        photo_id=photo_id,
        root_comment_id=root_comment_id,
        pcursor=pcursor,
        count=count,
    )


def build_web_video_comments_request(*, photo_id: str, pcursor: str = "") -> KuaishouRequest:
    """构造已真实验证的 Web 一级评论备用请求；生产主链不会自动调用。"""
    return KuaishouRequest(
        method="GET",
        path=_WEB_COMMENTS_PATH,
        params={"photo_id": _required_text(photo_id, "photo_id"), "pcursor": pcursor},
    )


def build_web_video_sub_comments_request(
    *,
    photo_id: str,
    root_comment_id: str,
    pcursor: str = "",
) -> KuaishouRequest:
    """构造已真实验证的 Web 二级评论备用请求；生产主链不会自动调用。"""
    return KuaishouRequest(
        method="GET",
        path=_WEB_SUB_COMMENTS_PATH,
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


def extract_detail_item(body: dict[str, Any]) -> dict[str, Any]:
    """从真实 App Detail 的 data.photos 提取第一条作品。"""
    data = body.get("data")
    photos = data.get("photos") if isinstance(data, dict) else None
    if not isinstance(photos, list) or not photos or not isinstance(photos[0], dict):
        raise ValueError("快手详情响应缺少非空 data.photos")
    return photos[0]


def extract_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App 主链/Web 备用链共有的 data.rootComments 提取一级评论。"""
    data = body.get("data")
    if not isinstance(data, dict):
        return ()
    items = data.get("rootComments")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def extract_sub_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App 主链/Web 备用链共有的 data.subComments 提取二级评论。"""
    data = body.get("data")
    if not isinstance(data, dict):
        return ()
    items = data.get("subComments")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def extract_user_profile(body: dict[str, Any]) -> dict[str, Any]:
    """从用户 V2 响应中提取包含 userId/user_id 的身份对象。"""
    # Envelope 的 params.user_id 是请求回显，不能作为 Provider 返回的身份。
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("快手用户 V2 响应缺少 data")
    queue: list[dict[str, Any]] = [data]
    seen: set[int] = set()
    while queue and len(seen) < 64:
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        if any(key in current for key in ("user_id", "userId", "kwaiId")):
            return current
        queue.extend(value for value in current.values() if isinstance(value, dict))
    raise ValueError("快手用户 V2 响应缺少 userId/user_id")


def extract_user_post_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """提取用户作品 V2 的视频卡片，兼容当前常见 envelope。"""
    container, items = _find_user_posts_container(body)
    if container is None:
        raise ValueError("kuaishou 账号作品响应缺少有效作品列表")
    return items


def extract_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """提取用户搜索 V2 候选，兼容常见用户列表 envelope。"""
    _, items = _find_user_search_container(body)
    return items


def extract_comment_counts(body: dict[str, Any]) -> tuple[int | None, int | None]:
    """提取快手评论接口可选的总评论数；一级评论数没有稳定字段。"""
    data = body.get("data")
    if not isinstance(data, dict):
        return None, None
    return _nonnegative_integer(data.get("commentCount", data.get("comment_count"))), None


def _find_user_posts_container(
    body: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], ...]]:
    data = body.get("data")
    if not isinstance(data, dict):
        return None, ()
    queue: list[dict[str, Any]] = [data]
    seen: set[int] = set()
    item_keys = ("feeds", "photos", "photoList", "photo_list", "items", "list")
    while queue and len(seen) < 64:
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        for key in item_keys:
            value = current.get(key)
            if not isinstance(value, list):
                continue
            # 坏项保留索引并交给 Mapper/账号失败账本，不把过滤后集合当结束证据。
            items = tuple(item if isinstance(item, dict) else {} for item in value)
            if isinstance(value, list):
                return current, items
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return None, ()


def _find_user_search_container(
    body: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], ...]]:
    data = body.get("data")
    if not isinstance(data, dict):
        return None, ()
    queue: list[dict[str, Any]] = [data]
    seen: set[int] = set()
    item_keys = (
        "mixFeeds",
        "users",
        "userList",
        "user_list",
        "userResults",
        "user_results",
        "items",
        "list",
    )
    while queue and len(seen) < 64:
        current = queue.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        for key in item_keys:
            value = current.get(key)
            if not isinstance(value, list):
                continue
            items = tuple(
                item for item in value if isinstance(item, dict) and _is_user_search_item(item)
            )
            if items or not value:
                return current, items
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return None, ()


def _is_user_search_item(item: dict[str, Any]) -> bool:
    candidate = item.get("user")
    if not isinstance(candidate, dict):
        candidate = item.get("userInfo")
    if not isinstance(candidate, dict):
        candidate = item
    return any(
        key in candidate
        for key in (
            "userId",
            "user_id",
            "kwaiId",
            "kwai_id",
            "eid",
            "userName",
            "user_name",
        )
    )


def _is_terminal_pcursor(value: str) -> bool:
    """识别真实快手响应已验证的分页结束哨兵。"""

    return value.strip().casefold() in _TERMINAL_PCURSORS


def _nonnegative_integer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _choice(mapping: dict[str, str], value: str, field_name: str) -> str:
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"{field_name} 不支持: {value}; 可选: {', '.join(mapping)}") from exc


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


__all__ = [
    "KuaishouCursorPagination",
    "KuaishouRequest",
    "KuaishouSearchPagination",
    "KuaishouUserPostsPagination",
    "KuaishouUserSearchPagination",
    "build_app_video_comments_request",
    "build_app_video_sub_comments_request",
    "build_comprehensive_search_candidate_request",
    "build_search_request",
    "build_user_posts_request",
    "build_user_profile_request",
    "build_user_search_request",
    "build_video_comments_request",
    "build_video_detail_request",
    "build_video_sub_comments_request",
    "build_web_video_comments_request",
    "build_web_video_sub_comments_request",
    "extract_comment_items",
    "extract_comment_counts",
    "extract_detail_item",
    "extract_search_items",
    "extract_sub_comment_items",
    "extract_user_post_items",
    "extract_user_profile",
    "extract_user_search_items",
]
