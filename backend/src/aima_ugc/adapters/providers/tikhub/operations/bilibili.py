"""TikHub B站 App Operation 与保守分页状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_SEARCH_PATH = "/api/v1/bilibili/app/fetch_search_by_type"
_DETAIL_PATH = "/api/v1/bilibili/app/fetch_one_video"
_COMMENTS_PATH = "/api/v1/bilibili/app/fetch_video_comments"
_REPLY_PATH = "/api/v1/bilibili/app/fetch_reply_detail"

_SEARCH_ORDERS = {
    "general": "totalrank",
    "latest": "pubdate",
    "play_count": "click",
    "danmaku_count": "dm",
}


@dataclass(frozen=True, slots=True)
class BilibiliRequest:
    """一次 B站 TikHub Operation 的脱敏请求描述。"""

    method: Literal["GET"]
    path: str
    params: dict[str, object]
    body: None = None


@dataclass(frozen=True, slots=True)
class BilibiliSearchPagination:
    """搜索 page 状态；结果数组位置由后续真实 Fixture 提供 observation。"""

    next_page: int
    should_continue: bool
    stop_reason: str | None = None

    @classmethod
    def from_page_observation(
        cls,
        *,
        current_page: int,
        has_results: bool,
    ) -> BilibiliSearchPagination:
        if current_page < 1:
            raise ValueError("current_page 必须从 1 开始")
        if not has_results:
            return cls(current_page, False, "empty_page")
        return cls(current_page + 1, True)


@dataclass(frozen=True, slots=True)
class BilibiliCursorPagination:
    """只处理已由可靠响应解析得到的数字游标，不猜 JSON path。"""

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
        if returned_cursor is None:
            return cls(previous_cursor, False, "cursor_unavailable")
        if returned_cursor <= previous_cursor:
            return cls(returned_cursor, False, "pagination_not_advanced")
        return cls(returned_cursor, True)


def build_search_request(
    *,
    keyword: str,
    sort_mode: str = "general",
    page: int = 1,
    search_type: str = "video",
) -> BilibiliRequest:
    """构造 B站分类搜索；当前机器能力先固定视频类，避免超报未验证分类。"""
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须从 1 开始")
    if search_type != "video":
        raise ValueError("当前 B站 Operation 只验证 search_type=video")
    try:
        order = _SEARCH_ORDERS[sort_mode]
    except KeyError as exc:
        allowed = ", ".join(_SEARCH_ORDERS)
        raise ValueError(f"sort_mode 不支持: {sort_mode}; 可选: {allowed}") from exc
    return BilibiliRequest(
        method="GET",
        path=_SEARCH_PATH,
        params={
            "keyword": normalized_keyword,
            "search_type": search_type,
            "order": order,
            "page": page,
        },
    )


def build_video_detail_request(*, bvid: str) -> BilibiliRequest:
    """构造 B站单视频详情请求。"""
    return BilibiliRequest(
        method="GET",
        path=_DETAIL_PATH,
        params={"bvid": _required_text(bvid, "bvid")},
    )


def build_video_comments_request(
    *,
    oid: str,
    pagination_str: str | None = None,
) -> BilibiliRequest:
    """构造一级评论请求；分页串由 Operation 内部透传，不解析业务字段。"""
    params: dict[str, object] = {"oid": _required_text(oid, "oid")}
    if pagination_str is not None:
        normalized = pagination_str.strip()
        if not normalized:
            raise ValueError("pagination_str 不能为空字符串")
        params["pagination_str"] = normalized
    return BilibiliRequest(method="GET", path=_COMMENTS_PATH, params=params)


def build_reply_detail_request(
    *,
    oid: str,
    root: str,
    next_offset: int = 0,
) -> BilibiliRequest:
    """构造根评论回复详情请求；返回 next 的提取留给真实 Fixture 证明。"""
    if next_offset < 0:
        raise ValueError("next_offset 不能为负数")
    return BilibiliRequest(
        method="GET",
        path=_REPLY_PATH,
        params={
            "oid": _required_text(oid, "oid"),
            "root": _required_text(root, "root"),
            "next": next_offset,
        },
    )


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


__all__ = [
    "BilibiliCursorPagination",
    "BilibiliRequest",
    "BilibiliSearchPagination",
    "build_reply_detail_request",
    "build_search_request",
    "build_video_comments_request",
    "build_video_detail_request",
]
