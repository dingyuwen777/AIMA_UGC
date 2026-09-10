"""飞书 Wiki 多维表读取、字段映射与 Upsert Adapter。"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from time import monotonic
from typing import Any

import httpx

from .config import FeishuConfig

_FIELD_TYPES_TEXT = frozenset({1})
_FIELD_TYPES_NUMBER = frozenset({2})
_FIELD_TYPES_SINGLE_SELECT = frozenset({3})
_FIELD_TYPES_MULTI_SELECT = frozenset({4})
_FIELD_TYPES_DATETIME = frozenset({5})
_FIELD_TYPES_URL = frozenset({15})
_TABLE_CLONE_FIELD_TYPES = frozenset({1, 2, 3, 4, 5, 7, 11, 13, 15, 17})
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

DEFAULT_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "平台": ("平台", "媒体平台"),
    "情感": ("情感", "情感标签", "正负面", "正面/负面"),
    "内容ID": ("内容ID", "内容 Id", "内容ID号", "内容编号"),
    "标题": ("标题", "内容标题"),
    "正文": ("正文", "内文", "内容正文", "内容"),
    "作者": ("作者", "用户", "作者名称"),
    "内容链接": ("内容链接", "原文链接", "链接", "URL"),
    "发布时间": ("发布时间", "发表时间", "出版日期"),
    "代表性主题": ("代表性主题", "主题"),
    "入选理由": ("入选理由", "理由"),
    "代表性评分": ("代表性评分", "评分"),
    "声音内容/连接": ("声音内容/连接",),
    "典型评论示例": ("典型评论示例",),
    "优先级": ("优先级",),
    "来源": ("来源",),
    "一级标签": ("一级标签",),
    "二级标签": ("二级标签",),
    "用户情绪": ("用户情绪",),
    "处理建议": ("处理建议",),
    "处理进展": ("处理进展",),
}
DEFAULT_UPSERT_KEY_FIELDS = ("平台", "情感", "内容ID")


class FeishuAPIError(RuntimeError):
    """飞书 HTTP 或业务协议错误；不回显响应正文和 Secret。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        api_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.api_code = api_code
        self.retryable = retryable


class FeishuSyncError(RuntimeError):
    """飞书字段或同步计划不满足安全边界。"""


@dataclass(frozen=True, slots=True)
class FeishuField:
    """飞书字段定义的最小公共投影。"""

    field_id: str
    name: str
    field_type: int
    options: tuple[str, ...] = ()
    field_property: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class FeishuTableInfo:
    """新建多维表数据表的身份信息。"""

    table_id: str
    name: str
    skipped_fields: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "skipped_fields": list(self.skipped_fields),
        }


@dataclass(frozen=True, slots=True)
class FeishuFieldMapping:
    """内部输出字段到飞书字段的动态映射。"""

    resolved: Mapping[str, FeishuField]
    unavailable: Mapping[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "resolved": {
                logical: {
                    "field_id": field.field_id,
                    "field_name": field.name,
                    "field_type": field.field_type,
                    "options": list(field.options),
                }
                for logical, field in self.resolved.items()
            },
            "unavailable": dict(self.unavailable),
        }


@dataclass(frozen=True, slots=True)
class _FeishuRecord:
    record_id: str
    fields: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _FeishuUpdate:
    record_id: str
    key: tuple[str, ...]
    fields: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class FeishuPreparedSync:
    """写入前完成的字段、记录和 Upsert 计划。"""

    app_token: str
    field_mapping: FeishuFieldMapping
    existing_records: tuple[_FeishuRecord, ...]
    updates: tuple[_FeishuUpdate, ...]
    creates: tuple[Mapping[str, object], ...]
    selected_keys: tuple[tuple[str, ...], ...]
    expected_fields: Mapping[tuple[str, ...], Mapping[str, object]]

    @property
    def before_snapshot(self) -> tuple[dict[str, object], ...]:
        """返回可审计的写入前记录快照。"""

        return tuple(
            {"record_id": record.record_id, "fields": dict(record.fields)}
            for record in self.existing_records
        )


@dataclass(frozen=True, slots=True)
class FeishuSyncSummary:
    """一次实际同步和回读核验的摘要。"""

    created_count: int
    updated_count: int
    verified_count: int
    verification_errors: tuple[str, ...]
    field_mapping: FeishuFieldMapping
    target_table_id: str | None = None
    target_table_name: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "created_count": self.created_count,
            "updated_count": self.updated_count,
            "verified_count": self.verified_count,
            "verification_errors": list(self.verification_errors),
            "field_mapping": self.field_mapping.as_dict(),
        }
        if self.target_table_id is not None:
            payload["target_table_id"] = self.target_table_id
        if self.target_table_name is not None:
            payload["target_table_name"] = self.target_table_name
        return payload


class FeishuBitableClient:
    """调用飞书公开 API 完成字段发现、分页读取和安全 Upsert。"""

    def __init__(
        self,
        *,
        config: FeishuConfig,
        app_secret: str,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        upsert_key_fields: Sequence[str] = DEFAULT_UPSERT_KEY_FIELDS,
    ) -> None:
        if not app_secret or not app_secret.strip():
            raise ValueError("飞书 App Secret 不能为空")
        self._config = config
        self._app_secret = app_secret
        self._sleep = sleep
        self._upsert_key_fields = tuple(upsert_key_fields)
        if (
            not self._upsert_key_fields
            or len(set(self._upsert_key_fields)) != len(self._upsert_key_fields)
            or any(not field.strip() for field in self._upsert_key_fields)
        ):
            raise ValueError("飞书 Upsert 键字段必须是非空且不重复的字段名序列")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=config.base_url + "/",
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )
        self._tenant_token: str | None = None
        self._tenant_token_expires_at = 0.0

    def close(self) -> None:
        """关闭内部 HTTP Client。"""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FeishuBitableClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def resolve_app_token(self) -> str:
        """返回直接配置的 Base Token，或通过 Wiki 节点 Token 解析。"""

        if self._config.app_token:
            return self._config.app_token
        wiki_token = self._config.wiki_token
        if not wiki_token:
            raise FeishuSyncError("飞书缺少 app_token 或 wiki_token")

        payload = self._request(
            "GET",
            "open-apis/wiki/v2/spaces/get_node",
            params={"token": wiki_token},
        )
        data = payload.get("data")
        node = data.get("node") if isinstance(data, dict) else None
        if not isinstance(node, dict):
            raise FeishuAPIError("飞书 Wiki 节点响应缺少 node", api_code=0)
        obj_token = node.get("obj_token")
        if not isinstance(obj_token, str) or not obj_token.strip():
            raise FeishuAPIError("飞书 Wiki 节点不是可用的多维表", api_code=0)
        return obj_token.strip()

    def create_table_from_current(
        self,
        *,
        name: str,
        default_view_name: str = "表格视图",
    ) -> FeishuTableInfo:
        """复制当前模板表的可创建字段，并在同一 Base 中新建数据表。"""

        table_name = name.strip()
        if not table_name:
            raise ValueError("新建飞书数据表名称不能为空")
        view_name = default_view_name.strip()
        if not view_name:
            raise ValueError("飞书默认视图名称不能为空")

        app_token = self.resolve_app_token()
        source_fields = self.list_fields(app_token)
        source_mapping = resolve_field_mapping(
            source_fields,
            aliases={**DEFAULT_FIELD_ALIASES, **self._config.field_aliases},
        )
        missing_keys = [
            logical for logical in self._upsert_key_fields if logical not in source_mapping.resolved
        ]
        if missing_keys:
            raise FeishuSyncError("模板数据表缺少必需字段: " + ", ".join(missing_keys))
        field_definitions = [
            _table_field_definition(field)
            for field in source_fields
            if field.field_type in _TABLE_CLONE_FIELD_TYPES
        ]
        skipped_fields = tuple(
            field.name
            for field in source_fields
            if field.field_type not in _TABLE_CLONE_FIELD_TYPES
        )
        if not field_definitions:
            raise FeishuSyncError("模板数据表没有可复制的字段")

        payload = self._request(
            "POST",
            f"open-apis/bitable/v1/apps/{app_token}/tables",
            json_body={
                "table": {
                    "name": table_name,
                    "default_view_name": view_name,
                    "fields": field_definitions,
                }
            },
        )
        data = payload.get("data")
        table_payload = data.get("table") if isinstance(data, dict) else None
        table_id = table_payload.get("table_id") if isinstance(table_payload, dict) else None
        if not isinstance(table_id, str) or not table_id.strip():
            table_id = data.get("table_id") if isinstance(data, dict) else None
        if not isinstance(table_id, str) or not table_id.strip():
            raise FeishuAPIError("飞书新建数据表响应缺少 table_id", api_code=0)
        return FeishuTableInfo(
            table_id=table_id.strip(),
            name=table_name,
            skipped_fields=skipped_fields,
        )

    def list_fields(self, app_token: str | None = None) -> tuple[FeishuField, ...]:
        """分页读取多维表字段定义。"""

        token = app_token or self.resolve_app_token()
        fields: list[FeishuField] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            payload = self._request(
                "GET",
                f"open-apis/bitable/v1/apps/{token}/tables/{self._config.table_id}/fields",
                params=params,
            )
            data = payload.get("data")
            if not isinstance(data, dict):
                raise FeishuAPIError("飞书字段响应缺少 data", api_code=0)
            raw_items = data.get("items", data.get("field_items", []))
            if not isinstance(raw_items, list):
                raise FeishuAPIError("飞书字段响应 items 格式错误", api_code=0)
            fields.extend(_parse_field(item) for item in raw_items)
            has_more = data.get("has_more") is True
            next_page_token = data.get("page_token")
            if not has_more:
                break
            if not isinstance(next_page_token, str) or not next_page_token:
                raise FeishuAPIError("飞书字段分页响应缺少 page_token", api_code=0)
            page_token = next_page_token
        return tuple(fields)

    def list_records(self, app_token: str | None = None) -> tuple[_FeishuRecord, ...]:
        """分页读取多维表记录。"""

        token = app_token or self.resolve_app_token()
        records: list[_FeishuRecord] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            payload = self._request(
                "GET",
                f"open-apis/bitable/v1/apps/{token}/tables/{self._config.table_id}/records",
                params=params,
            )
            data = payload.get("data")
            if not isinstance(data, dict):
                raise FeishuAPIError("飞书记录响应缺少 data", api_code=0)
            raw_items = data.get("items", [])
            if not isinstance(raw_items, list):
                raise FeishuAPIError("飞书记录响应 items 格式错误", api_code=0)
            records.extend(_parse_record(item) for item in raw_items)
            has_more = data.get("has_more") is True
            next_page_token = data.get("page_token")
            if not has_more:
                break
            if not isinstance(next_page_token, str) or not next_page_token:
                raise FeishuAPIError("飞书记录分页响应缺少 page_token", api_code=0)
            page_token = next_page_token
        return tuple(records)

    def preflight(self, rows: Sequence[Mapping[str, object]]) -> FeishuPreparedSync:
        """读取字段和已有记录，生成不会清空其他字段的写入计划。"""

        app_token = self.resolve_app_token()
        fields = self.list_fields(app_token)
        mapping = resolve_field_mapping(
            fields,
            aliases={**DEFAULT_FIELD_ALIASES, **self._config.field_aliases},
        )
        missing_required = [
            logical for logical in self._upsert_key_fields if logical not in mapping.resolved
        ]
        if missing_required:
            raise FeishuSyncError("飞书缺少 Upsert 必需字段: " + ", ".join(missing_required))
        existing_records = self.list_records(app_token)
        existing_by_key: dict[tuple[str, ...], _FeishuRecord] = {}
        for record in existing_records:
            key = _record_key(record, mapping, self._upsert_key_fields)
            if key is None:
                continue
            if key in existing_by_key:
                raise FeishuSyncError(
                    "飞书已有记录存在重复的 "
                    + " + ".join(self._upsert_key_fields)
                    + "，已停止写入"
                )
            existing_by_key[key] = record

        updates: list[_FeishuUpdate] = []
        creates: list[Mapping[str, object]] = []
        selected_keys: list[tuple[str, ...]] = []
        expected_fields: dict[tuple[str, ...], Mapping[str, object]] = {}
        seen_input_keys: set[tuple[str, ...]] = set()
        for row in rows:
            key = _row_key(row, self._upsert_key_fields)
            if key is None:
                raise FeishuSyncError(
                    "待同步结果缺少 " + " + ".join(self._upsert_key_fields)
                )
            if key in seen_input_keys:
                raise FeishuSyncError(
                    "待同步结果存在重复的 " + " + ".join(self._upsert_key_fields)
                )
            seen_input_keys.add(key)
            fields_payload = _row_fields(row, mapping)
            for logical in self._upsert_key_fields:
                actual = mapping.resolved[logical].name
                if actual not in fields_payload:
                    raise FeishuSyncError(f"关键字段无法转换为飞书类型: {logical}")
            selected_keys.append(key)
            expected_fields[key] = fields_payload
            existing = existing_by_key.get(key)
            if existing is None:
                creates.append(fields_payload)
            else:
                updates.append(
                    _FeishuUpdate(
                        record_id=existing.record_id,
                        key=key,
                        fields=fields_payload,
                    )
                )

        return FeishuPreparedSync(
            app_token=app_token,
            field_mapping=mapping,
            existing_records=existing_records,
            updates=tuple(updates),
            creates=tuple(creates),
            selected_keys=tuple(selected_keys),
            expected_fields=expected_fields,
        )

    def apply(self, prepared: FeishuPreparedSync) -> FeishuSyncSummary:
        """执行计划，再重新读取记录验证本次所有 Upsert 键。"""

        for chunk in _chunks(prepared.updates, 500):
            self._request(
                "POST",
                f"open-apis/bitable/v1/apps/{prepared.app_token}/tables/{self._config.table_id}/records/batch_update",
                json_body={
                    "records": [
                        {"record_id": item.record_id, "fields": dict(item.fields)} for item in chunk
                    ]
                },
            )
        for chunk in _chunks(prepared.creates, 500):
            self._request(
                "POST",
                f"open-apis/bitable/v1/apps/{prepared.app_token}/tables/{self._config.table_id}/records/batch_create",
                json_body={"records": [{"fields": dict(fields)} for fields in chunk]},
            )

        verification_records = self.list_records(prepared.app_token)
        verified_by_key: dict[tuple[str, ...], _FeishuRecord] = {}
        verification_errors: list[str] = []
        for record in verification_records:
            key = _record_key(record, prepared.field_mapping, self._upsert_key_fields)
            if key is None:
                continue
            if key in verified_by_key:
                verification_errors.append("回读后存在重复 Upsert 键")
            verified_by_key[key] = record
        verified_count = 0
        for key in prepared.selected_keys:
            verified_record = verified_by_key.get(key)
            if verified_record is None:
                verification_errors.append("回读缺少 " + "/".join(key))
            else:
                mismatches = [
                    field_name
                    for field_name, expected in prepared.expected_fields[key].items()
                    if not _field_values_equal(verified_record.fields.get(field_name), expected)
                ]
                if mismatches:
                    verification_errors.extend(
                        f"回读字段不一致 {'/'.join(key)}/{field_name}"
                        for field_name in mismatches
                    )
                else:
                    verified_count += 1
        return FeishuSyncSummary(
            created_count=len(prepared.creates),
            updated_count=len(prepared.updates),
            verified_count=verified_count,
            verification_errors=tuple(dict.fromkeys(verification_errors)),
            field_mapping=prepared.field_mapping,
        )

    def sync(
        self,
        rows: Sequence[Mapping[str, object]],
    ) -> tuple[FeishuPreparedSync, FeishuSyncSummary]:
        """执行写入前预检、Upsert 和回读核验。"""

        prepared = self.preflight(rows)
        return prepared, self.apply(prepared)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        for auth_round in range(2):
            token = self._tenant_access_token()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            try:
                return self._request_with_retry(
                    method,
                    path,
                    headers=headers,
                    params=params,
                    json_body=json_body,
                    allow_auth_retry=auth_round == 0,
                )
            except FeishuAPIError as exc:
                if exc.status_code == 401 and auth_round == 0:
                    self._tenant_token = None
                    self._tenant_token_expires_at = 0.0
                    continue
                raise
        raise FeishuAPIError("飞书认证重试状态异常")

    def _tenant_access_token(self) -> str:
        if self._tenant_token is not None and monotonic() < self._tenant_token_expires_at:
            return self._tenant_token
        payload = self._request_with_retry(
            "POST",
            "open-apis/auth/v3/tenant_access_token/internal",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            params=None,
            json_body={"app_id": self._config.app_id, "app_secret": self._app_secret},
            allow_auth_retry=False,
        )
        token = payload.get("tenant_access_token")
        expire = payload.get("expire")
        if not isinstance(token, str) or not token.strip():
            raise FeishuAPIError("飞书 Token 响应缺少 tenant_access_token", api_code=0)
        expiry_seconds = expire if isinstance(expire, int) and expire > 0 else 7200
        self._tenant_token = token
        self._tenant_token_expires_at = monotonic() + max(expiry_seconds - 60, 1)
        return token

    def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, str | int | float | bool | None] | None,
        json_body: Mapping[str, object] | None,
        allow_auth_retry: bool,
    ) -> dict[str, object]:
        del allow_auth_retry
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    headers=headers,
                    json=json_body,
                )
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_retries:
                    raise FeishuAPIError("飞书网络请求失败", retryable=True) from exc
                self._sleep(_retry_delay(attempt))
                continue
            if response.status_code not in range(200, 300):
                retryable = response.status_code in _RETRYABLE_STATUS_CODES
                if retryable and attempt < self._config.max_retries:
                    self._sleep(_retry_delay(attempt, response.headers.get("Retry-After")))
                    continue
                raise FeishuAPIError(
                    f"飞书请求失败: HTTP {response.status_code}",
                    status_code=response.status_code,
                    retryable=retryable,
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise FeishuAPIError(
                    "飞书响应不是合法 JSON",
                    status_code=response.status_code,
                ) from exc
            if not isinstance(payload, dict):
                raise FeishuAPIError(
                    "飞书响应根节点不是 JSON object",
                    status_code=response.status_code,
                )
            code = payload.get("code")
            if isinstance(code, bool) or (code is not None and not isinstance(code, int)):
                raise FeishuAPIError("飞书响应 code 类型错误", status_code=response.status_code)
            if isinstance(code, int) and code != 0:
                if code in {1254290, 1254291} and attempt < self._config.max_retries:
                    self._sleep(_retry_delay(attempt))
                    continue
                raise FeishuAPIError(
                    "飞书业务请求失败",
                    status_code=response.status_code,
                    api_code=code,
                    retryable=code in {1254290, 1254291},
                )
            return {str(key): value for key, value in payload.items()}
        raise FeishuAPIError("飞书请求重试状态异常")


def resolve_field_mapping(
    fields: Sequence[FeishuField],
    *,
    aliases: Mapping[str, Sequence[str]] | None = None,
) -> FeishuFieldMapping:
    """根据字段名称和类型解析可安全写入的字段。"""

    alias_map = aliases or DEFAULT_FIELD_ALIASES
    by_name = {field.name: field for field in fields}
    resolved: dict[str, FeishuField] = {}
    unavailable: dict[str, str] = {}
    for logical, names in alias_map.items():
        field = next((by_name[name] for name in names if name in by_name), None)
        if field is None:
            unavailable[logical] = "field_not_found"
            continue
        if not _field_type_supported(field.field_type):
            unavailable[logical] = f"unsupported_field_type:{field.field_type}"
            continue
        resolved[logical] = field
    return FeishuFieldMapping(resolved=resolved, unavailable=unavailable)


def _field_type_supported(field_type: int) -> bool:
    return field_type in (
        _FIELD_TYPES_TEXT
        | _FIELD_TYPES_NUMBER
        | _FIELD_TYPES_SINGLE_SELECT
        | _FIELD_TYPES_MULTI_SELECT
        | _FIELD_TYPES_DATETIME
        | _FIELD_TYPES_URL
    )


def _parse_field(value: object) -> FeishuField:
    if not isinstance(value, dict):
        raise FeishuAPIError("飞书字段项不是 object", api_code=0)
    field_id = value.get("field_id")
    name = value.get("field_name")
    field_type = value.get("type")
    if not isinstance(field_id, str) or not field_id:
        raise FeishuAPIError("飞书字段项缺少标识", api_code=0)
    if not isinstance(name, str) or not name:
        raise FeishuAPIError("飞书字段项缺少标识", api_code=0)
    if isinstance(field_type, bool) or not isinstance(field_type, int):
        raise FeishuAPIError("飞书字段项 type 类型错误", api_code=0)
    property_value = value.get("property")
    raw_options = property_value.get("options", []) if isinstance(property_value, dict) else []
    field_property = (
        {str(key): item for key, item in property_value.items()}
        if isinstance(property_value, dict)
        else None
    )
    options: list[str] = []
    if isinstance(raw_options, list):
        for raw_option in raw_options:
            if isinstance(raw_option, dict) and isinstance(raw_option.get("name"), str):
                options.append(raw_option["name"])
    return FeishuField(
        field_id=field_id,
        name=name,
        field_type=field_type,
        options=tuple(options),
        field_property=field_property,
    )


def _table_field_definition(field: FeishuField) -> dict[str, object]:
    """生成创建数据表所需的字段定义，不复用旧字段 ID。"""

    definition: dict[str, object] = {
        "field_name": field.name,
        "type": field.field_type,
    }
    if field.field_type in _FIELD_TYPES_SINGLE_SELECT | _FIELD_TYPES_MULTI_SELECT:
        options: list[dict[str, object]] = []
        raw_options = field.field_property.get("options", []) if field.field_property else []
        if isinstance(raw_options, list):
            for raw_option in raw_options:
                if not isinstance(raw_option, dict) or not isinstance(raw_option.get("name"), str):
                    continue
                option: dict[str, object] = {"name": raw_option["name"]}
                color = raw_option.get("color")
                if isinstance(color, int) and not isinstance(color, bool):
                    option["color"] = color
                options.append(option)
        if not options:
            options = [{"name": option} for option in field.options]
        if options:
            definition["property"] = {"options": options}
    return definition


def _parse_record(value: object) -> _FeishuRecord:
    if not isinstance(value, dict):
        raise FeishuAPIError("飞书记录项不是 object", api_code=0)
    record_id = value.get("record_id")
    fields = value.get("fields", {})
    if not isinstance(record_id, str) or not record_id:
        raise FeishuAPIError("飞书记录项缺少 record_id", api_code=0)
    if not isinstance(fields, dict):
        raise FeishuAPIError("飞书记录 fields 类型错误", api_code=0)
    return _FeishuRecord(
        record_id=record_id,
        fields={str(key): item for key, item in fields.items()},
    )


def _row_key(
    row: Mapping[str, object],
    key_fields: Sequence[str],
) -> tuple[str, ...] | None:
    values = tuple(_key_value(field, row.get(field)) for field in key_fields)
    return values if all(values) else None


def _record_key(
    record: _FeishuRecord,
    mapping: FeishuFieldMapping,
    key_fields: Sequence[str],
) -> tuple[str, ...] | None:
    values = tuple(
        _key_value(field, record.fields.get(mapping.resolved[field].name))
        for field in key_fields
    )
    return values if all(values) else None


def _key_value(field: str, value: object) -> str:
    """提取幂等键文本；目标表的内容/连接字段优先使用其中的 URL。"""

    text = _value_text(value)
    if field == "声音内容/连接":
        match = re.search(r"https?://[^\s]+", text)
        if match:
            return match.group(0).rstrip("，。；、,.;:：）)]}>")
    return text


def _row_fields(row: Mapping[str, object], mapping: FeishuFieldMapping) -> dict[str, object]:
    converted: dict[str, object] = {}
    for logical, field in mapping.resolved.items():
        value = row.get(logical)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        converted_value = _convert_field_value(field, value)
        if converted_value is not None:
            converted[field.name] = converted_value
    return converted


def _convert_field_value(field: FeishuField, value: object) -> object | None:
    if field.field_type in _FIELD_TYPES_TEXT:
        return _value_text(value)
    if field.field_type in _FIELD_TYPES_URL:
        text = _value_text(value)
        if not text.startswith(("http://", "https://")):
            return None
        return {"link": text, "text": text}
    if field.field_type in _FIELD_TYPES_NUMBER:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float, Decimal)):
            return value
        try:
            return int(str(value).strip())
        except ValueError:
            try:
                return float(str(value).strip())
            except ValueError:
                return None
    if field.field_type in _FIELD_TYPES_SINGLE_SELECT:
        text = _value_text(value)
        return text if text in field.options else None
    if field.field_type in _FIELD_TYPES_MULTI_SELECT:
        if isinstance(value, (list, tuple)):
            values = [_value_text(item) for item in value]
        else:
            values = [_value_text(value)]
        if not values or any(item not in field.options for item in values):
            return None
        return values
    if field.field_type in _FIELD_TYPES_DATETIME:
        return _datetime_milliseconds(value)
    return None


def _datetime_milliseconds(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        text = _value_text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed = datetime.strptime(text, "%Y-%m-%d")
                except ValueError:
                    return None
    if parsed.tzinfo is None:
        from zoneinfo import ZoneInfo

        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return int(parsed.astimezone(UTC).timestamp() * 1000)


def _value_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("text", "link", "name", "value"):
            if key in value:
                return _value_text(value[key])
        return ""
    if isinstance(value, list):
        return ",".join(_value_text(item) for item in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _field_values_equal(actual: object, expected: object) -> bool:
    if isinstance(expected, list):
        actual_values = actual if isinstance(actual, list) else [actual]
        return sorted(_value_text(item) for item in actual_values) == sorted(
            _value_text(item) for item in expected
        )
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            _value_text(actual.get(key)) == _value_text(value)
            for key, value in expected.items()
        )
    if isinstance(expected, (int, float, Decimal)) and not isinstance(expected, bool):
        if isinstance(actual, (int, float, Decimal)) and not isinstance(actual, bool):
            return float(actual) == float(expected)
    return _value_text(actual) == _value_text(expected)


def _chunks(values: Sequence[Any], size: int) -> tuple[Sequence[Any], ...]:
    return tuple(values[start : start + size] for start in range(0, len(values), size))


def _retry_delay(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            retry_after_seconds = float(retry_after)
            return min(max(retry_after_seconds, 0.0), 30.0)
        except ValueError:
            pass
    return min(30.0, 0.5 * float(2**attempt))


__all__ = [
    "DEFAULT_FIELD_ALIASES",
    "DEFAULT_UPSERT_KEY_FIELDS",
    "FeishuAPIError",
    "FeishuBitableClient",
    "FeishuField",
    "FeishuFieldMapping",
    "FeishuPreparedSync",
    "FeishuTableInfo",
    "FeishuSyncError",
    "FeishuSyncSummary",
    "resolve_field_mapping",
]
