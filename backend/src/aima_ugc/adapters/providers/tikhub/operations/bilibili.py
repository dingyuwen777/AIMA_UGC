"""TikHub B站 App Operation 与有证据的分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/bilibili/app/fetch_search_by_type"
_DETAIL_PATH = "/api/v1/bilibili/app/fetch_one_video"
_COMMENTS_PATH = "/api/v1/bilibili/app/fetch_video_comments"
_REPLY_PATH = "/api/v1/bilibili/app/fetch_reply_detail"

_SEARCH_ORDERS = {
    "general": 0,
    "latest": 1,
    "play_count": 2,
    "danmaku_count": 3,
}
_COMMENT_SORT_MODES = {
    "latest": 2,
    "hot": 3,
}


@dataclass(frozen=True, slots=True)
class BilibiliRequest:
    """一次 B站 Operation 的脱敏请求描述。"""

    method: Literal["GET"]
    path: str
    params: dict[str, object]
    body: None = None


@dataclass(frozen=True, slots=True)
class BilibiliSearchPagination:
    """分类搜索按官方响应 cursor 推进。"""

    next_cursor: str
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_response(
        cls,
        *,
        previous_cursor: str | None,
        body: dict[str, Any],
    ) -> BilibiliSearchPagination:
        returned_cursor = _search_next_cursor(body)
        if returned_cursor == "":
            return cls("", False, "provider_exhausted")
        if previous_cursor is not None and returned_cursor == previous_cursor:
            return cls(returned_cursor, False, "pagination_not_advanced")
        return cls(returned_cursor, True)


@dataclass(frozen=True, slots=True)
class BilibiliCursorPagination:
    """评论/回复只处理调用方已可靠提取的 next_offset，不猜响应路径。"""

    next_cursor: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_returned_cursor(
        cls,
        *,
        previous_cursor: int,
        returned_cursor: int | None,
    ) -> BilibiliCursorPagination:
        if previous_cursor < 0:
            raise ValueError("previous_cursor 不能小于 0")
        if returned_cursor is None:
            return cls(previous_cursor, False, "cursor_unavailable")
        if returned_cursor < 0:
            raise ValueError("returned_cursor 不能小于 0")
        if returned_cursor <= previous_cursor:
            return cls(returned_cursor, False, "pagination_not_advanced")
        return cls(returned_cursor, True)


def build_search_request(
    *,
    keyword: str,
    cursor: str | None = None,
    sort_mode: str = "general",
    search_type: str = "video",
) -> BilibiliRequest:
    """构造 B站分类搜索请求；首版只允许视频内容。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if search_type != "video":
        raise ValueError("search_type 当前只支持 video")

    params: dict[str, object] = {
        "keyword": normalized_keyword,
        "search_type": search_type,
        "order": _choice(_SEARCH_ORDERS, sort_mode, "sort_mode"),
    }
    if cursor is not None:
        normalized_cursor = cursor.strip()
        if normalized_cursor:
            params["cursor"] = normalized_cursor
    return BilibiliRequest(method="GET", path=_SEARCH_PATH, params=params)


def build_video_detail_request(
    *,
    av_id: str | None = None,
    bv_id: str | None = None,
) -> BilibiliRequest:
    """构造 B站 App 视频详情请求；AV/BV ID 二选一。"""
    return BilibiliRequest(
        method="GET",
        path=_DETAIL_PATH,
        params=_video_identity_params(av_id=av_id, bv_id=bv_id),
    )


def build_video_comments_request(
    *,
    av_id: str | None = None,
    bv_id: str | None = None,
    sort_mode: str = "latest",
    next_offset: int | None = None,
) -> BilibiliRequest:
    """构造 B站 App 一级评论请求；首屏不发送 next_offset。"""
    params = _video_identity_params(av_id=av_id, bv_id=bv_id)
    params["mode"] = _choice(_COMMENT_SORT_MODES, sort_mode, "sort_mode")
    if next_offset is not None:
        params["next_offset"] = _non_negative_int(next_offset, "next_offset")
    return BilibiliRequest(method="GET", path=_COMMENTS_PATH, params=params)


def build_reply_detail_request(
    *,
    root: str,
    av_id: str | None = None,
    bv_id: str | None = None,
    next_offset: int | None = None,
) -> BilibiliRequest:
    """构造 B站 App 二级回复请求；不覆盖 Provider 默认 ps。"""
    params: dict[str, object] = {
        "root": _required_id(root, "root"),
        **_video_identity_params(av_id=av_id, bv_id=bv_id),
    }
    if next_offset is not None:
        params["next_offset"] = _non_negative_int(next_offset, "next_offset")
    return BilibiliRequest(method="GET", path=_REPLY_PATH, params=params)


def extract_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """从真实 App 分类搜索的 data.data.items 提取 av item。"""
    outer_data = body.get("data")
    if not isinstance(outer_data, dict):
        return ()
    provider_data = outer_data.get("data")
    if not isinstance(provider_data, dict):
        return ()
    items = provider_data.get("items")
    if not isinstance(items, list):
        return ()
    return tuple(
        item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("av"), dict)
    )


def _search_next_cursor(body: dict[str, Any]) -> str:
    outer_data = body.get("data")
    if not isinstance(outer_data, dict):
        raise ValueError("B站搜索响应缺少 data")
    provider_data = outer_data.get("data")
    if not isinstance(provider_data, dict):
        raise ValueError("B站搜索响应缺少 data.data")
    pagination = provider_data.get("pagination")
    if pagination is None:
        return ""
    if not isinstance(pagination, dict):
        raise ValueError("B站搜索响应 data.data.pagination 类型错误")
    return _string(pagination.get("next"))


def _video_identity_params(
    *,
    av_id: str | None,
    bv_id: str | None,
) -> dict[str, object]:
    normalized_av = _optional_id(av_id)
    normalized_bv = _optional_id(bv_id)
    if (normalized_av is None) == (normalized_bv is None):
        raise ValueError("av_id 与 bv_id 必须二选一")
    if normalized_av is not None:
        return {"av_id": normalized_av}
    assert normalized_bv is not None
    return {"bv_id": normalized_bv}


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


def _optional_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _non_negative_int(value: int, field_name: str) -> int:
    if value < 0:
        raise ValueError(f"{field_name} 不能小于 0")
    return value


def _string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "BilibiliCursorPagination",
    "BilibiliRequest",
    "BilibiliSearchPagination",
    "build_reply_detail_request",
    "build_search_request",
    "build_video_comments_request",
    "build_video_detail_request",
    "extract_search_items",
]
