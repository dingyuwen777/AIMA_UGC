"""TikHub 快手 App 主 Operation、Web 已验证备用 Operation 与 pcursor 状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_SEARCH_PATH = "/api/v1/kuaishou/app/search_video_v2"
_DETAIL_PATH = "/api/v1/kuaishou/app/fetch_one_video"
_APP_COMMENTS_PATH = "/api/v1/kuaishou/app/fetch_video_comment"
_APP_SUB_COMMENTS_PATH = "/api/v1/kuaishou/app/fetch_video_sub_comments"
_WEB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_comment"
_WEB_SUB_COMMENTS_PATH = "/api/v1/kuaishou/web/fetch_one_video_sub_comment"


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
        if next_cursor == previous_cursor:
            return cls(next_cursor, False, "pagination_not_advanced")
        return cls(next_cursor, True)


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


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


__all__ = [
    "KuaishouCursorPagination",
    "KuaishouRequest",
    "KuaishouSearchPagination",
    "build_app_video_comments_request",
    "build_app_video_sub_comments_request",
    "build_search_request",
    "build_video_comments_request",
    "build_video_detail_request",
    "build_video_sub_comments_request",
    "build_web_video_comments_request",
    "build_web_video_sub_comments_request",
    "extract_comment_items",
    "extract_detail_item",
    "extract_search_items",
    "extract_sub_comment_items",
]
