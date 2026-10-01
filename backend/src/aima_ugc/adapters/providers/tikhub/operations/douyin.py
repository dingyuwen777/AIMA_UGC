"""TikHub 抖音 Search V2 / App V3 Operation 与分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/douyin/search/fetch_video_search_v2"
_SEARCH_V1_CANDIDATE_PATH = "/api/v1/douyin/search/fetch_video_search_v1"
_APP_V3_BASE = "/api/v1/douyin/app/v3"
_DEFAULT_USER_POSTS_PATH = "/api/v1/douyin/app/v3/fetch_user_post_videos"
_DEFAULT_USER_PROFILE_PATH = "/api/v1/douyin/web/handler_user_profile_v2"

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


@dataclass(frozen=True, slots=True)
class DouyinUserPostsPagination:
    """按账号作品接口返回的 max_cursor/has_more 推进分页。"""

    next_cursor: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: int,
        body: dict[str, Any],
        items_path: str = "data.aweme_list",
        cursor_path: str = "data.max_cursor",
        has_more_path: str = "data.has_more",
    ) -> DouyinUserPostsPagination:
        items = _path_value(body, items_path)
        next_cursor = _integer(
            _path_value(body, cursor_path),
            default=previous_cursor,
        )
        has_more = _path_value(body, has_more_path)
        if not isinstance(items, list):
            return cls(next_cursor, False, "response_data_unavailable")
        if not items:
            return cls(next_cursor, False, "empty_page")
        if _provider_exhausted(has_more):
            return cls(next_cursor, False, "provider_exhausted")
        # 抖音 App V3 的 max_cursor 是按发布时间倒序翻页的时间戳，
        # 正常下一页会比上一页更小；只有游标完全不变才是真正的卡住。
        if next_cursor == previous_cursor:
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
    return _build_video_search_request(
        path=_SEARCH_PATH,
        keyword=keyword,
        cursor=cursor,
        sort_mode=sort_mode,
        published_within=published_within,
        duration=duration,
        content_type=content_type,
        search_id=search_id,
        backtrace=backtrace,
    )


def build_video_search_v1_candidate_request(
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
    """构造同业务语义的 Search V1 A/B 候选；不进入默认 Capability 或自动 fallback。"""
    return _build_video_search_request(
        path=_SEARCH_V1_CANDIDATE_PATH,
        keyword=keyword,
        cursor=cursor,
        sort_mode=sort_mode,
        published_within=published_within,
        duration=duration,
        content_type=content_type,
        search_id=search_id,
        backtrace=backtrace,
    )


def _build_video_search_request(
    *,
    path: str,
    keyword: str,
    cursor: int,
    sort_mode: str,
    published_within: str,
    duration: str,
    content_type: str,
    search_id: str,
    backtrace: str,
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
    return DouyinRequest("POST", path, {}, body)


def build_video_detail_request(*, aweme_id: str) -> DouyinRequest:
    return DouyinRequest(
        "GET",
        f"{_APP_V3_BASE}/fetch_one_video_v3",
        {"aweme_id": _required_id(aweme_id, "aweme_id")},
    )


def build_video_detail_by_share_url_request(*, share_url: str) -> DouyinRequest:
    """通过已验证的 App V3 分享链接详情接口取得视频身份。"""

    return DouyinRequest(
        "GET", f"{_APP_V3_BASE}/fetch_one_video_by_share_url", {"share_url": share_url}
    )


def build_user_posted_videos_request(
    *,
    account_value: str,
    cursor: int = 0,
    path: str = _DEFAULT_USER_POSTS_PATH,
    method: Literal["GET", "POST"] = "GET",
    account_param: str = "sec_user_id",
    cursor_param: str = "max_cursor",
) -> DouyinRequest:
    """构造抖音指定账号作品请求；路径和参数名可按 TikHub 账号接口配置。"""

    normalized_path = _required_path(path)
    normalized_account_param = _required_text(account_param, "account_param")
    normalized_cursor_param = _required_text(cursor_param, "cursor_param")
    if method not in {"GET", "POST"}:
        raise ValueError("method 只能是 GET 或 POST")
    _nonnegative_cursor(cursor)
    payload: dict[str, object] = {
        normalized_account_param: _required_id(account_value, "account_value"),
        normalized_cursor_param: cursor,
    }
    if method == "POST":
        return DouyinRequest(method, normalized_path, {}, payload)
    return DouyinRequest(method, normalized_path, payload)


def build_user_profile_request(
    *,
    unique_id: str,
    path: str = _DEFAULT_USER_PROFILE_PATH,
    method: Literal["GET"] = "GET",
    id_param: str = "unique_id",
) -> DouyinRequest:
    """构造按抖音号解析用户 sec_uid 的请求。"""

    normalized_path = _required_path(path)
    normalized_id_param = _required_text(id_param, "id_param")
    if method != "GET":
        raise ValueError("用户资料解析接口目前只支持 GET")
    return DouyinRequest(
        method,
        normalized_path,
        {normalized_id_param: _required_id(unique_id, "unique_id")},
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
    return tuple(item for item in items if isinstance(item, dict) and _search_item_id(item))


def extract_user_posted_videos(
    body: dict[str, Any],
    *,
    items_path: str = "data.aweme_list",
) -> tuple[dict[str, Any], ...]:
    """提取指定账号作品列表，并把 Dou+ 简洁结构规范化为 App V3 结构。"""

    douplus_items = _path_value(body, "data.data.itemInfoList")
    if isinstance(douplus_items, list):
        return tuple(
            (_normalize_douplus_post(item) or item) if isinstance(item, dict) else {}
            for item in douplus_items
        )

    candidates = [items_path, "data.aweme_list", "data.data.aweme_list", "aweme_list"]
    seen_paths: set[str] = set()
    for candidate in candidates:
        if candidate in seen_paths:
            continue
        seen_paths.add(candidate)
        items = _path_value(body, candidate)
        if isinstance(items, list):
            return tuple(item if isinstance(item, dict) else {} for item in items)
    raise ValueError("抖音账号作品响应缺少作品列表")


def _normalize_douplus_post(item: dict[str, Any]) -> dict[str, Any] | None:
    aweme = item.get("AwemeInfo")
    if not isinstance(aweme, dict):
        return None
    aweme_id = _string(aweme.get("AwemeId"))
    if not aweme_id:
        return None
    author_raw = aweme.get("Author")
    author_source = author_raw if isinstance(author_raw, dict) else {}
    statistics_raw = aweme.get("Statistics")
    statistics_source = statistics_raw if isinstance(statistics_raw, dict) else {}
    video_raw = aweme.get("Video")
    video_source = video_raw if isinstance(video_raw, dict) else {}
    normalized: dict[str, Any] = {
        "aweme_id": aweme_id,
        "item_title": video_source.get("Title"),
        "desc": aweme.get("Desc"),
        "create_time": aweme.get("CreateTime"),
        "share_url": f"https://www.douyin.com/video/{aweme_id}",
        "author": {
            "sec_uid": author_source.get("SecUid"),
            "nickname": author_source.get("Nickname"),
        },
        "statistics": {
            "comment_count": statistics_source.get("CommentCount"),
            "digg_count": statistics_source.get("DiggCount"),
            "share_count": statistics_source.get("ShareCount"),
        },
    }
    if aweme.get("IsPhoto") is True:
        normalized["images"] = [{}]
    else:
        normalized["video"] = {"source": "douplus"}
    return normalized


def extract_user_profile(body: dict[str, Any]) -> dict[str, Any]:
    """从用户资料响应中提取包含 sec_uid 的用户对象。"""

    candidates: list[dict[str, Any]] = []

    def visit(value: object, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(value, dict):
            if any(key in value for key in ("sec_uid", "sec_user_id", "unique_id", "uid")):
                candidates.append(value)
            for nested in value.values():
                visit(nested, depth + 1)
        elif isinstance(value, list):
            for nested in value:
                visit(nested, depth + 1)

    visit(body)
    if not candidates:
        raise ValueError("抖音用户资料响应缺少用户身份字段")
    candidates.sort(
        key=lambda item: sum(
            key in item for key in ("sec_uid", "sec_user_id", "unique_id", "uid", "nickname")
        ),
        reverse=True,
    )
    return {str(key): value for key, value in candidates[0].items()}


def extract_detail_item(body: dict[str, Any]) -> dict[str, Any]:
    """从真实 App V3 detail 响应提取 data.aweme_detail。"""
    data = body.get("data")
    detail = data.get("aweme_detail") if isinstance(data, dict) else None
    if not isinstance(detail, dict):
        raise ValueError("抖音详情响应缺少 data.aweme_detail")
    return {str(key): value for key, value in detail.items()}


def extract_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App V3 评论/回复响应提取 data.comments。"""
    data = body.get("data")
    if not isinstance(data, dict):
        return ()
    items = data.get("comments")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def extract_comment_counts(body: dict[str, Any]) -> tuple[int | None, int | None]:
    """提取抖音评论接口返回的评论总数。

    App V3/Web 的 ``data.total`` 与作品 ``statistics.comment_count`` 一样是
    评论总数；接口没有稳定提供单独的一级评论总数。每个根评论的回复仍需
    额外按 ``reply_comment_total`` 对齐，防止总量碰巧相等却漏掉回复。
    """

    data = body.get("data")
    if not isinstance(data, dict):
        return None, None
    total = _nonnegative_integer(data.get("total"))
    return total, None


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


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空")
    return value.strip()


def _required_path(value: str) -> str:
    normalized = _required_text(value, "path")
    if not normalized.startswith("/"):
        raise ValueError("path 必须是以 / 开头的 TikHub 路径")
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


def _nonnegative_integer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _provider_exhausted(value: object) -> bool:
    return value is False or value == 0 or value == "0" or value == "false"


def _path_value(value: object, path: str) -> object:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


__all__ = [
    "DouyinCursorPagination",
    "DouyinRequest",
    "DouyinSearchPagination",
    "DouyinUserPostsPagination",
    "build_video_comment_replies_request",
    "build_video_comments_request",
    "build_video_detail_request",
    "build_video_detail_by_share_url_request",
    "build_video_search_request",
    "build_video_search_v1_candidate_request",
    "build_user_posted_videos_request",
    "build_user_profile_request",
    "extract_comment_items",
    "extract_comment_counts",
    "extract_detail_item",
    "extract_search_items",
    "extract_user_posted_videos",
    "extract_user_profile",
]
