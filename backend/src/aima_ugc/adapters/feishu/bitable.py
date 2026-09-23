"""飞书 Wiki 多维表读取、字段映射与 Upsert Adapter。"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any

import httpx

from aima_ugc.platform.reporting.representative_section import split_representative_labels

from .config import FeishuConfig

_FIELD_TYPES_TEXT = frozenset({1})
_FIELD_TYPES_NUMBER = frozenset({2})
_FIELD_TYPES_SINGLE_SELECT = frozenset({3})
_FIELD_TYPES_MULTI_SELECT = frozenset({4})
_FIELD_TYPES_DATETIME = frozenset({5})
_FIELD_TYPES_URL = frozenset({15})
_FIELD_TYPES_ATTACHMENT = frozenset({17})
_TABLE_CLONE_FIELD_TYPES = frozenset({1, 2, 3, 4, 5, 7, 11, 13, 15, 17})
_TABLE_FIELD_ORDER: tuple[str, ...] = (
    "声音内容/连接",
    "来源",
    "用户情绪",
    "声音截图",
    "典型评论示例",
    "处理进展",
    "进展描述",
    "发布时间",
    "一级标签",
    "二级标签",
    "优先级",
    "处理人",
    "处理人.直属上级",
    "处理建议",
    "实际完成时间",
    "期望完成时间",
)
_TABLE_FIELD_ORDER_INDEX = {name: index for index, name in enumerate(_TABLE_FIELD_ORDER)}
_REQUIRED_TEMPLATE_SELECT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "一级标签",
        (
            "品牌评价",
            "外观设计",
            "骑行性能",
            "电池、续航与充电",
            "智能化与电子功能",
            "耐用性与质量",
            "价格与价值",
            "销售与购买体验",
            "售后服务",
            "无法分类",
        ),
    ),
    (
        "二级标签",
        (
            "口碑与信任",
            "形象与定位",
            "性价比与溢价",
            "推荐与购买意愿",
            "偏好与转换",
            "营销与传播",
            "整体造型与颜值",
            "颜色与配色",
            "外观风格与适配人群",
            "动力与加速表现",
            "操控与稳定性",
            "制动与刹车表现",
            "舒适性",
            "实际续航表现",
            "电池寿命与衰减",
            "充电体验",
            "电池安全",
            "App与智能互联",
            "智能解锁与启动",
            "仪表与信息显示",
            "智能辅助功能",
            "系统稳定性与功能体验",
            "做工与装配质量",
            "长期使用与寿命表现",
            "故障问题与稳定性",
            "购车价格与配置价值",
            "性价比与价格竞争力",
            "购车优惠与促销政策",
            "使用与养护成本",
            "门店与渠道便利性",
            "销售服务与购车咨询",
            "下单与交易流程",
            "交付与提车体验",
            "售后网点与服务便利性",
            "客服与服务态度",
            "维修处理效率与质量",
            "保修政策与执行",
            "配件供应与维修成本",
            "投诉处理与用户权益",
            "无法判断",
        ),
    ),
    ("用户情绪", ("正面", "负面")),
    ("处理进展", ("待处理",)),
)
_REQUIRED_TEMPLATE_MULTI_SELECT_FIELD_NAMES = frozenset({"一级标签", "二级标签"})
_EMBEDDED_DEFAULT_FIELD_NAMES = frozenset({"Multiline", "Multiline 1", "Single option"})
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
    "声音截图": ("声音截图",),
    "典型评论示例": ("典型评论示例",),
    "进展描述": ("进展描述",),
    "优先级": ("优先级",),
    "处理人": ("处理人",),
    "处理人.直属上级": ("处理人.直属上级",),
    "来源": ("来源",),
    "一级标签": ("一级标签",),
    "二级标签": ("二级标签",),
    "用户情绪": ("用户情绪",),
    "处理建议": ("处理建议",),
    "处理进展": ("处理进展",),
    "实际完成时间": ("实际完成时间",),
    "期望完成时间": ("期望完成时间",),
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
        http_method: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.api_code = api_code
        self.retryable = retryable
        self.http_method = http_method
        self.endpoint = endpoint


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
    is_primary: bool = False


@dataclass(frozen=True, slots=True)
class FeishuTableInfo:
    """新建多维表数据表的身份信息。"""

    table_id: str
    name: str
    skipped_fields: tuple[str, ...] = ()
    app_token: str | None = None
    bitable_block_token: str | None = None
    url: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "table_id": self.table_id,
            "name": self.name,
            "skipped_fields": list(self.skipped_fields),
        }
        if self.app_token is not None:
            payload["app_token"] = self.app_token
        if self.bitable_block_token is not None:
            payload["bitable_block_token"] = self.bitable_block_token
        if self.url is not None:
            payload["url"] = self.url
        return payload


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
    last_modified_time: int = 0


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
    target_app_token: str | None = None
    target_bitable_block_token: str | None = None
    target_table_url: str | None = None
    mirror_app_token: str | None = None
    mirror_table_id: str | None = None
    mirror_document_token: str | None = None
    mirror_document_url: str | None = None

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
        if self.target_app_token is not None:
            payload["target_app_token"] = self.target_app_token
        if self.target_bitable_block_token is not None:
            payload["target_bitable_block_token"] = self.target_bitable_block_token
        if self.target_table_url is not None:
            payload["target_table_url"] = self.target_table_url
        if self.mirror_app_token is not None:
            payload["mirror_app_token"] = self.mirror_app_token
        if self.mirror_table_id is not None:
            payload["mirror_table_id"] = self.mirror_table_id
        if self.mirror_document_token is not None:
            payload["mirror_document_token"] = self.mirror_document_token
        if self.mirror_document_url is not None:
            payload["mirror_document_url"] = self.mirror_document_url
        return payload


@dataclass(frozen=True, slots=True)
class FeishuMirrorSyncSummary:
    """一次独立 Base 与文档内嵌 Base 的双向对账结果。"""

    external_created_count: int
    external_updated_count: int
    external_deleted_count: int
    embedded_created_count: int
    embedded_updated_count: int
    embedded_deleted_count: int
    verified_count: int
    known_key_hashes: tuple[str, ...]
    excluded_fields: tuple[str, ...] = ()


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
        self._uploaded_attachment_tokens: dict[tuple[str, int, int], str] = {}

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
        field_definitions, skipped_fields = _target_field_definitions(
            source_fields,
            aliases={**DEFAULT_FIELD_ALIASES, **self._config.field_aliases},
            upsert_key_fields=self._upsert_key_fields,
        )

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
            app_token=app_token,
            # Docx Bitable block 的 token 是 app_token_table_id 组合；这与
            # 飞书文档块 API 返回的 bitable.token 格式一致。table_id 同时
            # 仍用于本轮数据表的字段/记录写入。
            bitable_block_token=f"{app_token}_{table_id.strip()}",
            url=f"https://feishu.cn/base/{app_token}?table={table_id.strip()}",
        )

    def configure_embedded_table_from_current(
        self,
        *,
        app_token: str,
        table_id: str,
        name: str,
    ) -> FeishuTableInfo:
        """把文档内新建 Bitable 的默认表安全转换为当前模板结构。"""

        target_app_token = app_token.strip()
        target_table_id = table_id.strip()
        table_name = name.strip()
        if not target_app_token or not target_table_id:
            raise ValueError("飞书内嵌多维表 token 不完整")
        if not table_name:
            raise ValueError("飞书内嵌多维表名称不能为空")

        source_app_token = self.resolve_app_token()
        source_fields = self.list_fields(source_app_token)
        field_definitions, skipped_fields = _target_field_definitions(
            source_fields,
            aliases={**DEFAULT_FIELD_ALIASES, **self._config.field_aliases},
            upsert_key_fields=self._upsert_key_fields,
        )
        desired_names = {str(item["field_name"]) for item in field_definitions}
        target_fields = self.list_fields(target_app_token, table_id=target_table_id)
        target_records = self.list_records(target_app_token, table_id=target_table_id)
        existing_names = {field.name for field in target_fields}

        if target_records:
            nonempty_records = tuple(
                record for record in target_records if not _record_is_blank(record)
            )
            if nonempty_records:
                missing = desired_names - existing_names
                if missing:
                    raise FeishuSyncError(
                        "飞书内嵌多维表已有记录且缺少模板字段，已停止修改: "
                        + ", ".join(sorted(missing))
                    )
                return FeishuTableInfo(
                    table_id=target_table_id,
                    name=table_name,
                    skipped_fields=skipped_fields,
                    app_token=target_app_token,
                    bitable_block_token=f"{target_app_token}_{target_table_id}",
                    # 文档内嵌 Base 没有可独立打开的 /base URL。
                    url=None,
                )
            # Docx 创建的原生 Bitable 默认带三条空记录。它们不是用户数据，
            # 在配置字段前精确删除，避免最终表格顶部残留空白行。
            for chunk in _chunks(target_records, 500):
                self._request(
                    "POST",
                    (
                        f"open-apis/bitable/v1/apps/{target_app_token}/tables/"
                        f"{target_table_id}/records/batch_delete"
                    ),
                    json_body={"records": [record.record_id for record in chunk]},
                )

        unexpected_fields = existing_names - desired_names - _EMBEDDED_DEFAULT_FIELD_NAMES
        if unexpected_fields:
            raise FeishuSyncError(
                "飞书内嵌多维表包含非默认字段，已停止覆盖: "
                + ", ".join(sorted(unexpected_fields))
            )
        primary = next((field for field in target_fields if field.is_primary), None)
        if primary is None:
            raise FeishuSyncError("飞书内嵌多维表缺少主字段，已停止修改")

        primary_definition = field_definitions[0]
        self._request(
            "PUT",
            (
                f"open-apis/bitable/v1/apps/{target_app_token}/tables/"
                f"{target_table_id}/fields/{primary.field_id}"
            ),
            json_body=primary_definition,
        )
        refreshed = self.list_fields(target_app_token, table_id=target_table_id)
        for field in refreshed:
            if (
                not field.is_primary
                and field.name in _EMBEDDED_DEFAULT_FIELD_NAMES
                and field.name not in desired_names
            ):
                self._request(
                    "DELETE",
                    (
                        f"open-apis/bitable/v1/apps/{target_app_token}/tables/"
                        f"{target_table_id}/fields/{field.field_id}"
                    ),
                )

        refreshed = self.list_fields(target_app_token, table_id=target_table_id)
        by_name = {field.name: field for field in refreshed}
        for definition in field_definitions[1:]:
            field_name = str(definition["field_name"])
            existing = by_name.get(field_name)
            if existing is None:
                self._request(
                    "POST",
                    (
                        f"open-apis/bitable/v1/apps/{target_app_token}/tables/"
                        f"{target_table_id}/fields"
                    ),
                    json_body=definition,
                )
            else:
                self._request(
                    "PUT",
                    (
                        f"open-apis/bitable/v1/apps/{target_app_token}/tables/"
                        f"{target_table_id}/fields/{existing.field_id}"
                    ),
                    json_body=definition,
                )

        verified_fields = self.list_fields(target_app_token, table_id=target_table_id)
        verified_names = {field.name for field in verified_fields}
        missing = desired_names - verified_names
        if missing:
            raise FeishuSyncError(
                "飞书内嵌多维表字段创建后回读缺失: " + ", ".join(sorted(missing))
            )
        return FeishuTableInfo(
            table_id=target_table_id,
            name=table_name,
            skipped_fields=skipped_fields,
            app_token=target_app_token,
            bitable_block_token=f"{target_app_token}_{target_table_id}",
            # 文档内嵌 Base 的用户入口是承载它的 Docx 文档。
            url=None,
        )

    def list_fields(
        self,
        app_token: str | None = None,
        *,
        table_id: str | None = None,
    ) -> tuple[FeishuField, ...]:
        """分页读取多维表字段定义。"""

        token = app_token or self.resolve_app_token()
        target_table_id = table_id or self._config.table_id
        fields: list[FeishuField] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            payload = self._request(
                "GET",
                f"open-apis/bitable/v1/apps/{token}/tables/{target_table_id}/fields",
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

    def list_records(
        self,
        app_token: str | None = None,
        *,
        table_id: str | None = None,
        automatic_fields: bool = False,
    ) -> tuple[_FeishuRecord, ...]:
        """分页读取多维表记录。"""

        token = app_token or self.resolve_app_token()
        target_table_id = table_id or self._config.table_id
        records: list[_FeishuRecord] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {"page_size": 500}
            if automatic_fields:
                params["automatic_fields"] = "true"
            if page_token:
                params["page_token"] = page_token
            payload = self._request(
                "GET",
                f"open-apis/bitable/v1/apps/{token}/tables/{target_table_id}/records",
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

    def mirror_records_bidirectionally(
        self,
        *,
        external_app_token: str,
        external_table_id: str,
        embedded_app_token: str,
        embedded_table_id: str,
        known_key_hashes: Sequence[str] = (),
        last_synced_at_ms: int = 0,
    ) -> FeishuMirrorSyncSummary:
        """按主字段双向同步两张同构表，冲突时以最后修改时间较新的一侧为准。

        飞书附件 token 绑定所属 Base，不能直接跨 Base 写入。因此附件在报告生成时
        分别上传到两侧，持续镜像只处理其余业务字段，避免产生失效附件 token。
        """

        external_fields = self.list_fields(
            external_app_token,
            table_id=external_table_id,
        )
        embedded_fields = self.list_fields(
            embedded_app_token,
            table_id=embedded_table_id,
        )
        external_by_name = {field.name: field for field in external_fields}
        embedded_by_name = {field.name: field for field in embedded_fields}
        external_primary = next((field for field in external_fields if field.is_primary), None)
        embedded_primary = next((field for field in embedded_fields if field.is_primary), None)
        if external_primary is None or embedded_primary is None:
            raise FeishuSyncError("双向镜像表缺少主字段")
        if external_primary.name != embedded_primary.name:
            raise FeishuSyncError("双向镜像表主字段名称不一致")

        shared_names = set(external_by_name) & set(embedded_by_name)
        incompatible = sorted(
            name
            for name in shared_names
            if external_by_name[name].field_type != embedded_by_name[name].field_type
        )
        if incompatible:
            raise FeishuSyncError("双向镜像表字段类型不一致: " + ", ".join(incompatible))
        excluded_fields = tuple(
            sorted(
                name
                for name in shared_names
                if external_by_name[name].field_type in _FIELD_TYPES_ATTACHMENT
            )
        )
        syncable_names = tuple(
            sorted(
                name
                for name in shared_names
                if external_by_name[name].field_type not in _FIELD_TYPES_ATTACHMENT
            )
        )
        if external_primary.name not in syncable_names:
            raise FeishuSyncError("双向镜像表主字段不可同步")

        external_records = self.list_records(
            external_app_token,
            table_id=external_table_id,
            automatic_fields=True,
        )
        embedded_records = self.list_records(
            embedded_app_token,
            table_id=embedded_table_id,
            automatic_fields=True,
        )
        external_by_key = _mirror_records_by_key(external_records, external_primary.name)
        embedded_by_key = _mirror_records_by_key(embedded_records, embedded_primary.name)
        previous_keys = set(known_key_hashes)
        next_keys: set[str] = set()

        external_updates: list[dict[str, object]] = []
        embedded_updates: list[dict[str, object]] = []
        external_creates: list[dict[str, object]] = []
        embedded_creates: list[dict[str, object]] = []
        external_deletes: list[str] = []
        embedded_deletes: list[str] = []

        for key in sorted(set(external_by_key) | set(embedded_by_key)):
            external = external_by_key.get(key)
            embedded = embedded_by_key.get(key)
            key_hash = _mirror_key_hash(key)
            if external is not None and embedded is not None:
                differences = tuple(
                    name
                    for name in syncable_names
                    if not _field_values_equal(
                        external.fields.get(name),
                        embedded.fields.get(name),
                    )
                )
                if differences:
                    if external.last_modified_time >= embedded.last_modified_time:
                        embedded_updates.append(
                            {
                                "record_id": embedded.record_id,
                                "fields": {
                                    name: external.fields.get(name) for name in differences
                                },
                            }
                        )
                    else:
                        external_updates.append(
                            {
                                "record_id": external.record_id,
                                "fields": {
                                    name: embedded.fields.get(name) for name in differences
                                },
                            }
                        )
                next_keys.add(key_hash)
                continue

            present = external if external is not None else embedded
            assert present is not None
            if key_hash in previous_keys and present.last_modified_time <= last_synced_at_ms:
                if external is not None:
                    external_deletes.append(external.record_id)
                else:
                    assert embedded is not None
                    embedded_deletes.append(embedded.record_id)
                continue

            fields = {
                name: present.fields.get(name)
                for name in syncable_names
                if present.fields.get(name) is not None
            }
            if external is None:
                external_creates.append({"fields": fields})
            else:
                embedded_creates.append({"fields": fields})
            next_keys.add(key_hash)

        self._apply_mirror_mutations(
            app_token=external_app_token,
            table_id=external_table_id,
            creates=external_creates,
            updates=external_updates,
            deletes=external_deletes,
        )
        self._apply_mirror_mutations(
            app_token=embedded_app_token,
            table_id=embedded_table_id,
            creates=embedded_creates,
            updates=embedded_updates,
            deletes=embedded_deletes,
        )

        verified_external = _mirror_records_by_key(
            self.list_records(external_app_token, table_id=external_table_id),
            external_primary.name,
        )
        verified_embedded = _mirror_records_by_key(
            self.list_records(embedded_app_token, table_id=embedded_table_id),
            embedded_primary.name,
        )
        if set(verified_external) != set(verified_embedded):
            raise FeishuSyncError("双向镜像回读后的记录集合不一致")
        mismatched = [
            key
            for key in verified_external
            if any(
                not _field_values_equal(
                    verified_external[key].fields.get(name),
                    verified_embedded[key].fields.get(name),
                )
                for name in syncable_names
            )
        ]
        if mismatched:
            raise FeishuSyncError(f"双向镜像回读仍有 {len(mismatched)} 条记录不一致")
        verified_hashes = tuple(sorted(_mirror_key_hash(key) for key in verified_external))
        return FeishuMirrorSyncSummary(
            external_created_count=len(external_creates),
            external_updated_count=len(external_updates),
            external_deleted_count=len(external_deletes),
            embedded_created_count=len(embedded_creates),
            embedded_updated_count=len(embedded_updates),
            embedded_deleted_count=len(embedded_deletes),
            verified_count=len(verified_external),
            known_key_hashes=verified_hashes,
            excluded_fields=excluded_fields,
        )

    def _apply_mirror_mutations(
        self,
        *,
        app_token: str,
        table_id: str,
        creates: Sequence[Mapping[str, object]],
        updates: Sequence[Mapping[str, object]],
        deletes: Sequence[str],
    ) -> None:
        for chunk in _chunks(creates, 500):
            self._request(
                "POST",
                f"open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                json_body={"records": [dict(item) for item in chunk]},
            )
        for chunk in _chunks(updates, 500):
            self._request(
                "POST",
                f"open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
                json_body={"records": [dict(item) for item in chunk]},
            )
        for chunk in _chunks(deletes, 500):
            self._request(
                "POST",
                f"open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
                json_body={"records": list(chunk)},
            )

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
                    "飞书已有记录存在重复的 " + " + ".join(self._upsert_key_fields) + "，已停止写入"
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
                raise FeishuSyncError("待同步结果缺少 " + " + ".join(self._upsert_key_fields))
            if key in seen_input_keys:
                raise FeishuSyncError("待同步结果存在重复的 " + " + ".join(self._upsert_key_fields))
            seen_input_keys.add(key)
            fields_payload = _row_fields(
                row,
                mapping,
                upload_attachment=self.upload_bitable_attachment,
            )
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
                        f"回读字段不一致 {'/'.join(key)}/{field_name}" for field_name in mismatches
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

    def upload_bitable_attachment(self, path: Path) -> str:
        """上传一张本地截图，返回可写入附件字段的 file_token。"""

        attachment_path = Path(path)
        if not attachment_path.is_file():
            raise FeishuSyncError(f"飞书附件文件不存在: {attachment_path.name}")
        stat = attachment_path.stat()
        cache_key = (str(attachment_path.resolve()), stat.st_size, stat.st_mtime_ns)
        cached = self._uploaded_attachment_tokens.get(cache_key)
        if cached is not None:
            return cached
        if stat.st_size <= 0:
            raise FeishuSyncError(f"飞书附件文件为空: {attachment_path.name}")
        if stat.st_size > 20 * 1024 * 1024:
            raise FeishuSyncError(f"飞书附件文件超过 20 MB: {attachment_path.name}")
        content = attachment_path.read_bytes()
        app_token = self.resolve_app_token()
        payload = self._request_multipart(
            "POST",
            "open-apis/drive/v1/medias/upload_all",
            data={
                "file_name": attachment_path.name,
                "parent_type": "bitable_file",
                "parent_node": app_token,
                "size": str(len(content)),
            },
            files={
                "file": (
                    attachment_path.name,
                    content,
                    _attachment_content_type(attachment_path),
                )
            },
        )
        data = payload.get("data")
        file_token = data.get("file_token") if isinstance(data, dict) else None
        if not isinstance(file_token, str) or not file_token.strip():
            raise FeishuAPIError("飞书附件上传响应缺少 file_token", api_code=0)
        self._uploaded_attachment_tokens[cache_key] = file_token.strip()
        return file_token.strip()

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

    def _request_multipart(
        self,
        method: str,
        path: str,
        *,
        data: Mapping[str, str],
        files: Mapping[str, object],
    ) -> dict[str, object]:
        """执行需要 multipart/form-data 的飞书请求，并复用认证重试边界。"""

        for auth_round in range(2):
            token = self._tenant_access_token()
            try:
                return self._request_with_retry(
                    method,
                    path,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    params=None,
                    json_body=None,
                    data=data,
                    files=files,
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
        data: Mapping[str, str] | None = None,
        files: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        del allow_auth_retry
        for attempt in range(self._config.max_retries + 1):
            try:
                request_kwargs: dict[str, object] = {
                    "params": params,
                    "headers": headers,
                }
                if json_body is not None:
                    request_kwargs["json"] = json_body
                if data is not None:
                    request_kwargs["data"] = data
                if files is not None:
                    request_kwargs["files"] = files
                response = self._client.request(method, path, **request_kwargs)
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_retries:
                    raise FeishuAPIError(
                        "飞书网络请求失败",
                        retryable=True,
                        http_method=method,
                        endpoint=path,
                    ) from exc
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
                    http_method=method,
                    endpoint=path,
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise FeishuAPIError(
                    "飞书响应不是合法 JSON",
                    status_code=response.status_code,
                    http_method=method,
                    endpoint=path,
                ) from exc
            if not isinstance(payload, dict):
                raise FeishuAPIError(
                    "飞书响应根节点不是 JSON object",
                    status_code=response.status_code,
                    http_method=method,
                    endpoint=path,
                )
            code = payload.get("code")
            if isinstance(code, bool) or (code is not None and not isinstance(code, int)):
                raise FeishuAPIError(
                    "飞书响应 code 类型错误",
                    status_code=response.status_code,
                    http_method=method,
                    endpoint=path,
                )
            if isinstance(code, int) and code != 0:
                if code in {1254290, 1254291} and attempt < self._config.max_retries:
                    self._sleep(_retry_delay(attempt))
                    continue
                raise FeishuAPIError(
                    "飞书业务请求失败",
                    status_code=response.status_code,
                    api_code=code,
                    retryable=code in {1254290, 1254291},
                    http_method=method,
                    endpoint=path,
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
        | _FIELD_TYPES_ATTACHMENT
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
        is_primary=value.get("is_primary") is True,
    )


def _target_field_definitions(
    source_fields: Sequence[FeishuField],
    *,
    aliases: Mapping[str, Sequence[str]],
    upsert_key_fields: Sequence[str],
) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    """从模板字段构造新表或文档内嵌表共用的确定性字段定义。"""

    source_mapping = resolve_field_mapping(source_fields, aliases=aliases)
    missing_keys = [
        logical for logical in upsert_key_fields if logical not in source_mapping.resolved
    ]
    if missing_keys:
        raise FeishuSyncError("模板数据表缺少必需字段: " + ", ".join(missing_keys))
    field_definitions = [
        _table_field_definition(field)
        for field in source_fields
        if field.field_type in _TABLE_CLONE_FIELD_TYPES
    ]
    existing_field_names = {field.name for field in source_fields}
    for field_name, options in _REQUIRED_TEMPLATE_SELECT_FIELDS:
        if field_name not in existing_field_names:
            field_definitions.append(
                {
                    "field_name": field_name,
                    "type": 4 if field_name in _REQUIRED_TEMPLATE_MULTI_SELECT_FIELD_NAMES else 3,
                    "property": {"options": [{"name": option} for option in options]},
                }
            )
    if "声音截图" not in existing_field_names:
        field_definitions.append({"field_name": "声音截图", "type": 17})
    field_definitions = _order_table_field_definitions(field_definitions)
    skipped_fields = tuple(
        field.name for field in source_fields if field.field_type not in _TABLE_CLONE_FIELD_TYPES
    )
    if skipped_fields:
        raise FeishuSyncError(
            "模板数据表存在无法复制的字段，已停止创建新表: " + ", ".join(skipped_fields)
        )
    if not field_definitions:
        raise FeishuSyncError("模板数据表没有可复制的字段")
    return field_definitions, skipped_fields


def _table_field_definition(field: FeishuField) -> dict[str, object]:
    """生成创建数据表所需的字段定义，不复用旧字段 ID。"""

    if field.name == "声音内容/连接":
        field_type = 15
    elif field.name == "声音截图":
        field_type = 17
    elif field.name in dict(_REQUIRED_TEMPLATE_SELECT_FIELDS):
        field_type = 4 if field.name in _REQUIRED_TEMPLATE_MULTI_SELECT_FIELD_NAMES else 3
    else:
        field_type = field.field_type
    definition: dict[str, object] = {
        "field_name": field.name,
        "type": field_type,
    }
    if field_type in _FIELD_TYPES_SINGLE_SELECT | _FIELD_TYPES_MULTI_SELECT:
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
        required_options = dict(_REQUIRED_TEMPLATE_SELECT_FIELDS).get(field.name, ())
        existing_options = {str(option["name"]) for option in options}
        options.extend(
            {"name": option} for option in required_options if option not in existing_options
        )
        if options:
            definition["property"] = {"options": options}
    return definition


def _order_table_field_definitions(
    definitions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """按报告使用的固定列顺序排列新表字段，未列出的模板字段置于末尾。"""

    indexed = list(enumerate(definitions))
    indexed.sort(
        key=lambda item: (
            _TABLE_FIELD_ORDER_INDEX.get(
                str(item[1].get("field_name", "")),
                len(_TABLE_FIELD_ORDER_INDEX),
            ),
            item[0],
        )
    )
    return [dict(definition) for _, definition in indexed]


def _attachment_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")


def _parse_record(value: object) -> _FeishuRecord:
    if not isinstance(value, dict):
        raise FeishuAPIError("飞书记录项不是 object", api_code=0)
    record_id = value.get("record_id")
    fields = value.get("fields", {})
    if not isinstance(record_id, str) or not record_id:
        raise FeishuAPIError("飞书记录项缺少 record_id", api_code=0)
    if not isinstance(fields, dict):
        raise FeishuAPIError("飞书记录 fields 类型错误", api_code=0)
    raw_modified_time = value.get("last_modified_time", 0)
    try:
        last_modified_time = int(raw_modified_time)
    except (TypeError, ValueError):
        last_modified_time = 0
    return _FeishuRecord(
        record_id=record_id,
        fields={str(key): item for key, item in fields.items()},
        last_modified_time=max(last_modified_time, 0),
    )


def _record_is_blank(record: _FeishuRecord) -> bool:
    """识别 Docx 新建内嵌表自动生成的空白记录，不把 0/false 当作空值。"""

    for value in record.fields.values():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, tuple, dict, set)) and not value:
            continue
        return False
    return True


def _mirror_records_by_key(
    records: Sequence[_FeishuRecord],
    primary_field_name: str,
) -> dict[str, _FeishuRecord]:
    indexed: dict[str, _FeishuRecord] = {}
    for record in records:
        key = _key_value("声音内容/连接", record.fields.get(primary_field_name))
        if not key:
            continue
        if key in indexed:
            raise FeishuSyncError("双向镜像表存在重复主字段，已停止同步")
        indexed[key] = record
    return indexed


def _mirror_key_hash(key: str) -> str:
    return sha256(key.encode("utf-8")).hexdigest()


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
        _key_value(field, record.fields.get(mapping.resolved[field].name)) for field in key_fields
    )
    return values if all(values) else None


def _key_value(field: str, value: object) -> str:
    """提取幂等键文本；目标表的内容/连接字段优先使用其中的 URL。"""

    if field == "声音内容/连接":
        url_value = value
        if isinstance(url_value, list) and len(url_value) == 1:
            url_value = url_value[0]
        if isinstance(url_value, Mapping):
            link = url_value.get("link")
            if isinstance(link, str) and link.strip():
                return link.strip().rstrip("，。；、,.;:：）)]}>")
    text = _value_text(value)
    if field == "声音内容/连接":
        match = re.search(r"https?://[^\s]+", text)
        if match:
            return match.group(0).rstrip("，。；、,.;:：）)]}>")
    return text


def _row_fields(
    row: Mapping[str, object],
    mapping: FeishuFieldMapping,
    *,
    upload_attachment: Callable[[Path], str] | None = None,
) -> dict[str, object]:
    converted: dict[str, object] = {}
    for logical, field in mapping.resolved.items():
        value = row.get(logical)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        converted_value = _convert_field_value(
            field,
            value,
            upload_attachment=upload_attachment,
        )
        if converted_value is not None:
            converted[field.name] = converted_value
    return converted


def _convert_field_value(
    field: FeishuField,
    value: object,
    *,
    upload_attachment: Callable[[Path], str] | None = None,
) -> object | None:
    if field.field_type in _FIELD_TYPES_TEXT:
        return _value_text(value)
    if field.field_type in _FIELD_TYPES_URL:
        text = _value_text(value)
        match = re.search(r"https?://[^\s]+", text)
        if match is None:
            return None
        link = match.group(0).rstrip("，。；、,.;:：）)]}>")
        display_text = text[: match.start()].strip() or link
        return {"link": link, "text": display_text}
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
            raw_values = [
                label
                for item in value
                for label in split_representative_labels(_value_text(item))
            ]
        else:
            raw_values = list(split_representative_labels(_value_text(value)))
        values: list[str] = []
        for item in raw_values:
            normalized = item.strip()
            if normalized and normalized not in values:
                values.append(normalized)
        if not values or any(item not in field.options for item in values):
            return None
        return values
    if field.field_type in _FIELD_TYPES_DATETIME:
        return _datetime_milliseconds(value)
    if field.field_type in _FIELD_TYPES_ATTACHMENT:
        if isinstance(value, Path):
            if upload_attachment is None:
                return None
            return [{"file_token": upload_attachment(value)}]
        if isinstance(value, Mapping):
            file_token = value.get("file_token")
            if isinstance(file_token, str) and file_token:
                return [{"file_token": file_token}]
            return None
        if isinstance(value, (list, tuple)):
            attachments: list[dict[str, str]] = []
            for item in value:
                if isinstance(item, Mapping) and isinstance(item.get("file_token"), str):
                    attachments.append({"file_token": item["file_token"]})
                elif isinstance(item, Path) and upload_attachment is not None:
                    attachments.append({"file_token": upload_attachment(item)})
            return attachments or None
        return None
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
        for key in ("file_token", "text", "link", "name", "value"):
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
        if isinstance(actual, list) and len(actual) == 1:
            actual = actual[0]
        if not isinstance(actual, dict):
            return False
        return all(
            _value_text(actual.get(key)) == _value_text(value) for key, value in expected.items()
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
    "FeishuMirrorSyncSummary",
    "FeishuPreparedSync",
    "FeishuTableInfo",
    "FeishuSyncError",
    "FeishuSyncSummary",
    "resolve_field_mapping",
]
