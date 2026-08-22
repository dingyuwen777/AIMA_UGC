"""System 模块稳定业务对象。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import JsonValue

from aima_ugc.contracts.collection import ProviderConfigV1
from aima_ugc.contracts.platform import PlatformScope

ActorKind = Literal["system", "principal"]


@dataclass(frozen=True, slots=True)
class SystemSetting:
    """非敏感、需要数据库事实源的系统设置。"""

    key: str
    value: JsonValue
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """与具体身份 Provider 解耦的审计事件。"""

    id: UUID
    actor_kind: ActorKind
    actor_ref: str | None
    event_type: str
    object_type: str | None
    object_id: str | None
    request_id: str | None
    safe_detail: dict[str, JsonValue]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """一个可被多个平台复用的 Provider 配置实例；Secret 只保存引用。"""

    id: UUID
    provider: str
    display_name: str
    base_url: str
    secret_ref: str
    enabled: bool

    def __post_init__(self) -> None:
        validated = ProviderConfigV1(
            provider_config_id=self.id,
            provider=self.provider,
            display_name=self.display_name,
            base_url=self.base_url,
            secret_ref=self.secret_ref,
            enabled=self.enabled,
        )
        object.__setattr__(self, "provider", validated.provider)
        object.__setattr__(self, "display_name", validated.display_name)
        object.__setattr__(self, "base_url", validated.base_url)
        object.__setattr__(self, "secret_ref", validated.secret_ref)


@dataclass(frozen=True, slots=True)
class KeywordPack:
    """可复用的关键词集合父事实。"""

    id: UUID
    name: str
    description: str
    enabled: bool
    version: int


@dataclass(frozen=True, slots=True)
class Keyword:
    """单个关键词事实；规范化身份由调用边界显式提供。"""

    id: UUID
    text: str
    normalized_text: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class KeywordPackItem:
    """词包内关键词的平台适用范围属性。"""

    pack_id: UUID
    keyword_id: UUID
    platform_scope: PlatformScope
    priority: int
    enabled: bool
    note: str


@dataclass(frozen=True, slots=True)
class GlobalRelevanceConfig:
    """全系统零或一条的 Relevance Keyword Pack 选择事实。"""

    keyword_pack_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
