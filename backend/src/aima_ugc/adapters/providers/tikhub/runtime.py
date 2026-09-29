"""TikHub 五平台真实 Operation/分页/Mapper 的统一 Runtime Adapter。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import SecretStr, TypeAdapter

from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1
from aima_ugc.contracts.platform import PlatformName
from aima_ugc.contracts.provider import JsonObject
from aima_ugc.modules.collection.comment_target import (
    resolve_comment_target,
    resolve_supported_locator,
)
from aima_ugc.modules.collection.providers.transport import ProviderTransportRequest

from .mappers import bilibili as bilibili_mapper
from .mappers import douyin as douyin_mapper
from .mappers import kuaishou as kuaishou_mapper
from .mappers import weibo as weibo_mapper
from .mappers import xiaohongshu as xiaohongshu_mapper
from .mappers.common import TikHubMappingContext
from .operations import backup, bilibili, douyin, kuaishou, weibo, xiaohongshu

TikHubPlatform = PlatformName
TikHubBusinessOperation = Literal[
    "keyword_search",
    "content_detail",
    "identity_resolution",
    "comments",
    "sub_comments",
    "account_search",
    "account_info",
    "account_notes",
    "account_posts",
]
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
    # 某些 TikHub 抖音评论响应会错误地返回 has_more=0，但仍给出递增
    # cursor。账号“全量评论”模式可以在总数未对齐时使用它做恢复探测；
    # 普通调用方仍只看 next_state/should_continue，不会改变既有分页语义。
    resume_state: JsonObject | None = None

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
    if platform == "xiaohongshu":
        return _build_xiaohongshu_search(keyword=keyword, config=cfg, state=paging)
    if platform == "douyin":
        return _build_douyin_search(keyword=keyword, config=cfg, state=paging)
    if platform == "weibo":
        return _build_weibo_search(keyword=keyword, config=cfg, state=paging)
    if platform == "bilibili":
        return _build_bilibili_search(keyword=keyword, config=cfg, state=paging)
    return _build_kuaishou_search(keyword=keyword, state=paging)


def build_xiaohongshu_user_search_call(
    *,
    keyword: str,
    state: dict[str, object] | None = None,
    source: str = "search_result",
) -> TikHubOperationCall:
    """构造指定账号解析使用的小红书用户搜索调用。"""
    paging = state or {}
    request = xiaohongshu.build_search_users_request(
        keyword=keyword,
        page=_int_state(paging, "page", default=1),
        search_id=_optional_str_state(paging, "search_id"),
        source=source,
    )
    return TikHubOperationCall(
        platform="xiaohongshu",
        business_operation="account_search",
        operation="search_users",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_xiaohongshu_user_info_call(
    *,
    user_id: str | None = None,
    share_text: str | None = None,
) -> TikHubOperationCall:
    """构造指定账号身份校验使用的小红书用户信息调用。"""
    request = xiaohongshu.build_user_info_request(user_id=user_id, share_text=share_text)
    return TikHubOperationCall(
        platform="xiaohongshu",
        business_operation="account_info",
        operation="get_user_info",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
    )


def build_xiaohongshu_user_posted_notes_call(
    *,
    user_id: str,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造指定账号笔记发现使用的小红书用户发布笔记调用。"""
    paging = state or {}
    request = xiaohongshu.build_user_posted_notes_request(
        user_id=user_id,
        cursor=_str_state(paging, "cursor", default=""),
    )
    return TikHubOperationCall(
        platform="xiaohongshu",
        business_operation="account_notes",
        operation="get_user_posted_notes",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_douyin_user_posted_videos_call(
    *,
    account_value: str,
    state: dict[str, object] | None = None,
    config: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造抖音指定账号作品调用；账号接口细节由人工配置提供。"""

    cfg = config or {}
    paging = state or {}
    request = douyin.build_user_posted_videos_request(
        account_value=account_value,
        cursor=_int_state(paging, "cursor", default=0),
        path=_str_config(
            cfg,
            "account_posts_path",
            default="/api/v1/douyin/app/v3/fetch_user_post_videos",
        ),
        method=cast(
            Literal["GET", "POST"],
            _str_config(cfg, "account_posts_method", default="GET"),
        ),
        account_param=_str_config(cfg, "account_id_param", default="sec_user_id"),
        cursor_param=_str_config(cfg, "account_cursor_param", default="max_cursor"),
    )
    return TikHubOperationCall(
        platform="douyin",
        business_operation="account_posts",
        operation="fetch_user_post_videos",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        body=_optional_json_object(request.body),
        pagination_input=_json_object(paging),
    )


def build_douyin_douplus_user_posts_call(
    *,
    sec_uid: str,
    state: dict[str, object] | None = None,
    count: int = 10,
) -> TikHubOperationCall:
    """构造 App V3 作品接口失败后的 Dou+ 简洁作品补采调用。"""

    paging = state or {}
    request = backup.build_douyin_douplus_user_posts_backup_request(
        sec_uid=sec_uid,
        cursor=str(_int_state(paging, "cursor", default=0)),
        count=count,
    )
    return TikHubOperationCall(
        platform="douyin",
        business_operation="account_posts",
        operation="fetch_user_posts_douplus",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        body=_optional_json_object(request.body),
        pagination_input=_json_object(paging),
    )


def build_kuaishou_user_profile_call(*, user_reference: str) -> TikHubOperationCall:
    """构造快手 eid/userId → 用户资料的 V2 调用。"""
    request = kuaishou.build_user_profile_request(user_id=user_reference)
    return TikHubOperationCall(
        platform="kuaishou",
        business_operation="account_info",
        operation="fetch_one_user_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
    )


def build_kuaishou_user_search_call(
    *,
    keyword: str,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造快手号/昵称 → 用户候选的搜索 V2 调用。"""
    paging = state or {}
    request = kuaishou.build_user_search_request(
        keyword=keyword,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        platform="kuaishou",
        business_operation="account_search",
        operation="search_user_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_kuaishou_user_posts_call(
    *,
    user_id: str,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造快手指定账号按最新排序的作品 V2 调用。"""
    paging = state or {}
    request = kuaishou.build_user_posts_request(
        user_id=user_id,
        pcursor=_str_state(paging, "pcursor", default=""),
        sort="latest",
    )
    return TikHubOperationCall(
        platform="kuaishou",
        business_operation="account_posts",
        operation="fetch_user_post_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_weibo_user_search_call(
    *,
    query: str,
    state: dict[str, object] | None = None,
    nickname: str | None = None,
) -> TikHubOperationCall:
    """构造微博昵称 → UID 的 Web V2 用户搜索调用。"""

    paging = state or {}
    request = weibo.build_user_search_request(
        query=query,
        page=_int_state(paging, "page", default=1),
        nickname=nickname,
    )
    return TikHubOperationCall(
        platform="weibo",
        business_operation="account_search",
        operation="fetch_user_search",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_weibo_user_posts_call(
    *,
    uid: str,
    state: dict[str, object] | None = None,
    feature: int = 3,
) -> TikHubOperationCall:
    """构造微博指定账号历史微博调用，按官方 since_id 全分页。"""

    paging = state or {}
    request = weibo.build_user_posts_request(
        uid=uid,
        page=_int_state(paging, "page", default=1),
        since_id=_str_state(paging, "since_id", default=""),
        feature=feature,
    )
    return TikHubOperationCall(
        platform="weibo",
        business_operation="account_posts",
        operation="fetch_user_posts",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_bilibili_user_posts_call(
    *,
    uid: str,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造 B站用户投稿视频 V2 调用；该接口无历史作品分页上限。"""

    paging = state or {}
    request = bilibili.build_user_posts_v2_request(
        uid=uid,
        page=_int_state(paging, "page", default=1),
    )
    return TikHubOperationCall(
        platform="bilibili",
        business_operation="account_posts",
        operation="fetch_user_post_videos_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )
def _build_xiaohongshu_search(
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
        platform="xiaohongshu",
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
    if platform == "xiaohongshu":
        return _advance_xiaohongshu_search(current, body)
    if platform == "douyin":
        return _advance_douyin_search(current, body)
    if platform == "weibo":
        return _advance_weibo_search(current, body)
    if platform == "bilibili":
        return _advance_bilibili_search(current, body)
    return _advance_kuaishou_search(current, body)


def advance_xiaohongshu_user_search(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """推进指定账号解析用的用户搜索页码。"""
    current = state or {}
    result = xiaohongshu.XiaohongshuUserSearchPagination.from_response(
        current_page=_int_state(current, "page", default=1),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(
        _json_object(
            {
                "page": result.next_page,
                "search_id": result.search_id or "",
            }
        ),
        None,
    )


def build_douyin_user_profile_call(
    *,
    unique_id: str,
    config: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造按抖音号解析 sec_uid 的用户资料调用。"""

    cfg = config or {}
    request = douyin.build_user_profile_request(
        unique_id=unique_id,
        path=_str_config(
            cfg,
            "account_profile_path",
            default="/api/v1/douyin/web/handler_user_profile_v2",
        ),
        id_param=_str_config(cfg, "account_profile_id_param", default="unique_id"),
    )
    return TikHubOperationCall(
        platform="douyin",
        business_operation="account_info",
        operation="handler_user_profile_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
    )


def advance_xiaohongshu_user_posted_notes(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """推进指定账号笔记发现的 cursor。"""
    current = state or {}
    result = xiaohongshu.XiaohongshuUserNotesPagination.from_response(
        previous_cursor=_str_state(current, "cursor", default=""),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(
        _json_object({"cursor": result.next_cursor}),
        None,
    )


def advance_douyin_user_posted_videos(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
    config: dict[str, object] | None = None,
) -> TikHubPageAdvance:
    """推进抖音指定账号作品的 max_cursor 分页。"""

    cfg = config or {}
    result = douyin.DouyinUserPostsPagination.from_response(
        previous_cursor=_int_state(state or {}, "cursor", default=0),
        body=body,
        items_path=_str_config(cfg, "account_items_path", default="data.aweme_list"),
        cursor_path=_str_config(cfg, "account_cursor_path", default="data.max_cursor"),
        has_more_path=_str_config(cfg, "account_has_more_path", default="data.has_more"),
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"cursor": result.next_cursor}), None)


def advance_douyin_douplus_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """按 Dou+ ``data.data.cursor/hasMore`` 推进用户作品分页。"""

    result = douyin.DouyinUserPostsPagination.from_response(
        previous_cursor=_int_state(state or {}, "cursor", default=0),
        body=body,
        items_path="data.data.itemInfoList",
        cursor_path="data.data.cursor",
        has_more_path="data.data.hasMore",
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"cursor": result.next_cursor}), None)


def advance_kuaishou_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """推进快手指定账号作品 V2 的 pcursor。"""
    result = kuaishou.KuaishouUserPostsPagination.from_response(
        previous_cursor=_str_state(state or {}, "pcursor", default=""),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"pcursor": result.next_cursor}), None)


def advance_weibo_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """推进微博指定账号历史微博的 page/since_id 分页。"""

    current = state or {}
    result = weibo.WeiboUserPostsPagination.from_response(
        previous_since_id=_str_state(current, "since_id", default=""),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(
        _json_object(
            {
                "page": _int_state(current, "page", default=1) + 1,
                "since_id": result.next_since_id,
            }
        ),
        None,
    )


def advance_bilibili_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """推进 B站用户投稿视频 V2 页码。"""

    current = state or {}
    result = bilibili.BilibiliUserPostsPagination.from_response(
        current_page=_int_state(current, "page", default=1),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"page": result.next_page}), None)


def advance_kuaishou_user_search(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> TikHubPageAdvance:
    """推进快手用户搜索 V2 的 pcursor。"""
    result = kuaishou.KuaishouUserSearchPagination.from_response(
        previous_cursor=_str_state(state or {}, "pcursor", default=""),
        body=body,
    )
    if not result.should_continue:
        return TikHubPageAdvance(None, result.stop_reason)
    return TikHubPageAdvance(_json_object({"pcursor": result.next_cursor}), None)


def _advance_xiaohongshu_search(
    state: dict[str, object], body: dict[str, Any]
) -> TikHubPageAdvance:
    result = xiaohongshu.XiaohongshuSearchPagination.from_response(
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
    if platform == "xiaohongshu":
        return xiaohongshu.extract_search_items(body)
    if platform == "douyin":
        return douyin.extract_search_items(body)
    if platform == "weibo":
        return weibo.extract_search_items(body)
    if platform == "bilibili":
        return bilibili.extract_search_items(body)
    return kuaishou.extract_search_items(body)


def extract_xiaohongshu_user_search_items(
    body: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """提取指定账号解析用的用户候选。"""
    return xiaohongshu.extract_user_search_items(body)


def extract_xiaohongshu_user_info(body: dict[str, Any]) -> dict[str, Any]:
    """提取指定账号身份校验用的用户对象。"""
    return xiaohongshu.extract_user_info(body)


def extract_xiaohongshu_user_posted_notes(
    body: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """提取指定账号发布的笔记卡片。"""
    return xiaohongshu.extract_user_posted_notes(body)


def extract_douyin_user_posted_videos(
    body: dict[str, Any],
    *,
    config: dict[str, object] | None = None,
) -> tuple[dict[str, Any], ...]:
    """提取抖音指定账号作品卡片。"""

    cfg = config or {}
    return douyin.extract_user_posted_videos(
        body,
        items_path=_str_config(cfg, "account_items_path", default="data.aweme_list"),
    )


def extract_douyin_user_profile(body: dict[str, Any]) -> dict[str, Any]:
    """提取按抖音号解析得到的用户身份对象。"""

    return douyin.extract_user_profile(body)


def extract_kuaishou_user_profile(body: dict[str, Any]) -> dict[str, Any]:
    """提取快手用户 V2 身份对象。"""
    return kuaishou.extract_user_profile(body)


def extract_kuaishou_user_posts(
    body: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """提取快手指定账号作品卡片。"""
    return kuaishou.extract_user_post_items(body)


def extract_kuaishou_user_search_items(
    body: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """提取快手用户搜索 V2 候选。"""
    return kuaishou.extract_user_search_items(body)


def extract_weibo_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """提取微博 Web V2 用户搜索候选。"""

    return weibo.extract_user_search_items(body)


def extract_weibo_user_posts(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """提取微博指定账号历史微博卡片。"""

    return weibo.extract_user_post_items(body)


def extract_bilibili_user_posts(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """提取 B站指定账号的用户投稿视频 V2 作品卡片。"""

    return bilibili.extract_user_post_items(body)


def _provider_lookup_identity(
    *,
    platform: TikHubPlatform,
    external_content_id: str,
    alternate_ids: dict[str, str] | None = None,
) -> tuple[str, str]:
    """只允许经过平台白名单校验的 typed locator 进入 TikHub 请求。"""
    resolution = resolve_comment_target(
        platform=platform,
        external_content_id=external_content_id,
        alternate_ids=alternate_ids,
    )
    if resolution.state != "resolved":
        raise ValueError("identity_unavailable: 缺少可验证的平台评论目标身份")
    assert resolution.lookup_id_type is not None
    assert resolution.lookup_id is not None
    return resolution.lookup_id_type, resolution.lookup_id


def build_detail_call(platform: TikHubPlatform, content: CanonicalContentV1) -> TikHubOperationCall:
    id_type, lookup_value = _provider_lookup_identity(
        platform=platform,
        external_content_id=content.external_content_id,
        alternate_ids=content.alternate_ids,
    )
    if platform == "xiaohongshu":
        if content.content_type == "video":
            xiaohongshu_request = xiaohongshu.build_video_detail_request(note_id=lookup_value)
            operation = "get_video_note_detail"
        else:
            xiaohongshu_request = xiaohongshu.build_image_detail_request(note_id=lookup_value)
            operation = "get_image_note_detail"
        return TikHubOperationCall(
            "xiaohongshu",
            "content_detail",
            operation,
            "GET",
            xiaohongshu_request.path,
            _json_object(xiaohongshu_request.params),
        )
    if platform == "douyin":
        douyin_request = douyin.build_video_detail_request(aweme_id=lookup_value)
        return TikHubOperationCall(
            "douyin",
            "content_detail",
            "fetch_one_video_v3",
            douyin_request.method,
            douyin_request.path,
            _json_object(douyin_request.params),
        )
    if platform == "weibo":
        weibo_request = weibo.build_status_detail_request(status_id=lookup_value)
        return TikHubOperationCall(
            "weibo",
            "content_detail",
            "fetch_status_detail",
            weibo_request.method,
            weibo_request.path,
            _json_object(weibo_request.params),
        )
    if platform == "bilibili":
        bilibili_request = bilibili.build_video_detail_request(**{id_type: lookup_value})
        return TikHubOperationCall(
            "bilibili",
            "content_detail",
            "fetch_one_video",
            bilibili_request.method,
            bilibili_request.path,
            _json_object(bilibili_request.params),
        )
    kuaishou_request = kuaishou.build_video_detail_request(photo_id=lookup_value)
    return TikHubOperationCall(
        "kuaishou",
        "content_detail",
        "fetch_one_video",
        kuaishou_request.method,
        kuaishou_request.path,
        _json_object(kuaishou_request.params),
    )


def build_identity_resolution_call(
    *, platform: TikHubPlatform, locator_type: str, locator: str
) -> TikHubOperationCall:
    """短链详情属于独立身份解析 Operation，评论接口不接收链接。"""

    validated = resolve_supported_locator(platform, {locator_type: locator})
    if validated != (locator_type, locator):
        raise ValueError("identity_unavailable: 分享链接不是当前支持的精确定位身份")
    if platform == "xiaohongshu":
        xiaohongshu_request = xiaohongshu.build_image_detail_by_share_text_request(
            share_text=locator
        )
        return TikHubOperationCall(
            "xiaohongshu",
            "identity_resolution",
            "get_image_note_detail",
            "GET",
            xiaohongshu_request.path,
            _json_object(xiaohongshu_request.params),
        )
    douyin_request = douyin.build_video_detail_by_share_url_request(share_url=locator)
    return TikHubOperationCall(
        "douyin",
        "identity_resolution",
        "fetch_one_video_by_share_url",
        douyin_request.method,
        douyin_request.path,
        _json_object(douyin_request.params),
    )


def build_comments_call(
    *,
    platform: TikHubPlatform,
    external_content_id: str,
    alternate_ids: dict[str, str] | None = None,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    paging = state or {}
    id_type, lookup_value = _provider_lookup_identity(
        platform=platform,
        external_content_id=external_content_id,
        alternate_ids=alternate_ids,
    )
    if platform == "xiaohongshu":
        xiaohongshu_request = xiaohongshu.build_note_comments_request(
            note_id=lookup_value,
            cursor=_str_state(paging, "cursor", default=""),
            index=_int_state(paging, "index", default=0),
            page_area=_str_state(paging, "page_area", default="UNFOLDED"),
        )
        return TikHubOperationCall(
            "xiaohongshu",
            "comments",
            "get_note_comments",
            "GET",
            xiaohongshu_request.path,
            _json_object(xiaohongshu_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "douyin":
        douyin_request = douyin.build_video_comments_request(
            aweme_id=lookup_value,
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
            status_id=lookup_value,
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
            **{id_type: lookup_value},
            sort_mode="latest",
            next_offset=_bilibili_offset_state(paging, default=0),
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
        photo_id=lookup_value,
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
    alternate_ids: dict[str, str] | None = None,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造当前正式二级回复主 Operation；不做任何 App/Web 自动 fallback。"""
    paging = state or {}
    id_type, lookup_value = _provider_lookup_identity(
        platform=platform,
        external_content_id=external_content_id,
        alternate_ids=alternate_ids,
    )
    if platform == "xiaohongshu":
        xiaohongshu_request = xiaohongshu.build_sub_comments_request(
            note_id=lookup_value,
            comment_id=root_comment_id,
            cursor=_str_state(paging, "cursor", default=""),
            index=_int_state(paging, "index", default=1),
        )
        return TikHubOperationCall(
            "xiaohongshu",
            "sub_comments",
            "get_note_sub_comments",
            "GET",
            xiaohongshu_request.path,
            _json_object(xiaohongshu_request.params),
            pagination_input=_json_object(paging),
        )
    if platform == "douyin":
        douyin_request = douyin.build_video_comment_replies_request(
            item_id=lookup_value,
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
            **{id_type: lookup_value},
            next_offset=_optional_bilibili_offset_state(paging),
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
        photo_id=lookup_value,
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


def build_douyin_web_comments_call(
    *,
    external_content_id: str,
    state: dict[str, object] | None = None,
    count: int = 50,
) -> TikHubOperationCall:
    """构造抖音 Web 一级评论补采调用，保留为独立 Provider Attempt。"""

    paging = state or {}
    request = backup.build_douyin_web_comments_backup_request(
        aweme_id=external_content_id,
        cursor=_int_state(paging, "cursor", default=0),
        count=count,
    )
    return TikHubOperationCall(
        "douyin",
        "comments",
        "fetch_video_comments_web",
        request.method,
        request.path,
        _json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_douyin_web_sub_comments_call(
    *,
    external_content_id: str,
    root_comment_id: str,
    state: dict[str, object] | None = None,
    count: int = 100,
) -> TikHubOperationCall:
    """构造抖音 Web 二级回复补采调用，保留为独立 Provider Attempt。"""

    paging = state or {}
    request = backup.build_douyin_web_replies_backup_request(
        item_id=external_content_id,
        comment_id=root_comment_id,
        cursor=_int_state(paging, "cursor", default=0),
        count=count,
    )
    return TikHubOperationCall(
        "douyin",
        "sub_comments",
        "fetch_video_comment_replies_web",
        request.method,
        request.path,
        _json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_kuaishou_web_comments_call(
    *,
    external_content_id: str,
    alternate_ids: dict[str, str] | None = None,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造快手 Web 一级评论补采调用。"""
    paging = state or {}
    _, lookup_value = _provider_lookup_identity(
        platform="kuaishou",
        external_content_id=external_content_id,
        alternate_ids=alternate_ids,
    )
    request = kuaishou.build_web_video_comments_request(
        photo_id=lookup_value,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        "kuaishou",
        "comments",
        "fetch_one_video_comment_web",
        request.method,
        request.path,
        _json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_kuaishou_web_sub_comments_call(
    *,
    external_content_id: str,
    root_comment_id: str,
    alternate_ids: dict[str, str] | None = None,
    state: dict[str, object] | None = None,
) -> TikHubOperationCall:
    """构造快手 Web 二级回复补采调用。"""
    paging = state or {}
    _, lookup_value = _provider_lookup_identity(
        platform="kuaishou",
        external_content_id=external_content_id,
        alternate_ids=alternate_ids,
    )
    request = kuaishou.build_web_video_sub_comments_request(
        photo_id=lookup_value,
        root_comment_id=root_comment_id,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubOperationCall(
        "kuaishou",
        "sub_comments",
        "fetch_one_video_sub_comment_web",
        request.method,
        request.path,
        _json_object(request.params),
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
    if platform == "xiaohongshu":
        return _advance_xiaohongshu_comments(current, body, default_index=0)
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
    if platform == "xiaohongshu":
        return _advance_xiaohongshu_comments(current, body, default_index=1)
    if platform == "douyin":
        return _advance_douyin_comments(current, body)
    if platform == "weibo":
        return _advance_weibo_sub_comments(current, body)
    if platform == "bilibili":
        return _advance_bilibili_comments(current, body)
    return _advance_kuaishou_comments(current, body, item_key="subComments")


def _advance_xiaohongshu_comments(
    state: dict[str, object],
    body: dict[str, Any],
    *,
    default_index: int,
) -> TikHubPageAdvance:
    page_area = _str_state(state, "page_area", default="UNFOLDED")
    result = xiaohongshu.XiaohongshuCommentPagination.from_response(
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
    previous_cursor = _int_state(state, "cursor", default=0)
    result = douyin.DouyinCursorPagination.from_response(
        previous_cursor=previous_cursor,
        body=body,
    )


    if not result.should_continue:
        resume_state = None
        # TikHub 偶尔在空页上返回递增 cursor（甚至把 total 改成 cursor），
        # 这不是可继续采集的有效分页。只有当前页确实返回评论时才允许
        # Runner 做一次“提前结束”恢复探测，避免全量模式无限计费请求。
        has_items = bool(douyin.extract_comment_items(body))
        if (
            result.stop_reason == "provider_exhausted"
            and result.next_cursor > previous_cursor
            and has_items
        ):
            resume_state = _json_object({"cursor": result.next_cursor})
        return TikHubPageAdvance(None, result.stop_reason, resume_state)
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
    next_offset = _bilibili_offset_from_response(returned)
    if isinstance(next_offset, str):
        # App 评论接口把 next_offset 声明为整数，但部分响应的
        # pagination_reply.next_offset 会混入 Web 的不透明 token。该 token 回传会
        # 触发 422；同一 cursor.next 提供了 App 接口可用的整数续页游标。
        next_offset = _nonnegative_integer(cursor.get("next"))
    result = bilibili.BilibiliCursorPagination.from_returned_cursor(
        previous_cursor=_bilibili_offset_state(state, default=0),
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
    if platform == "xiaohongshu":
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
    if platform == "xiaohongshu":
        return xiaohongshu.extract_comment_items(body)
    if platform == "douyin":
        return douyin.extract_comment_items(body)
    if platform == "weibo":
        return weibo.extract_comment_items(body)
    if platform == "bilibili":
        return bilibili.extract_comment_items(body)
    return kuaishou.extract_comment_items(body)


def extract_comment_counts(
    platform: TikHubPlatform, body: dict[str, Any]
) -> tuple[int | None, int | None]:
    """提取 Provider 返回的全部评论数和一级评论数；未支持的平台返回未知。"""
    if platform == "xiaohongshu":
        return xiaohongshu.extract_comment_counts(body)
    if platform == "douyin":
        return douyin.extract_comment_counts(body)
    if platform == "kuaishou":
        return kuaishou.extract_comment_counts(body)
    return None, None


def extract_sub_comment_items(
    platform: TikHubPlatform, body: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    """按当前正式二级回复响应形态提取业务 item。"""
    if platform == "xiaohongshu":
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
    if platform == "xiaohongshu":
        return xiaohongshu_mapper.map_content(
            raw, _xiaohongshu_context(context), item_locator=item_locator
        )
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
    if platform == "xiaohongshu":
        return xiaohongshu_mapper.map_comment(
            raw,
            _xiaohongshu_context(context),
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


def _xiaohongshu_context(
    context: TikHubMappingContext,
) -> xiaohongshu_mapper.XiaohongshuMappingContext:
    return xiaohongshu_mapper.XiaohongshuMappingContext(
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


def _bilibili_offset_state(
    state: dict[str, object],
    *,
    default: int | str,
) -> int | str:
    value = state.get("next_offset", default)
    if isinstance(value, bool):
        raise ValueError("TikHub pagination next_offset 必须是非负整数或非空字符串")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("TikHub pagination next_offset 不能小于 0")
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("TikHub pagination next_offset 必须是非负整数或非空字符串")


def _optional_bilibili_offset_state(state: dict[str, object]) -> int | str | None:
    if "next_offset" not in state or state["next_offset"] is None:
        return None
    return _bilibili_offset_state(state, default=0)


def _bilibili_offset_from_response(value: object) -> int | str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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
    "advance_bilibili_user_posts",
    "advance_search",
    "advance_sub_comments",
    "advance_douyin_user_posted_videos",
    "advance_kuaishou_user_posts",
    "advance_kuaishou_user_search",
    "advance_xiaohongshu_user_posted_notes",
    "advance_xiaohongshu_user_search",
    "build_comments_call",
    "build_bilibili_user_posts_call",
    "build_douyin_user_posted_videos_call",
    "build_douyin_user_profile_call",
    "build_kuaishou_user_posts_call",
    "build_kuaishou_user_profile_call",
    "build_kuaishou_user_search_call",
    "build_kuaishou_web_comments_call",
    "build_kuaishou_web_sub_comments_call",
    "build_detail_call",
    "build_search_call",
    "build_sub_comments_call",
    "build_xiaohongshu_user_info_call",
    "build_xiaohongshu_user_posted_notes_call",
    "build_xiaohongshu_user_search_call",
    "extract_comment_items",
    "extract_comment_counts",
    "extract_bilibili_user_posts",
    "extract_detail_items",
    "extract_search_items",
    "extract_douyin_user_posted_videos",
    "extract_douyin_user_profile",
    "extract_kuaishou_user_posts",
    "extract_kuaishou_user_profile",
    "extract_kuaishou_user_search_items",
    "extract_sub_comment_items",
    "extract_xiaohongshu_user_info",
    "extract_xiaohongshu_user_posted_notes",
    "extract_xiaohongshu_user_search_items",
    "map_comment",
    "map_content",
    "mapping_context",
]
