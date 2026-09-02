"""TikHub 小红书 App V2 账号发现与用户笔记 Operation。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .xiaohongshu import XiaohongshuRequest

_BASE = "/api/v1/xiaohongshu/app_v2"


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
        """按 search_id 推进用户搜索，并拒绝空页、重复页和停滞页。"""
        metadata = _find_mapping(body, required_any=("search_id", "next_page"))
        page_data = _find_mapping(body, required_any=("users", "user_list", "items", "has_more"))
        raw_items = _find_list(body, keys=("users", "user_list", "items"))
        search_id = _string(metadata.get("search_id"))
        next_page = _integer(metadata.get("next_page"), default=current_page + 1)
        if raw_items is None:
            return cls(next_page, search_id, (), False, "response_shape_unavailable")

        items = tuple(item for item in raw_items if isinstance(item, dict))
        has_more = _first_value((page_data, metadata), "has_more")
        if not items:
            stop_reason = "empty_page_with_more" if has_more is True else "empty_page"
            return cls(next_page, search_id, (), False, stop_reason)

        item_ids = tuple(filter(None, (_user_item_id(item) for item in items)))
        if item_ids and item_ids == previous_item_ids:
            return cls(next_page, search_id, item_ids, False, "duplicate_page")

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
        """优先按响应级 cursor 推进用户笔记，并拒绝异常结构、重复页和停滞 cursor。"""
        page_data = _find_mapping(body, required_any=("notes", "has_more", "cursor"))
        raw_items = _find_list(body, keys=("notes",))
        if raw_items is None:
            return cls(None, (), False, "response_shape_unavailable")

        items = tuple(item for item in raw_items if isinstance(item, dict))
        has_more = page_data.get("has_more")
        if not items:
            stop_reason = "empty_page_with_more" if has_more is True else "empty_page"
            return cls(None, (), False, stop_reason)

        item_ids = tuple(filter(None, (_posted_note_item_id(item) for item in items)))
        if item_ids and item_ids == previous_item_ids:
            return cls(None, item_ids, False, "duplicate_page")

        if has_more is False:
            return cls(None, item_ids, False, "provider_exhausted")

        next_cursor = _string(page_data.get("cursor")) or _posted_note_cursor(items[-1])
        if not next_cursor:
            return cls(None, item_ids, False, "cursor_unavailable")
        if next_cursor == previous_cursor:
            return cls(next_cursor, item_ids, False, "pagination_not_advanced")
        return cls(next_cursor, item_ids, True)


def build_search_users_request(
    *,
    keyword: str,
    page: int = 1,
    search_id: str | None = None,
    source: str = "explore_feed",
) -> XiaohongshuRequest:
    """构造 App V2 用户搜索；翻页时复用首次响应的 search_id。"""
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


def extract_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 App V2 用户搜索响应提取用户候选，不泄露 Provider Envelope。"""
    values = _find_list(body, keys=("users", "user_list", "items"))
    if values is None:
        return ()
    return tuple(item for item in values if isinstance(item, dict))


def extract_user_info_item(body: dict[str, Any]) -> dict[str, Any] | None:
    """从 App V2 用户详情响应提取用户对象。"""
    data = _find_mapping(
        body,
        required_any=(
            "user",
            "user_info",
            "profile",
            "user_id",
            "userid",
            "red_id",
            "nickname",
        ),
    )
    user = _unwrap_user(data)
    return user if user else None


def extract_user_posted_note_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从 App V2 用户发布笔记响应提取 notes 列表。"""
    values = _find_list(body, keys=("notes",))
    if values is None:
        return ()
    return tuple(item for item in values if isinstance(item, dict))


def _user_lookup_params(
    *,
    user_id: str | None,
    share_text: str | None,
) -> dict[str, object]:
    """规范化用户定位参数，避免空定位产生仍会计费的无效请求。"""
    normalized_user_id = user_id.strip() if isinstance(user_id, str) else ""
    normalized_share_text = share_text.strip() if isinstance(share_text, str) else ""
    if normalized_user_id:
        return {"user_id": normalized_user_id}
    if normalized_share_text:
        return {"share_text": normalized_share_text}
    raise ValueError("user_id 与 share_text 至少提供一个")


def _find_mapping(body: dict[str, Any], *, required_any: tuple[str, ...]) -> dict[str, Any]:
    """沿 TikHub 常见 data Envelope 向内寻找包含目标字段的映射。"""
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


def _find_list(body: dict[str, Any], *, keys: tuple[str, ...]) -> list[object] | None:
    """沿 data Envelope 查找真实列表字段；缺失或字段类型异常返回 None。"""
    current: object = body
    for _ in range(5):
        if not isinstance(current, dict):
            return None
        for key in keys:
            if key in current:
                value = current[key]
                return value if isinstance(value, list) else None
        current = current.get("data")
    return None


def _first_value(mappings: tuple[dict[str, Any], ...], key: str) -> object:
    """按候选映射顺序返回第一个存在的字段值。"""
    for mapping in mappings:
        if key in mapping:
            return mapping[key]
    return None


def _unwrap_user(raw: dict[str, Any]) -> dict[str, Any]:
    """兼容用户搜索和用户详情中的常见 user wrapper。"""
    for key in ("user", "user_info", "userInfo", "profile"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _user_item_id(item: object) -> str:
    """提取用户搜索候选中的稳定 user_id。"""
    if not isinstance(item, dict):
        return ""
    user = _unwrap_user(item)
    value = user.get("user_id") or user.get("userid") or user.get("userId") or user.get("id")
    return _string(value) or ""


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
    """提取用户笔记 cursor；缺失时按官方说明回退到最后一条 note_id。"""
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
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


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


__all__ = [
    "XiaohongshuUserNotesPagination",
    "XiaohongshuUserSearchPagination",
    "build_search_users_request",
    "build_user_info_request",
    "build_user_posted_notes_request",
    "extract_user_info_item",
    "extract_user_posted_note_items",
    "extract_user_search_items",
]
