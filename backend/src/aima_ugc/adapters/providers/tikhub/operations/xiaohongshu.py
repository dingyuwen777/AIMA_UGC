"""TikHub 小红书 App V2 主 Operation 与 App V1/Web V3 A/B 候选。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_BASE = "/api/v1/xiaohongshu/app_v2"
_APP_V1_BASE = "/api/v1/xiaohongshu/app"
_WEB_V3_BASE = "/api/v1/xiaohongshu/web_v3"
_SORT_TYPES = {
    "general": "general",
    "latest": "time_descending",
    "most_liked": "popularity_descending",
    "most_commented": "comment_descending",
    "most_collected": "collect_descending",
    "english_preferred": "english_preferred",
}
_TIME_FILTERS = {
    "all": "不限",
    "1d": "一天内",
    "7d": "一周内",
    "180d": "半年内",
}
_NOTE_TYPES = {
    "all": "不限",
    "video": "视频笔记",
    "image": "普通笔记",
    "live": "直播笔记",
}


@dataclass(frozen=True, slots=True)
class XiaohongshuRequest:
    """一次小红书 Operation 的脱敏请求描述。"""

    path: str
    params: dict[str, object]


@dataclass(frozen=True, slots=True)
class XiaohongshuSearchPagination:
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
    ) -> XiaohongshuSearchPagination:
        """从笔记搜索响应构造下一页状态，并拒绝空页、重复页和停滞页。"""
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
class XiaohongshuUserSearchPagination:
    """用户搜索下一页状态和停止原因。"""

    next_page: int
    search_id: str | None
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
    ) -> XiaohongshuUserSearchPagination:
        """按 search_id 推进用户搜索，避免缺失会话状态后继续产生无效付费请求。"""
        metadata = _find_mapping(body, required_any=("search_id", "next_page"))
        items = extract_user_search_items(body)
        search_id = _string(metadata.get("search_id"))
        next_page = _integer(metadata.get("next_page"), default=current_page + 1)
        if not items:
            return cls(next_page, search_id, (), False, "empty_page")

        item_ids = tuple(filter(None, (_user_item_id(item) for item in items)))
        if item_ids and item_ids == previous_item_ids:
            return cls(next_page, search_id, item_ids, False, "duplicate_page")

        page_data = _find_mapping(body, required_any=("users", "items", "has_more"))
        has_more = _first_value((page_data, metadata), "has_more")
        if has_more is False:
            return cls(next_page, search_id, item_ids, False, "provider_exhausted")
        if next_page <= current_page:
            return cls(next_page, search_id, item_ids, False, "pagination_not_advanced")
        if not search_id:
            return cls(next_page, None, item_ids, False, "search_id_unavailable")
        return cls(next_page, search_id, item_ids, True)


@dataclass(frozen=True, slots=True)
class XiaohongshuUserNotesPagination:
    """用户已发布笔记 cursor 分页状态和停止原因。"""

    next_cursor: str | None
    item_ids: tuple[str, ...]
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: str,
        body: dict[str, Any],
        previous_item_ids: tuple[str, ...] = (),
    ) -> XiaohongshuUserNotesPagination:
        """从用户笔记列表最后一条笔记推进 cursor，并拒绝重复页和停滞 cursor。"""
        items = extract_user_posted_note_items(body)
        if not items:
            return cls(None, (), False, "empty_page")

        item_ids = tuple(filter(None, (_posted_note_item_id(item) for item in items)))
        if item_ids and item_ids == previous_item_ids:
            return cls(None, item_ids, False, "duplicate_page")

        page_data = _find_mapping(body, required_any=("notes", "has_more"))
        if page_data.get("has_more") is False:
            return cls(None, item_ids, False, "provider_exhausted")

        next_cursor = _posted_note_cursor(items[-1])
        if not next_cursor:
            return cls(None, item_ids, False, "cursor_unavailable")
        if next_cursor == previous_cursor:
            return cls(next_cursor, item_ids, False, "pagination_not_advanced")
        return cls(next_cursor, item_ids, True)


@dataclass(frozen=True, slots=True)
class XiaohongshuCommentPagination:
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
    ) -> XiaohongshuCommentPagination:
        """从一级/二级评论响应推进 cursor/index/pageArea。"""
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
    sort_type: str = "general",
    time_filter: str = "all",
    note_type: str = "all",
    source: str = "explore_feed",
    search_id: str | None = None,
    search_session_id: str | None = None,
) -> XiaohongshuRequest:
    """接受规范化业务枚举；既有 Provider 原值仍兼容。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    params: dict[str, object] = {
        "keyword": normalized_keyword,
        "page": page,
        "sort_type": _mapped_or_provider_value(_SORT_TYPES, sort_type, "sort_type"),
        "note_type": _mapped_or_provider_value(_NOTE_TYPES, note_type, "note_type"),
        "time_filter": _mapped_or_provider_value(_TIME_FILTERS, time_filter, "time_filter"),
        "source": source,
    }
    if search_id:
        params["search_id"] = search_id
    if search_session_id:
        params["search_session_id"] = search_session_id
    return XiaohongshuRequest(f"{_BASE}/search_notes", params)


def build_search_users_request(
    *,
    keyword: str,
    page: int = 1,
    search_id: str | None = None,
    source: str = "explore_feed",
) -> XiaohongshuRequest:
    """构造 App V2 用户搜索；翻页只复用首次响应的 search_id。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    params: dict[str, object] = {
        "keyword": normalized_keyword,
        "page": page,
        "source": source,
    }
    if search_id:
        params["search_id"] = search_id
    return XiaohongshuRequest(f"{_BASE}/search_users", params)


def build_user_info_request(
    *,
    user_id: str | None = None,
    share_text: str | None = None,
) -> XiaohongshuRequest:
    """构造 App V2 用户详情；优先稳定 user_id，缺失时才接受分享文本。"""
    return XiaohongshuRequest(
        f"{_BASE}/get_user_info",
        _user_lookup_params(user_id=user_id, share_text=share_text),
    )


def build_user_posted_notes_request(
    *,
    user_id: str | None = None,
    share_text: str | None = None,
    cursor: str = "",
) -> XiaohongshuRequest:
    """构造 App V2 用户已发布笔记请求；cursor 为空表示第一页。"""
    params = _user_lookup_params(user_id=user_id, share_text=share_text)
    params["cursor"] = cursor
    return XiaohongshuRequest(f"{_BASE}/get_user_posted_notes", params)


def build_app_v1_search_candidate_request(
    *,
    keyword: str,
    page: int = 1,
    sort_type: str = "general",
    note_type: str = "不限",
    time_filter: str = "不限",
    search_id: str | None = None,
    session_id: str | None = None,
) -> XiaohongshuRequest:
    """构造 App V1 Search A/B 候选；不进入默认 Capability 或自动 fallback。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    params: dict[str, object] = {
        "keyword": normalized_keyword,
        "page": page,
        "sort_type": sort_type,
        "filter_note_type": note_type,
        "filter_note_time": time_filter,
    }
    if search_id:
        params["search_id"] = search_id
    if session_id:
        params["session_id"] = session_id
    return XiaohongshuRequest(f"{_APP_V1_BASE}/search_notes", params)


def build_web_v3_search_candidate_request(
    *, keyword: str, page: int = 1, sort: str = "general", note_type: int = 0
) -> XiaohongshuRequest:
    """构造 Web V3 Search A/B 候选；不进入默认 Capability 或自动 fallback。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    return XiaohongshuRequest(
        f"{_WEB_V3_BASE}/fetch_search_notes",
        {"keyword": normalized_keyword, "page": page, "sort": sort, "note_type": note_type},
    )


def build_image_detail_request(*, note_id: str) -> XiaohongshuRequest:
    """构造图文笔记详情请求。"""
    return XiaohongshuRequest(f"{_BASE}/get_image_note_detail", {"note_id": note_id})


def build_video_detail_request(*, note_id: str) -> XiaohongshuRequest:
    """构造视频笔记详情请求。"""
    return XiaohongshuRequest(f"{_BASE}/get_video_note_detail", {"note_id": note_id})


def build_app_v1_detail_candidate_request(*, note_id: str) -> XiaohongshuRequest:
    """构造 App V1 笔记详情 A/B 候选。"""
    return XiaohongshuRequest(f"{_APP_V1_BASE}/get_note_info", {"note_id": note_id})


def build_web_v3_detail_candidate_request(*, note_id: str, xsec_token: str) -> XiaohongshuRequest:
    """构造 Web V3 笔记详情 A/B 候选；官方接口要求显式 xsec_token。"""
    return XiaohongshuRequest(
        f"{_WEB_V3_BASE}/fetch_note_detail",
        {"note_id": note_id, "xsec_token": xsec_token},
    )


def build_note_comments_request(
    *, note_id: str, cursor: str = "", index: int = 0, page_area: str = "UNFOLDED"
) -> XiaohongshuRequest:
    """构造当前正式 App V2 一级评论请求。"""
    return XiaohongshuRequest(
        f"{_BASE}/get_note_comments",
        {
            "note_id": note_id,
            "cursor": cursor,
            "index": index,
            "pageArea": page_area,
            "sort_strategy": "latest_v2",
        },
    )


def build_app_v1_comments_candidate_request(
    *, note_id: str, start: str = "", sort_strategy: int = 1
) -> XiaohongshuRequest:
    """构造 App V1 一级评论 A/B 候选。"""
    return XiaohongshuRequest(
        f"{_APP_V1_BASE}/get_note_comments",
        {"note_id": note_id, "start": start, "sort_strategy": sort_strategy},
    )


def build_web_v3_comments_candidate_request(
    *, note_id: str, xsec_token: str, cursor: str = ""
) -> XiaohongshuRequest:
    """构造 Web V3 一级评论 A/B 候选；官方接口要求显式 xsec_token。"""
    return XiaohongshuRequest(
        f"{_WEB_V3_BASE}/fetch_note_comments",
        {"note_id": note_id, "xsec_token": xsec_token, "cursor": cursor},
    )


def build_sub_comments_request(
    *, note_id: str, comment_id: str, cursor: str = "", index: int = 1
) -> XiaohongshuRequest:
    """构造当前正式 App V2 二级评论请求。"""
    return XiaohongshuRequest(
        f"{_BASE}/get_note_sub_comments",
        {
            "note_id": note_id,
            "comment_id": comment_id,
            "cursor": cursor,
            "index": index,
        },
    )


def build_app_v1_sub_comments_candidate_request(
    *, note_id: str, comment_id: str, start: str = ""
) -> XiaohongshuRequest:
    """构造 App V1 二级评论 A/B 候选。"""
    return XiaohongshuRequest(
        f"{_APP_V1_BASE}/get_sub_comments",
        {"note_id": note_id, "comment_id": comment_id, "start": start},
    )


def build_web_v3_sub_comments_candidate_request(
    *,
    note_id: str,
    root_comment_id: str,
    xsec_token: str,
    num: int = 10,
    cursor: str = "",
) -> XiaohongshuRequest:
    """构造 Web V3 二级评论 A/B 候选；官方接口要求显式 xsec_token。"""
    if num < 1:
        raise ValueError("num 必须大于 0")
    return XiaohongshuRequest(
        f"{_WEB_V3_BASE}/fetch_sub_comments",
        {
            "note_id": note_id,
            "root_comment_id": root_comment_id,
            "xsec_token": xsec_token,
            "num": num,
            "cursor": cursor,
        },
    )


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App V2 搜索响应中提取 item wrapper，不复制分页逻辑。"""
    page_data = _find_mapping(body, required_any=("items",))
    items = page_data.get("items")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def extract_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 App V2 用户搜索响应提取用户候选，兼容 users/items 两种 Envelope。"""
    page_data = _find_mapping(body, required_any=("users", "items"))
    values = page_data.get("users")
    if not isinstance(values, list):
        values = page_data.get("items")
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, dict))


def extract_user_info_item(body: dict[str, Any]) -> dict[str, Any] | None:
    """从 App V2 用户详情响应提取用户对象，不把 Provider Envelope 泄露给调用方。"""
    data = _find_mapping(
        body,
        required_any=("user", "user_info", "profile", "user_id", "userid", "red_id", "nickname"),
    )
    unwrapped = _unwrap_user(data)
    return unwrapped if unwrapped else None


def extract_user_posted_note_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 App V2 用户发布笔记响应提取 notes 列表。"""
    page_data = _find_mapping(body, required_any=("notes",))
    values = page_data.get("notes")
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, dict))


def extract_detail_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """统一提取图文 detail 的 note_list 与视频 detail 的直接 note item。"""
    outer = body.get("data")
    if not isinstance(outer, dict):
        return ()
    items = outer.get("data")
    if not isinstance(items, list):
        return ()
    extracted: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        note_list = item.get("note_list")
        if isinstance(note_list, list):
            extracted.extend(note for note in note_list if isinstance(note, dict))
        elif "id" in item or "note_id" in item:
            extracted.append(item)
    return tuple(extracted)


def extract_comment_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实一级/二级评论响应提取 comments。"""
    data = _find_mapping(body, required_any=("comments",))
    items = data.get("comments")
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, dict))


def _user_lookup_params(
    *,
    user_id: str | None,
    share_text: str | None,
) -> dict[str, object]:
    """规范化用户定位参数；不允许空定位产生仍会计费的 Provider 请求。"""
    normalized_user_id = user_id.strip() if isinstance(user_id, str) else ""
    normalized_share_text = share_text.strip() if isinstance(share_text, str) else ""
    if normalized_user_id:
        return {"user_id": normalized_user_id}
    if normalized_share_text:
        return {"share_text": normalized_share_text}
    raise ValueError("user_id 与 share_text 至少提供一个")


def _mapped_or_provider_value(mapping: dict[str, str], value: str, field_name: str) -> str:
    """把规范化业务枚举映射为 Provider 原值。"""
    normalized = value.strip()
    if normalized in mapping:
        return mapping[normalized]
    if normalized in mapping.values():
        return normalized
    raise ValueError(f"{field_name} 不支持: {value}; 可选: {', '.join(mapping)}")


def _find_mapping(body: dict[str, Any], *, required_any: tuple[str, ...]) -> dict[str, Any]:
    """沿常见 data Envelope 向内寻找包含目标字段的映射。"""
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
    """按候选映射顺序返回第一个存在的字段值。"""
    for mapping in mappings:
        if key in mapping:
            return mapping[key]
    return None


def _search_item_id(item: object) -> str:
    """提取搜索卡片中的稳定 note_id。"""
    if not isinstance(item, dict):
        return ""
    note = item.get("note")
    if isinstance(note, dict):
        return _string(note.get("id") or note.get("note_id")) or ""
    return _string(item.get("id") or item.get("note_id")) or ""


def _user_item_id(item: object) -> str:
    """提取用户搜索候选中的稳定 user_id。"""
    if not isinstance(item, dict):
        return ""
    user = _unwrap_user(item)
    return _string(
        user.get("user_id") or user.get("userid") or user.get("userId") or user.get("id")
    ) or ""


def _unwrap_user(raw: dict[str, Any]) -> dict[str, Any]:
    """兼容用户搜索/详情中的常见 user wrapper。"""
    for key in ("user", "user_info", "userInfo", "profile"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _posted_note_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """兼容用户笔记列表中的直接 note 与 wrapper 结构。"""
    for key in ("note", "note_card", "noteCard"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _posted_note_item_id(item: object) -> str:
    """提取用户笔记列表中的稳定 note_id。"""
    if not isinstance(item, dict):
        return ""
    note = _posted_note_payload(item)
    return _string(note.get("note_id") or note.get("id")) or ""


def _posted_note_cursor(item: object) -> str | None:
    """提取用户笔记项 cursor；缺失时按官方说明回退到 note_id。"""
    if not isinstance(item, dict):
        return None
    note = _posted_note_payload(item)
    return (
        _string(note.get("cursor"))
        or _string(item.get("cursor"))
        or _string(note.get("note_id") or note.get("id"))
    )


def _string(value: object) -> str | None:
    """把非空 Provider 标量规范化为字符串。"""
    return str(value) if value is not None and str(value) else None


def _integer(value: object, *, default: int) -> int:
    """把 Provider 数字字段安全规范化为整数。"""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
