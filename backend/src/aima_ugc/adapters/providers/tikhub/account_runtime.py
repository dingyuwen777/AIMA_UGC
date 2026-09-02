"""TikHub 小红书账号 Discovery 的生产 Runtime Adapter。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import SecretStr, TypeAdapter

from aima_ugc.contracts.provider import JsonObject
from aima_ugc.modules.collection.providers.transport import ProviderTransportRequest

from .operations import xiaohongshu

_JSON_OBJECT_ADAPTER = TypeAdapter(JsonObject)
TikHubAccountBusinessOperation = Literal["account_search", "account_info", "account_notes"]


@dataclass(frozen=True, slots=True)
class TikHubAccountOperationCall:
    """一个不含 Secret 的小红书账号 Discovery 调用事实。"""

    business_operation: TikHubAccountBusinessOperation
    operation: str
    method: Literal["GET"]
    path: str
    params: JsonObject
    pagination_input: JsonObject | None = None

    def transport_request(self, credential: SecretStr) -> ProviderTransportRequest:
        """在发送边界注入 Secret，不把鉴权事实写进调试输出。"""
        return ProviderTransportRequest(
            transport_kind="http",
            method=self.method,
            path=self.path,
            params=self.params,
            body=None,
            credential=credential,
        )


@dataclass(frozen=True, slots=True)
class TikHubAccountPageAdvance:
    """账号 Discovery 的 Provider-private 分页推进结果。"""

    next_state: JsonObject | None
    stop_reason: str | None

    @property
    def should_continue(self) -> bool:
        """只有存在下一页状态时才允许继续产生 Provider 请求。"""
        return self.next_state is not None


def build_user_search_call(
    *,
    keyword: str,
    state: dict[str, object] | None = None,
) -> TikHubAccountOperationCall:
    """把账号搜索输入映射为正式 App V2 `search_users` 调用。"""
    paging = state or {}
    request = xiaohongshu.build_search_users_request(
        keyword=keyword,
        page=_int_state(paging, "page", default=1),
        search_id=_optional_str_state(paging, "search_id"),
    )
    return TikHubAccountOperationCall(
        business_operation="account_search",
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
) -> TikHubAccountPageAdvance:
    """按正式用户搜索分页状态推进下一页。"""
    current = state or {}
    result = xiaohongshu.XiaohongshuUserSearchPagination.from_response(
        current_page=_int_state(current, "page", default=1),
        body=body,
        previous_item_ids=tuple(_string_list(current.get("item_ids"))),
    )
    if not result.should_continue:
        return TikHubAccountPageAdvance(None, result.stop_reason)
    return TikHubAccountPageAdvance(
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
    return xiaohongshu.extract_user_search_items(body)


def build_user_info_call(*, user_id: str) -> TikHubAccountOperationCall:
    """构造已解析稳定 user_id 的用户详情调用。"""
    request = xiaohongshu.build_user_info_request(user_id=user_id)
    return TikHubAccountOperationCall(
        business_operation="account_info",
        operation="get_user_info",
        method="GET",
        path=request.path,
        params=_json_object(request.params),
    )


def extract_user_info_item(body: dict[str, Any]) -> dict[str, Any] | None:
    """通过生产 Operation Extractor 读取用户详情。"""
    return xiaohongshu.extract_user_info_item(body)


def build_user_notes_call(
    *,
    user_id: str,
    state: dict[str, object] | None = None,
) -> TikHubAccountOperationCall:
    """构造指定稳定 user_id 的已发布笔记 cursor 调用。"""
    paging = state or {}
    request = xiaohongshu.build_user_posted_notes_request(
        user_id=user_id,
        cursor=_str_state(paging, "cursor", default=""),
    )
    return TikHubAccountOperationCall(
        business_operation="account_notes",
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
) -> TikHubAccountPageAdvance:
    """按用户笔记最后一项 cursor 推进下一页，并保留重复页保护。"""
    current = state or {}
    result = xiaohongshu.XiaohongshuUserNotesPagination.from_response(
        previous_cursor=_str_state(current, "cursor", default=""),
        body=body,
        previous_item_ids=tuple(_string_list(current.get("item_ids"))),
    )
    if not result.should_continue:
        return TikHubAccountPageAdvance(None, result.stop_reason)
    assert result.next_cursor is not None
    return TikHubAccountPageAdvance(
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
    return xiaohongshu.extract_user_posted_note_items(body)


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
    "TikHubAccountOperationCall",
    "TikHubAccountPageAdvance",
    "advance_user_notes",
    "advance_user_search",
    "build_user_info_call",
    "build_user_notes_call",
    "build_user_search_call",
    "extract_user_info_item",
    "extract_user_note_items",
    "extract_user_search_items",
]
