"""TikHub 五平台真实 Operation/分页/Mapper 的统一 Runtime Adapter。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import SecretStr, TypeAdapter

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.provider import JsonObject
from aima_ugc.modules.collection.providers.transport import ProviderTransportRequest

from .mappers import bilibili as bilibili_mapper
from .mappers import douyin as douyin_mapper
from .mappers import kuaishou as kuaishou_mapper
from .mappers import weibo as weibo_mapper
from .mappers import xiaohongshu as xhs_mapper
from .mappers.common import TikHubMappingContext
from .operations import bilibili, douyin, kuaishou, weibo, xiaohongshu

TikHubPlatform = Literal["xhs", "douyin", "weibo", "bilibili", "kuaishou"]
TikHubBusinessOperation = Literal["keyword_search", "content_detail", "comments", "sub_comments"]
_JSON_OBJECT_ADAPTER = TypeAdapter(JsonObject)


@dataclass(frozen=True, slots=True)
class TikHubOperationCall:
    """一个不含 Secret 的生产 TikHub Operation 调用事实。"""

    platform: TikHubPlatform
    business_operation: TikHubBusinessOperation
    operation: str
    method: Literal["GET", "POST"]
    path: str
    params: JsonObject
    body: JsonObject | None = None
    pagination_input: JsonObject | None = None

    def transport_request(self, credential: SecretStr) -> ProviderTransportRequest:
        return ProviderTransportRequest(
            transport_kind="http",
            method=self.method,
            path=self.path,
            params=self.params,
            body=self.body,
            credential=credential,
        )


@dataclass(frozen=True, slots=True)
class TikHubPageAdvance:
    """Provider-private 分页状态只停留在 Adapter 内。"""

    next_state: JsonObject | None
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
        return _build_xhs_search(keyword=keyword, config=cfg, state=paging)
    if platform == "douyin":
        return _build_douyin_search(keyword=keyword, config=cfg, state=paging)
    if platform == "weibo":
        return _build_weibo_search(keyword=keyword, config=cfg, state=paging)
    if platform == "bilibili":
        return _build_bilibili_search(keyword=keyword, config=cfg, state=paging)
    return _build_kuaishou_search(keyword=keyword, state=paging)


def _build_xhs_search(
    *, keyword: str, config: dict[str, object], state: dict[str, object]
) -> TikHubOperationCall:
    request = xiaohongshu.build_search_notes_request(
        keyword=keyword,
        page=_int_state(state, "page", default=1),
        sort_type=_str_config(config, "sort_mode", default="general"),
        time_filter=_str_config(config, "published_within", default="all"),
        note_type=_str_config(config, "content_type", default="all"),
        search_id=_optional_str_state(state, "search_id"),
        search_session_id=_optional_str_state(state, "search_session_id"),
    )
    return TikHubOperationCall(
        platform="xhs",
        business_operation="keyword_search",
        operation="search_notes",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(state),
    )


def _build_douyin_search(
    *, keyword: str, config: dict[str, object], state: dict[str, object]
) -> TikHubOperationCall:
    request = douyin.build_video_search_request(
        keyword=keyword,
        cursor=_int_state(state, "cursor", default=0),
        sort_mode=_str_config(config, "sort_mode", default="general"),
        published_within=_str_config(config, "published_within", default="all"),
        duration=_str_config(config, "duration", default="all"),
        content_type=_str_config(config, "content_type", default="all"),
        search_id=_str_state(state, "search_id", default=""),
        backtrace=_str_state(state, "backtrace", default=""),
    )
    return TikHubOperationCall(
        platform="douyin",
        business_operation="keyword_search",
        operation="fetch_video_search_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        body=_optional_json_object(request.body),
        pagination_input=_json_object(state),
    )


def _build_weibo_search(
    *, keyword: str, config: dict[str, object], state: dict[str, object]
) -> TikHubOperationCall:
    request = weibo.build_search_request(
        keyword=keyword,
        page=_int_state(state, "page", default=1),
        search_mode=_str_config(config, "sort_mode", default="latest"),
        time_scope=_str_config(config, "published_within", default="all"),
    )
    return TikHubOperationCall(
        platform="weibo",
        business_operation="keyword_search",
        operation="fetch_search",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(state),
    )


def _build_bilibili_search(
    *, keyword: str, config: dict[str, object], state: dict[str, object]
) -> TikHubOperationCall:
    request = bilibili.build_search_request(
        keyword=keyword,
        cursor=_optional_str_state(state, "cursor"),
        sort_mode=_str_config(config, "sort_mode", default="general"),
        search_type=_str_config(config, "content_type", default="video"),
    )
    return TikHubOperationCall(
        platform="bilibili",
        business_operation="keyword_search",
        operation="fetch_search_by_type",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(state),
    )


def _build_kuaishou_search(*, keyword: str, state: dict[str, object]) -> TikHubOperationCall:
    request = kuaishou.build_search_request(
        keyword=keyword,
        pcursor=_str_state(state, "pcursor", default=""),
    )
    return TikHubOperationCall(
        platform="kuaishou",
        business_operation="keyword_search",
        operation="search_video_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(state),
    )


def advance_search(
    *,
    platform: TikHubPlatform,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    current = state or {}
    if platform == "xhs":
        return _advance_xhs_search(current, body)
    if platform == "douyin":
        return _advance_douyin_search(current, body)
    if platform == "weibo":
        return _advance_weibo_search(current, body)
    if platform == "bilibili":
        return _advance_bilibili_search(current, body)
    return _advance_kuaishou_search(current, body)


def _advance_xhs_search(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = xiaohongshu.XhsSearchPagination.from_response(
        current_page=_int_state(state, "page", default=1),
        body=body,
        previous_item_ids=tuple(_string_list(state.get("item_ids"))),
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(
        _json_object(
            {
                "page": result.next_page,
                "search_id": result.search_id or "",
                "search_session_id": result.search_session_id or "",
                "item_ids": list(result.item_ids),
            }
        ),
        None,
    )


def _advance_douyin_search(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = douyin.DouyinSearchPagination.from_response(
        current_cursor=_int_state(state, "cursor", default=0),
        body=body,
        previous_item_ids=tuple(_string_list(state.get("item_ids"))),
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(
        _json_object(
            {
                "cursor": result.next_cursor,
                "search_id": result.search_id,
                "backtrace": result.backtrace,
                "item_ids": list(result.item_ids),
            }
        ),
        None,
    )


def _advance_weibo_search(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = weibo.WeiboSearchPagination.from_page_observation(
        current_page=_int_state(state, "page", default=1),
        has_results=bool(weibo.extract_search_items(body)),
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"page": result.next_page}), None)


def _advance_bilibili_search(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = bilibili.BilibiliSearchPagination.from_response(
        previous_cursor=_optional_str_state(state, "cursor"),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"cursor": result.next_cursor}), None)


def _advance_kuaishou_search(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = kuaishou.KuaishouSearchPagination.from_response(
        previous_cursor=_str_state(state, "pcursor", default=""),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"pcursor": result.next_cursor}), None)


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
    if platform == "xhs":
        if content.content_type == "video":
            xhs_request = xiaohongshu.build_video_detail_request(
                note_id=content.external_content_id
            )
            operation = "get_video_note_detail"
        else:
            xhs_request = xiaohongshu.build_image_detail_request(
                note_id=content.external_content_id
            )
            operation = "get_image_note_detail"
        return TikHubOperationCall(
            "xhs",
            "content_detail",
            operation,
            "GET",
            xhs_request.path,
            _json_object(xhs_request.params),
        )
    if platform == "douyin":
        douyin_request = douyin.build_video_detail_request(aweme_id=content.external_content_id)
        return TikHubOperationCall(
            "douyin",
            "content_detail",
            "fetch_one_video_v3",
            douyin_request.method,
            douyin_request.path,
            _json_object(douyin_request.params),
        )
    if platform == "weibo":
        weibo_request = weibo.build_status_detail_request(status_id=content.external_content_id)
        return TikHubOperationCall(
            "weibo",
            "content_detail",
            "fetch_status_detail",
            weibo_request.method,
            weibo_request.path,
            _json_object(weibo_request.params),
        )
    if platform == "bilibili":
        bilibili_request = bilibili.build_video_detail_request(av_id=content.external_content_id)
        return TikHubOperationCall(
            "bilibili",
            "content_detail",
            "fetch_one_video",
            bilibili_request.method,
            bilibili_request.path,
            _json_object(bilibili_request.params),
        )
    kuaishou_request = kuaishou.build_video_detail_request(photo_id=content.external_content_id)
    return TikHubOperationCall(
        "kuaishou",
        "content_detail",
        "fetch_one_video",
        kuaishou_request.method,
        kuaishou_request.path,
        _json_object(kuaishou_request.params),
    )


def build_comments_call(
    *, platform: TikHubPlatform, external_content_id: str, state: dict[str, object] | None = None
) -> TikHubOperationCall:
    paging = state or {}
    if platform == "xhs":
        xhs_request = xiaohongshu.build_note_comments_request(
            note_id=external_content_id,
            cursor=_str_state(paging, "cursor", default=""),
            index=_int_state(paging, "index", default=0),
            page_area=_str_state(paging, "page_area", default="UNFOLDED"),
        )
        return TikHubOperationCall(
            "xhs",
            "comments",
            "get_note_comments",
            "GET",
            xhs_request.path,
            _json_object(xhs_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "douyin":
        douyin_request = douyin.build_video_comments_request(
            aweme_id=external_content_id,
            cursor=_int_state(paging, "cursor", default=0),
        )
        return TikHubOperationCall(
            "douyin",
            "comments",
            "fetch_video_comments",
            douyin_request.method,
            douyin_request.path,
            _json_object(douyin_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "weibo":
        weibo_request = weibo.build_status_comments_request(
            status_id=external_content_id,
            max_id=_optional_str_state(paging, "max_id"),
            sort_mode="latest",
        )
        return TikHubOperationCall(
            "weibo",
            "comments",
            "fetch_status_comments",
            weibo_request.method,
            weibo_request.path,
            _json_object(weibo_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "bilibili":
        bilibili_request = bilibili.build_video_comments_request(
            av_id=external_content_id,
            sort_mode="latest",
            next_offset=_optional_int_state(paging, "next_offset"),
        )
        return TikHubOperationCall(
            "bilibili",
            "comments",
            "fetch_video_comments",
            bilibili_request.method,
            bilibili_request.path,
            _json_object(bilibili_request.params),
            pagination_input=_json_object(paging),
        )
    kuaishou_request = kuaishou.build_video_comments_request(
        photo_id=external_content_id,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        "kuaishou",
        "comments",
        "fetch_video_comment",
        kuaishou_request.method,
        kuaishou_request.path,
        _json_object(kuaishou_request.params),
        pagination_input=_json_object(paging),
    )


def build_sub_comments_call(
    *,
    platform: TikHubPlatform,
    external_content_id: str,
    root_comment_id: str,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造当前正式二级回复主 Operation；不做任何 App/Web 自动 fallback。"""
    paging = state or {}
    if platform == "xhs":
        xhs_request = xiaohongshu.build_sub_comments_request(
            note_id=external_content_id,
            comment_id=root_comment_id,
            cursor=_str_state(paging, "cursor", default=""),
            index=_int_state(paging, "index", default=1),
        )
        return TikHubOperationCall(
            "xhs",
            "sub_comments",
            "get_note_sub_comments",
            "GET",
            xhs_request.path,
            _json_object(xhs_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "douyin":
        douyin_request = douyin.build_video_comment_replies_request(
            item_id=external_content_id,
            comment_id=root_comment_id,
            cursor=_int_state(paging, "cursor", default=0),
        )
        return TikHubOperationCall(
            "douyin",
            "sub_comments",
            "fetch_video_comment_replies",
            douyin_request.method,
            douyin_request.path,
            _json_object(douyin_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "weibo":
        weibo_request = weibo.build_status_sub_comments_request(
            root_comment_id=root_comment_id,
            max_id=_str_state(paging, "max_id", default=""),
        )
        return TikHubOperationCall(
            "weibo",
            "sub_comments",
            "fetch_post_sub_comments",
            weibo_request.method,
            weibo_request.path,
            _json_object(weibo_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "bilibili":
        bilibili_request = bilibili.build_reply_detail_request(
            root=root_comment_id,
            av_id=external_content_id,
            next_offset=_optional_int_state(paging, "next_offset"),
        )
        return TikHubOperationCall(
            "bilibili",
            "sub_comments",
            "fetch_reply_detail",
            bilibili_request.method,
            bilibili_request.path,
            _json_object(bilibili_request.params),
            pagination_input=_json_object(paging),
        )
    kuaishou_request = kuaishou.build_video_sub_comments_request(
        photo_id=external_content_id,
        root_comment_id=root_comment_id,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        "kuaishou",
        "sub_comments",
        "fetch_video_sub_comments",
        kuaishou_request.method,
        kuaishou_request.path,
        _json_object(kuaishou_request.params),
        pagination_input=_json_object(paging),
    )


def advance_comments(
    *,
    platform: TikHubPlatform,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """按现有正式一级评论分页事实推进下一页。"""
    current = state or {}
    if platform == "xhs":
        return _advance_xhs_comments(current, body, default_index=0)
    if platform == "douyin":
        return _advance_douyin_comments(current, body)
    if platform == "weibo":
        return _advance_weibo_comments(current, body)
    if platform == "bilibili":
        return _advance_bilibili_comments(current, body)
    return _advance_kuaishou_comments(current, body, item_key="rootComments")


def advance_sub_comments(
    *,
    platform: TikHubPlatform,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """按现有正式二级回复分页事实推进下一页。"""
    current = state or {}
    if platform == "xhs":
        return _advance_xhs_comments(current, body, default_index=1)
    if platform == "douyin":
        return _advance_douyin_comments(current, body)
    if platform == "weibo":
        return _advance_weibo_sub_comments(current, body)
    if platform == "bilibili":
        return _advance_bilibili_comments(current, body)
    return _advance_kuaishou_comments(current, body, item_key="subComments")


def _advance_xhs_comments(
    state: dict[str, object],
    body: dict[str, Any],
    *,
    default_index: int,
) -> TikHubPageAdvance:
    page_area = _str_state(state, "page_area", default="UNFOLDED")
    result = xiaohongshu.XhsCommentPagination.from_response(
        previous_cursor=_str_state(state, "cursor", default=""),
        previous_index=_int_state(state, "index", default=default_index),
        page_area=page_area,
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(
        _json_object(
            {
                "cursor": result.cursor,
                "index": result.index,
                "page_area": result.page_area,
            }
        ),
        None,
    )


def _advance_douyin_comments(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = douyin.DouyinCursorPagination.from_response(
        previous_cursor=_int_state(state, "cursor", default=0),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"cursor": result.next_cursor}), None)


def _advance_weibo_comments(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    result = weibo.WeiboCommentPagination.from_response(
        previous_max_id=_optional_str_state(state, "max_id"),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"max_id": result.next_max_id}), None)


def _advance_weibo_sub_comments(
    state: dict[str, object], body: dict[str, Any]
) -> TikHubPageAdvance:
    outer = body.get("data")
    if not isinstance(outer, dict):
        return TikHubPageAdvance(None, "response_data_unavailable")
    returned = outer.get("max_id")
    if returned is None or returned in {0, "0", ""}:
        return TikHubPageAdvance(None, "provider_exhausted")
    result = weibo.WeiboSubCommentPagination.from_returned_max_id(
        previous_max_id=_str_state(state, "max_id", default=""),
        returned_max_id=str(returned),
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"max_id": result.next_max_id}), None)


def _advance_bilibili_comments(state: dict[str, object], body: dict[str, Any]) -> TikHubPageAdvance:
    provider = body.get("data")
    provider_data = provider.get("data") if isinstance(provider, dict) else None
    if not isinstance(provider_data, dict):
        return TikHubPageAdvance(None, "response_data_unavailable")
    cursor = provider_data.get("cursor")
    if not isinstance(cursor, dict):
        return TikHubPageAdvance(None, "cursor_unavailable")
    if cursor.get("is_end") is True:
        return TikHubPageAdvance(None, "provider_exhausted")
    pagination_reply = cursor.get("pagination_reply")
    returned = pagination_reply.get("next_offset") if isinstance(pagination_reply, dict) else None
    next_offset = _nonnegative_integer(returned)
    result = bilibili.BilibiliCursorPagination.from_returned_cursor(
        previous_cursor=_int_state(state, "next_offset", default=0),
        returned_cursor=next_offset,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"next_offset": result.next_cursor}), None)


def _advance_kuaishou_comments(
    state: dict[str, object],
    body: dict[str, Any],
    *,
    item_key: str,
) -> TikHubPageAdvance:
    result = kuaishou.KuaishouCursorPagination.from_response(
        previous_cursor=_str_state(state, "pcursor", default=""),
        body=body,
        item_key=item_key,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"pcursor": result.next_cursor}), None)


def extract_detail_items(
    platform: TikHubPlatform, body: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    if platform == "xhs":
        return xiaohongshu.extract_detail_items(body)
    if platform == "douyin":
        return (douyin.extract_detail_item(body),)
    if platform == "weibo":
        return (weibo.extract_detail_item(body),)
    if platform == "bilibili":
        return (bilibili.extract_detail_item(body),)
    return (kuaishou.extract_detail_item(body),)


def extract_comment_items(
    platform: TikHubPlatform, body: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    if platform == "xhs":
        return xiaohongshu.extract_comment_items(body)
    if platform == "douyin":
        return douyin.extract_comment_items(body)
    if platform == "weibo":
        return weibo.extract_comment_items(body)
    if platform == "bilibili":
        return bilibili.extract_comment_items(body)
    return kuaishou.extract_comment_items(body)


def extract_sub_comment_items(
    platform: TikHubPlatform, body: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    """按当前正式二级回复响应形态提取业务 item。"""
    if platform == "xhs":
        return xiaohongshu.extract_comment_items(body)
    if platform == "douyin":
        return douyin.extract_comment_items(body)
    if platform == "weibo":
        outer = body.get("data")
        items = outer.get("data") if isinstance(outer, dict) else None
        if not isinstance(items, list):
            return ()
        return tuple(item for item in items if isinstance(item, dict))
    if platform == "bilibili":
        _, replies = bilibili.extract_reply_detail(body)
        return replies
    return kuaishou.extract_sub_comment_items(body)


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
        return xhs_mapper.map_comment(
            raw,
            _xhs_context(context),
            item_locator=item_locator,
            is_root=is_root,
        )
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


def _json_object(value: dict[str, object]) -> JsonObject:
    return _JSON_OBJECT_ADAPTER.validate_python(value)


def _optional_json_object(value: dict[str, object] | None) -> JsonObject | None:
    return None if value is None else _json_object(value)


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


def _nonnegative_integer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


__all__ = [
    "TikHubOperationCall",
    "TikHubPageAdvance",
    "TikHubPlatform",
    "advance_comments",
    "advance_search",
    "advance_sub_comments",
    "build_comments_call",
    "build_detail_call",
    "build_search_call",
    "build_sub_comments_call",
    "extract_comment_items",
    "extract_detail_items",
    "extract_search_items",
    "extract_sub_comment_items",
    "map_comment",
    "map_content",
    "mapping_context",
]
