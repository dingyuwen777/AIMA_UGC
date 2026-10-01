"""TikHub 五平台账号 Discovery 的生产 Runtime Adapter。"""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import TypeAdapter

from aima_ugc.contracts.provider import JsonObject

from . import runtime as shared_runtime
from .operations import backup, bilibili, douyin, kuaishou, weibo, xiaohongshu_accounts

_JSON_OBJECT_ADAPTER = TypeAdapter(JsonObject)


class TikHubAccountOperationCall(shared_runtime.TikHubOperationCall):
    """沿用通用 TikHub 调用事实结构，但账号 Discovery 不进入公开 Collection Capability。"""


def build_user_search_call(
    *,
    keyword: str,
    state: dict[str, object] | None = None,
) -> TikHubAccountOperationCall:
    """把账号搜索输入映射为正式 App V2 `search_users` 调用。"""
    paging = state or {}
    request = xiaohongshu_accounts.build_search_users_request(
        keyword=keyword,
        page=_int_state(paging, "page", default=1),
        search_id=_optional_str_state(paging, "search_id"),
    )
    return TikHubAccountOperationCall(
        platform="xiaohongshu",
        business_operation=cast(Any, "account_search"),
        operation="search_users",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def advance_user_search(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> shared_runtime.TikHubPageAdvance:
    """按正式用户搜索分页状态推进下一页。"""
    current = state or {}
    result = xiaohongshu_accounts.XiaohongshuUserSearchPagination.from_response(
        current_page=_int_state(current, "page", default=1),
        body=body,
        previous_item_ids=tuple(_string_list(current.get("item_ids"))),
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(
        _json_object(
            {
                "page": result.next_page,
                "search_id": result.search_id or "",
                "item_ids": list(result.item_ids),
            }
        ),
        None,
    )


def extract_user_search_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """通过生产 Operation Extractor 读取用户搜索候选。"""
    return xiaohongshu_accounts.extract_user_search_items(body)


def build_user_info_call(*, user_id: str) -> TikHubAccountOperationCall:
    """构造已解析稳定 user_id 的用户详情调用。"""
    request = xiaohongshu_accounts.build_user_info_request(user_id=user_id)
    return TikHubAccountOperationCall(
        platform="xiaohongshu",
        business_operation=cast(Any, "account_info"),
        operation="get_user_info",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
    )


def extract_user_info_item(body: dict[str, Any]) -> dict[str, Any] | None:
    """通过生产 Operation Extractor 读取用户详情。"""
    return xiaohongshu_accounts.extract_user_info_item(body)


def build_user_notes_call(
    *,
    user_id: str,
    state: dict[str, object] | None = None,
) -> TikHubAccountOperationCall:
    """构造指定稳定 user_id 的已发布笔记 cursor 调用。"""
    paging = state or {}
    request = xiaohongshu_accounts.build_user_posted_notes_request(
        user_id=user_id,
        cursor=_str_state(paging, "cursor", default=""),
    )
    return TikHubAccountOperationCall(
        platform="xiaohongshu",
        business_operation=cast(Any, "account_notes"),
        operation="get_user_posted_notes",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def advance_user_notes(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> shared_runtime.TikHubPageAdvance:
    """按用户笔记最后一项 cursor 推进下一页，并保留重复页保护。"""
    current = state or {}
    result = xiaohongshu_accounts.XiaohongshuUserNotesPagination.from_response(
        previous_cursor=_str_state(current, "cursor", default=""),
        body=body,
        previous_item_ids=tuple(_string_list(current.get("item_ids"))),
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    assert result.next_cursor is not None
    return shared_runtime.TikHubPageAdvance(
        _json_object(
            {
                "cursor": result.next_cursor,
                "item_ids": list(result.item_ids),
            }
        ),
        None,
    )


def extract_user_note_items(body: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """通过生产 Operation Extractor 读取用户已发布笔记。"""
    return xiaohongshu_accounts.extract_user_posted_note_items(body)


def _json_object(value: dict[str, object]) -> JsonObject:
    """把 Runtime 私有状态校验为项目统一 JSON Object。"""
    return _JSON_OBJECT_ADAPTER.validate_python(value)


def _int_state(state: dict[str, object], key: str, *, default: int) -> int:
    """读取整数分页状态并拒绝 bool 等隐式类型。"""
    value = state.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"TikHub account pagination {key} 必须为整数")
    return value


def _str_state(state: dict[str, object], key: str, *, default: str) -> str:
    """读取字符串分页状态。"""
    value = state.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"TikHub account pagination {key} 必须为字符串")
    return value


def _optional_str_state(state: dict[str, object], key: str) -> str | None:
    """读取可选字符串分页状态，空字符串归一为 None。"""
    if key not in state or state[key] in {None, ""}:
        return None
    return _str_state(state, key, default="")


def _string_list(value: object) -> list[str]:
    """把分页防重 ID 列表限制为非空字符串集合。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


__all__ = [
    "build_user_search_call",
    "advance_user_search",
    "extract_user_search_items",
    "build_user_info_call",
    "extract_user_info_item",
    "build_user_notes_call",
    "advance_user_notes",
    "extract_user_note_items",
    "build_douyin_user_posted_videos_call",
    "build_douyin_douplus_user_posts_call",
    "build_kuaishou_user_profile_call",
    "build_kuaishou_user_search_call",
    "build_kuaishou_user_posts_call",
    "build_weibo_user_search_call",
    "build_weibo_user_posts_call",
    "build_bilibili_user_posts_call",
    "build_douyin_user_profile_call",
    "advance_douyin_user_posted_videos",
    "advance_douyin_douplus_user_posts",
    "advance_kuaishou_user_posts",
    "advance_weibo_user_posts",
    "advance_bilibili_user_posts",
    "advance_kuaishou_user_search",
    "extract_douyin_user_posted_videos",
    "extract_douyin_user_profile",
    "extract_kuaishou_user_profile",
    "extract_kuaishou_user_posts",
    "extract_kuaishou_user_search_items",
    "extract_weibo_user_search_items",
    "extract_weibo_user_posts",
    "extract_bilibili_user_posts",
]


def build_douyin_user_posted_videos_call(
    *,
    account_value: str,
    state: dict[str, object] | None = None,
    config: dict[str, object] | None = None,
) -> TikHubAccountOperationCall:
    """构造抖音指定账号作品调用；账号接口细节由人工配置提供。"""

    cfg = config or {}
    paging = state or {}
    request = douyin.build_user_posted_videos_request(
        account_value=account_value,
        cursor=_int_state(paging, "cursor", default=0),
        path=shared_runtime._str_config(
            cfg,
            "account_posts_path",
            default="/api/v1/douyin/app/v3/fetch_user_post_videos",
        ),
        method=cast(
            Literal["GET", "POST"],
            shared_runtime._str_config(cfg, "account_posts_method", default="GET"),
        ),
        account_param=shared_runtime._str_config(cfg, "account_id_param", default="sec_user_id"),
        cursor_param=shared_runtime._str_config(cfg, "account_cursor_param", default="max_cursor"),
    )
    return TikHubAccountOperationCall(
        platform="douyin",
        business_operation="account_posts",
        operation="fetch_user_post_videos",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        body=shared_runtime._optional_json_object(request.body),
        pagination_input=_json_object(paging),
    )


def build_douyin_douplus_user_posts_call(
    *,
    sec_uid: str,
    state: dict[str, object] | None = None,
    count: int = 10,
) -> TikHubAccountOperationCall:
    """构造 App V3 作品接口失败后的 Dou+ 简洁作品补采调用。"""

    paging = state or {}
    request = backup.build_douyin_douplus_user_posts_backup_request(
        sec_uid=sec_uid,
        cursor=str(_int_state(paging, "cursor", default=0)),
        count=count,
    )
    return TikHubAccountOperationCall(
        platform="douyin",
        business_operation="account_posts",
        operation="fetch_user_posts_douplus",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        body=shared_runtime._optional_json_object(request.body),
        pagination_input=_json_object(paging),
    )


def build_kuaishou_user_profile_call(*, user_reference: str) -> TikHubAccountOperationCall:
    """构造快手 eid/userId → 用户资料的 V2 调用。"""
    request = kuaishou.build_user_profile_request(user_id=user_reference)
    return TikHubAccountOperationCall(
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
) -> TikHubAccountOperationCall:
    """构造快手号/昵称 → 用户候选的搜索 V2 调用。"""
    paging = state or {}
    request = kuaishou.build_user_search_request(
        keyword=keyword,
        pcursor=_str_state(paging, "pcursor", default=""),
    )
    return TikHubAccountOperationCall(
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
) -> TikHubAccountOperationCall:
    """构造快手指定账号按最新排序的作品 V2 调用。"""
    paging = state or {}
    request = kuaishou.build_user_posts_request(
        user_id=user_id,
        pcursor=_str_state(paging, "pcursor", default=""),
        sort="latest",
    )
    return TikHubAccountOperationCall(
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
) -> TikHubAccountOperationCall:
    """构造微博昵称 → UID 的 Web V2 用户搜索调用。"""

    paging = state or {}
    request = weibo.build_user_search_request(
        query=query,
        page=_int_state(paging, "page", default=1),
        nickname=nickname,
    )
    return TikHubAccountOperationCall(
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
) -> TikHubAccountOperationCall:
    """构造微博指定账号历史微博调用，按官方 since_id 全分页。"""

    paging = state or {}
    request = weibo.build_user_posts_request(
        uid=uid,
        page=_int_state(paging, "page", default=1),
        since_id=_str_state(paging, "since_id", default=""),
        feature=feature,
    )
    return TikHubAccountOperationCall(
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
) -> TikHubAccountOperationCall:
    """构造 B站用户投稿视频 V2 调用；该接口无历史作品分页上限。"""

    paging = state or {}
    request = bilibili.build_user_posts_v2_request(
        uid=uid,
        page=_int_state(paging, "page", default=1),
    )
    return TikHubAccountOperationCall(
        platform="bilibili",
        business_operation="account_posts",
        operation="fetch_user_post_videos_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
        pagination_input=_json_object(paging),
    )


def build_douyin_user_profile_call(
    *,
    unique_id: str,
    config: dict[str, object] | None = None,
) -> TikHubAccountOperationCall:
    """构造按抖音号解析 sec_uid 的用户资料调用。"""

    cfg = config or {}
    request = douyin.build_user_profile_request(
        unique_id=unique_id,
        path=shared_runtime._str_config(
            cfg,
            "account_profile_path",
            default="/api/v1/douyin/web/handler_user_profile_v2",
        ),
        id_param=shared_runtime._str_config(cfg, "account_profile_id_param", default="unique_id"),
    )
    return TikHubAccountOperationCall(
        platform="douyin",
        business_operation="account_info",
        operation="handler_user_profile_v2",
        method=request.method,
        path=request.path,
        params=_json_object(request.params),
    )


def advance_douyin_user_posted_videos(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
    config: dict[str, object] | None = None,
) -> shared_runtime.TikHubPageAdvance:
    """推进抖音指定账号作品的 max_cursor 分页。"""

    cfg = config or {}
    result = douyin.DouyinUserPostsPagination.from_response(
        previous_cursor=_int_state(state or {}, "cursor", default=0),
        body=body,
        items_path=shared_runtime._str_config(cfg, "account_items_path", default="data.aweme_list"),
        cursor_path=shared_runtime._str_config(
            cfg, "account_cursor_path", default="data.max_cursor"
        ),
        has_more_path=shared_runtime._str_config(
            cfg, "account_has_more_path", default="data.has_more"
        ),
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(_json_object({"cursor": result.next_cursor}), None)


def advance_douyin_douplus_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> shared_runtime.TikHubPageAdvance:
    """按 Dou+ ``data.data.cursor/hasMore`` 推进用户作品分页。"""

    result = douyin.DouyinUserPostsPagination.from_response(
        previous_cursor=_int_state(state or {}, "cursor", default=0),
        body=body,
        items_path="data.data.itemInfoList",
        cursor_path="data.data.cursor",
        has_more_path="data.data.hasMore",
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(_json_object({"cursor": result.next_cursor}), None)


def advance_kuaishou_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> shared_runtime.TikHubPageAdvance:
    """推进快手指定账号作品 V2 的 pcursor。"""
    result = kuaishou.KuaishouUserPostsPagination.from_response(
        previous_cursor=_str_state(state or {}, "pcursor", default=""),
        body=body,
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(_json_object({"pcursor": result.next_cursor}), None)


def advance_weibo_user_posts(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> shared_runtime.TikHubPageAdvance:
    """推进微博指定账号历史微博的 page/since_id 分页。"""

    current = state or {}
    result = weibo.WeiboUserPostsPagination.from_response(
        previous_since_id=_str_state(current, "since_id", default=""),
        body=body,
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(
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
) -> shared_runtime.TikHubPageAdvance:
    """推进 B站用户投稿视频 V2 页码。"""

    current = state or {}
    result = bilibili.BilibiliUserPostsPagination.from_response(
        current_page=_int_state(current, "page", default=1),
        body=body,
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(_json_object({"page": result.next_page}), None)


def advance_kuaishou_user_search(
    *,
    state: dict[str, object] | None,
    body: dict[str, Any],
) -> shared_runtime.TikHubPageAdvance:
    """推进快手用户搜索 V2 的 pcursor。"""
    result = kuaishou.KuaishouUserSearchPagination.from_response(
        previous_cursor=_str_state(state or {}, "pcursor", default=""),
        body=body,
    )
    if not result.should_continue:
        return shared_runtime.TikHubPageAdvance(None, result.stop_reason)
    return shared_runtime.TikHubPageAdvance(_json_object({"pcursor": result.next_cursor}), None)


def extract_douyin_user_posted_videos(
    body: dict[str, Any],
    *,
    config: dict[str, object] | None = None,
) -> tuple[dict[str, Any], ...]:
    """提取抖音指定账号作品卡片。"""

    cfg = config or {}
    return douyin.extract_user_posted_videos(
        body,
        items_path=shared_runtime._str_config(cfg, "account_items_path", default="data.aweme_list"),
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
