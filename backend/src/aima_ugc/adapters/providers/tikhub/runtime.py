"""TikHub 五平台真实 Operation/分页/Mapper 的统一 Runtime Adapter。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import SecretStr

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.modules.collection.providers.transport import ProviderTransportRequest

from .mappers import bilibili as bilibili_mapper
from .mappers import douyin as douyin_mapper
from .mappers import kuaishou as kuaishou_mapper
from .mappers import weibo as weibo_mapper
from .mappers import xiaohongshu as xhs_mapper
from .mappers.common import TikHubMappingContext
from .operations import bilibili, douyin, kuaishou, weibo, xiaohongshu

TikHubPlatform = Literal["xhs", "douyin", "weibo", "bilibili", "kuaishou"]


@dataclass(frozen=True, slots=True)
class TikHubOperationCall:
    """一个不含 Secret 的生产 TikHub Operation 调用事实。"""

    platform: TikHubPlatform
    business_operation: Literal["keyword_search", "content_detail", "comments", "sub_comments"]
    operation: str
    method: Literal["GET", "POST"]
    path: str
    params: dict[str, object]
    body: dict[str, object] | None = None
    pagination_input: dict[str, object] | None = None

    def transport_request(self, credential: SecretStr) -> ProviderTransportRequest:
        return ProviderTransportRequest(
            transport_kind="http",
            method=self.method,
            path=self.path,
            params=dict(self.params),
            body=self.body,
            credential=credential,
        )


@dataclass(frozen=True, slots=True)
class TikHubPageAdvance:
    """Provider-private 分页状态只停留在 Adapter 内。"""

    next_state: dict[str, object] | None
    stop_reason: str | None

    @property
    def should_continue(self) -> bool:
        return self.next_state is not None


def build_search_call(
    *,
    platform: TikHubPlatform,
    keyword: str,
    config: dict[str, object] | None = None,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """把 Plan 规范化搜索策略映射到真实 TikHub Search Operation。"""
    cfg = config or {}
    paging = state or {}
    if platform == "xhs":
        request = xiaohongshu.build_search_notes_request(
            keyword=keyword,
            page=_int_state(paging, "page", default=1),
            sort_type=_str_config(cfg, "sort_mode", default="general"),
            time_filter=_str_config(cfg, "published_within", default="all"),
            note_type=_str_config(cfg, "content_type", default="all"),
            search_id=_optional_str_state(paging, "search_id"),
            search_session_id=_optional_str_state(paging, "search_session_id"),
        )
        return TikHubOperationCall(
            platform=platform,
            business_operation="keyword_search",
            operation="search_notes",
            method="GET",
            path=request.path,
            params=request.params,
            pagination_input=dict(paging),
        )
    if platform == "douyin":
        request = douyin.build_video_search_request(
            keyword=keyword,
            cursor=_int_state(paging, "cursor", default=0),
            sort_mode=_str_config(cfg, "sort_mode", default="general"),
            published_within=_str_config(cfg, "published_within", default="all"),
            duration=_str_config(cfg, "duration", default="all"),
            content_type=_str_config(cfg, "content_type", default="all"),
            search_id=_str_state(paging, "search_id", default=""),
            backtrace=_str_state(paging, "backtrace", default=""),
        )
        return TikHubOperationCall(
            platform=platform,
            business_operation="keyword_search",
            operation="fetch_video_search_v2",
            method=request.method,
            path=request.path,
            params=request.params,
            body=request.body,
            pagination_input=dict(paging),
        )
    if platform == "weibo":
        request = weibo.build_search_request(
            keyword=keyword,
            page=_int_state(paging, "page", default=1),
            search_mode=_str_config(cfg, "sort_mode", default="latest"),
            time_scope=_str_config(cfg, "published_within", default="all"),
        )
        return TikHubOperationCall(
            platform=platform,
            business_operation="keyword_search",
            operation="fetch_search",
            method=request.method,
            path=request.path,
            params=request.params,
            pagination_input=dict(paging),
        )
    if platform == "bilibili":
        request = bilibili.build_search_request(
            keyword=keyword,
            cursor=_optional_str_state(paging, "cursor"),
            sort_mode=_str_config(cfg, "sort_mode", default="general"),
            search_type=_str_config(cfg, "content_type", default="video"),
        )
        return TikHubOperationCall(
            platform=platform,
            business_operation="keyword_search",
            operation="fetch_search_by_type",
            method=request.method,
            path=request.path,
            params=request.params,
            pagination_input=dict(paging),
        )
    request = kuaishou.build_search_request(
        keyword=keyword,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        platform=platform,
        business_operation="keyword_search",
        operation="search_video_v2",
        method=request.method,
        path=request.path,
        params=request.params,
        pagination_input=dict(paging),
    )


def advance_search(
    *,
    platform: TikHubPlatform,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    current = state or {}
    if platform == "xhs":
        page = _int_state(current, "page", default=1)
        previous_ids = tuple(_string_list(current.get("item_ids")))
        result = xiaohongshu.XhsSearchPagination.from_response(
            current_page=page,
            body=body,
            previous_item_ids=previous_ids,
        )
        if not result.should_continue:
            return TikHubPageAdvance(None, result.stop_reason)
        return TikHubPageAdvance(
            {
                "page": result.next_page,
                "search_id": result.search_id or "",
                "search_session_id": result.search_session_id or "",
                "item_ids": list(result.item_ids),
            },
            None,
        )
    if platform == "douyin":
        cursor = _int_state(current, "cursor", default=0)
        previous_ids = tuple(_string_list(current.get("item_ids")))
        result = douyin.DouyinSearchPagination.from_response(
            current_cursor=cursor,
            body=body,
            previous_item_ids=previous_ids,
        )
        if not result.should_continue:
            return TikHubPageAdvance(None, result.stop_reason)
        return TikHubPageAdvance(
            {
                "cursor": result.next_cursor,
                "search_id": result.search_id,
                "backtrace": result.backtrace,
                "item_ids": list(result.item_ids),
            },
            None,
        )
    if platform == "weibo":
        page = _int_state(current, "page", default=1)
        result = weibo.WeiboSearchPagination.from_page_observation(
            current_page=page,
            has_results=bool(weibo.extract_search_items(body)),
        )
        if not result.should_continue:
            return TikHubPageAdvance(None, result.stop_reason)
        return TikHubPageAdvance({"page": result.next_page}, None)
    if platform == "bilibili":
        previous = _optional_str_state(current, "cursor")
        result = bilibili.BilibiliSearchPagination.from_response(
            previous_cursor=previous,
            body=body,
        )
        if not result.should_continue:
            return TikHubPageAdvance(None, result.stop_reason)
        return TikHubPageAdvance({"cursor": result.next_cursor}, None)
    previous = _str_state(current, "pcursor", default="")
    result = kuaishou.KuaishouSearchPagination.from_response(
        previous_cursor=previous,
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance({"pcursor": result.next_cursor}, None)


def extract_search_items(
    platform: TikHubPlatform, body: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    if platform == "xhs":
        return xiaohongshu.extract_search_items(body)
    if platform == "douyin":
        return douyin.extract_search_items(body)
    if platform == "weibo":
        return weibo.extract_search_items(body)
    if platform == "bilibili":
        return bilibili.extract_search_items(body)
    return kuaishou.extract_search_items(body)


def build_detail_call(platform: TikHubPlatform, content: CanonicalContentV1) -> TikHubOperationCall:
    external_id = content.external_content_id
    if platform == "xhs":
        request = (
            xiaohongshu.build_video_detail_request(note_id=external_id)
            if content.content_type == "video"
            else xiaohongshu.build_image_detail_request(note_id=external_id)
        )
        operation = "get_video_note_detail" if content.content_type == "video" else "get_image_note_detail"
        return TikHubOperationCall(platform, "content_detail", operation, "GET", request.path, request.params)
    if platform == "douyin":
        request = douyin.build_video_detail_request(aweme_id=external_id)
        return TikHubOperationCall(
            platform,
            "content_detail",
            "fetch_one_video_v3",
            request.method,
            request.path,
            request.params,
        )
    if platform == "weibo":
        request = weibo.build_status_detail_request(status_id=external_id)
        return TikHubOperationCall(
            platform,
            "content_detail",
            "fetch_status_detail",
            request.method,
            request.path,
            request.params,
        )
    if platform == "bilibili":
        request = bilibili.build_video_detail_request(av_id=external_id)
        return TikHubOperationCall(
            platform,
            "content_detail",
            "fetch_one_video",
            request.method,
            request.path,
            request.params,
        )
    request = kuaishou.build_video_detail_request(photo_id=external_id)
    return TikHubOperationCall(
        platform,
        "content_detail",
        "fetch_one_video",
        request.method,
        request.path,
        request.params,
    )


def build_comments_call(
    *, platform: TikHubPlatform, external_content_id: str, state: dict[str, object] | None = None
) -> TikHubOperationCall:
    paging = state or {}
    if platform == "xhs":
        request = xiaohongshu.build_note_comments_request(
            note_id=external_content_id,
            cursor=_str_state(paging, "cursor", default=""),
            index=_int_state(paging, "index", default=0),
            page_area=_str_state(paging, "page_area", default="UNFOLDED"),
        )
        return TikHubOperationCall(
            platform, "comments", "get_note_comments", "GET", request.path, request.params, pagination_input=dict(paging)
        )
    if platform == "douyin":
        request = douyin.build_video_comments_request(
            aweme_id=external_content_id,
            cursor=_int_state(paging, "cursor", default=0),
        )
        return TikHubOperationCall(
            platform,
            "comments",
            "fetch_video_comments",
            request.method,
            request.path,
            request.params,
            pagination_input=dict(paging),
        )
    if platform == "weibo":
        request = weibo.build_status_comments_request(
            status_id=external_content_id,
            max_id=_optional_str_state(paging, "max_id"),
            sort_mode="latest",
        )
        return TikHubOperationCall(
            platform,
            "comments",
            "fetch_status_comments",
            request.method,
            request.path,
            request.params,
            pagination_input=dict(paging),
        )
    if platform == "bilibili":
        request = bilibili.build_video_comments_request(
            av_id=external_content_id,
            sort_mode="latest",
            next_offset=_optional_int_state(paging, "next_offset"),
        )
        return TikHubOperationCall(
            platform,
            "comments",
            "fetch_video_comments",
            request.method,
            request.path,
            request.params,
            pagination_input=dict(paging),
        )
    request = kuaishou.build_video_comments_request(
        photo_id=external_content_id,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        platform,
        "comments",
        "fetch_one_video_comment",
        request.method,
        request.path,
        request.params,
        pagination_input=dict(paging),
    )


def extract_detail_items(platform: TikHubPlatform, body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if platform == "xhs":
        return xiaohongshu.extract_detail_items(body)
    if platform == "douyin":
        return (douyin.extract_detail_item(body),)
    if platform == "weibo":
        return (weibo.extract_detail_item(body),)
    if platform == "bilibili":
        return (bilibili.extract_detail_item(body),)
    return (kuaishou.extract_detail_item(body),)


def extract_comment_items(platform: TikHubPlatform, body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if platform == "xhs":
        return xiaohongshu.extract_comment_items(body)
    if platform == "douyin":
        return douyin.extract_comment_items(body)
    if platform == "weibo":
        return weibo.extract_comment_items(body)
    if platform == "bilibili":
        return bilibili.extract_comment_items(body)
    return kuaishou.extract_comment_items(body)


def map_content(
    *,
    platform: TikHubPlatform,
    raw: dict[str, Any],
    context: TikHubMappingContext,
    item_locator: str,
) -> CanonicalContentV1:
    if platform == "xhs":
        return xhs_mapper.map_content(raw, _xhs_context(context), item_locator=item_locator)
    if platform == "douyin":
        return douyin_mapper.map_content(raw, context, item_locator=item_locator)
    if platform == "weibo":
        return weibo_mapper.map_content(raw, context, item_locator=item_locator)
    if platform == "bilibili":
        return bilibili_mapper.map_content(raw, context, item_locator=item_locator)
    return kuaishou_mapper.map_content(raw, context, item_locator=item_locator)


def map_comment(
    *,
    platform: TikHubPlatform,
    raw: dict[str, Any],
    context: TikHubMappingContext,
    item_locator: str,
    is_root: bool,
) -> CanonicalCommentV1:
    if platform == "xhs":
        return xhs_mapper.map_comment(raw, _xhs_context(context), item_locator=item_locator, is_root=is_root)
    if platform == "douyin":
        return douyin_mapper.map_comment(raw, context, item_locator=item_locator, is_root=is_root)
    if platform == "weibo":
        return weibo_mapper.map_comment(raw, context, item_locator=item_locator, is_root=is_root)
    if platform == "bilibili":
        return bilibili_mapper.map_comment(raw, context, item_locator=item_locator, is_root=is_root)
    return kuaishou_mapper.map_comment(raw, context, item_locator=item_locator, is_root=is_root)


def mapping_context(
    *,
    provider_request_id: str,
    provider_attempt_id: str,
    raw_artifact_id: UUID,
    operation: str,
    source_type: str,
    source_value: str,
    observed_at: datetime,
    external_content_id: str | None = None,
    root_comment_id: str | None = None,
) -> TikHubMappingContext:
    return TikHubMappingContext(
        provider_request_id=provider_request_id,
        provider_attempt_id=provider_attempt_id,
        raw_artifact_id=raw_artifact_id,
        operation=operation,
        source_type=source_type,
        source_value=source_value,
        observed_at=observed_at,
        external_content_id=external_content_id,
        root_comment_id=root_comment_id,
    )


def _xhs_context(context: TikHubMappingContext) -> xhs_mapper.XhsMappingContext:
    return xhs_mapper.XhsMappingContext(
        provider_request_id=context.provider_request_id,
        provider_attempt_id=context.provider_attempt_id,
        raw_artifact_id=context.raw_artifact_id,
        operation=context.operation,
        source_type=context.source_type,
        source_value=context.source_value,
        observed_at=context.observed_at,
        root_comment_id=context.root_comment_id,
    )


def _str_config(config: dict[str, object], key: str, *, default: str) -> str:
    value = config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"TikHub Plan config {key} 必须为非空字符串")
    return value.strip()


def _int_state(state: dict[str, object], key: str, *, default: int) -> int:
    value = state.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"TikHub pagination {key} 必须为整数")
    return value


def _optional_int_state(state: dict[str, object], key: str) -> int | None:
    if key not in state or state[key] is None:
        return None
    return _int_state(state, key, default=0)


def _str_state(state: dict[str, object], key: str, *, default: str) -> str:
    value = state.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"TikHub pagination {key} 必须为字符串")
    return value


def _optional_str_state(state: dict[str, object], key: str) -> str | None:
    if key not in state or state[key] in {None, ""}:
        return None
    return _str_state(state, key, default="")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


__all__ = [
    "TikHubOperationCall",
    "TikHubPageAdvance",
    "TikHubPlatform",
    "advance_search",
    "build_comments_call",
    "build_detail_call",
    "build_search_call",
    "extract_comment_items",
    "extract_detail_items",
    "extract_search_items",
    "map_comment",
    "map_content",
    "mapping_context",
]
