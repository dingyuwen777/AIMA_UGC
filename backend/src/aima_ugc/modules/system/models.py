"""System 模块稳定业务对象。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import JsonValue

from aima_ugc.contracts.collection import ProviderConfigV1
from aima_ugc.contracts.platform import PlatformScope
from aima_ugc.platform.security import validate_secret_ref

ActorKind = Literal["system", "principal"]
ProviderKind = Literal["collection", "llm"]
_PROVIDER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


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
    """LLM/采集 Provider 的非敏感配置；Secret 永远只保存不可变引用。"""

    id: UUID
    provider: str
    display_name: str
    base_url: str
    secret_ref: str
    enabled: bool
    provider_kind: ProviderKind = "collection"
    model: str | None = None
    timeout_seconds: int = 45
    max_retries: int = 3
    max_concurrency: int = 5
    max_rps: int | None = None
    extra_config: dict[str, JsonValue] = field(default_factory=dict)
    is_default: bool = False
    revision: int = 1

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()
        display_name = self.display_name.strip()
        secret_ref = validate_secret_ref(self.secret_ref)
        model = self.model.strip() if isinstance(self.model, str) else None
        if not _PROVIDER_RE.fullmatch(provider):
            raise ValueError("Provider 名称必须是稳定的小写标识")
        if not display_name:
            raise ValueError("Provider 显示名称不能为空")
        if self.timeout_seconds <= 0:
            raise ValueError("Provider timeout_seconds 必须大于 0")
        if self.max_retries < 0:
            raise ValueError("Provider max_retries 不能为负数")
        if self.max_concurrency <= 0:
            raise ValueError("Provider max_concurrency 必须大于 0")
        if self.max_rps is not None and self.max_rps <= 0:
            raise ValueError("Provider max_rps 必须大于 0")
        if self.revision <= 0:
            raise ValueError("Provider revision 必须大于 0")
        if self.is_default and not self.enabled:
            raise ValueError("默认 Provider 必须处于启用状态")

        if self.provider_kind == "collection":
            validated = ProviderConfigV1(
                provider_config_id=self.id,
                provider=provider,
                display_name=display_name,
                base_url=self.base_url,
                secret_ref=secret_ref,
                enabled=self.enabled,
            )
            normalized_base_url = validated.base_url
        elif self.provider_kind == "llm":
            normalized_base_url = _normalize_llm_base_url(self.base_url)
            if not model:
                raise ValueError("LLM Provider 必须配置 model")
        else:  # pragma: no cover - Literal/DB constraint 双保险
            raise ValueError("未知 Provider Kind")

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "base_url", normalized_base_url)
        object.__setattr__(self, "secret_ref", secret_ref)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "extra_config", dict(self.extra_config))

    def safe_runtime_snapshot(self) -> dict[str, JsonValue]:
        """返回可持久化到 Run 的安全快照；仅包含 Secret 引用，不包含 Secret 值。"""

        return {
            "provider_config_id": str(self.id),
            "provider_kind": self.provider_kind,
            "provider": self.provider,
            "base_url": self.base_url,
            "secret_ref": self.secret_ref,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_concurrency": self.max_concurrency,
            "max_rps": self.max_rps,
            "extra_config": dict(self.extra_config),
            "revision": self.revision,
        }


def _normalize_llm_base_url(value: str) -> str:
    """LLM 允许 HTTPS 与受部署控制的 HTTP，但拒绝凭据、query 与 fragment。"""

    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("LLM Base URL 必须是绝对 HTTP/HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("LLM Base URL 不能内嵌用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("LLM Base URL 不能包含 query 或 fragment")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


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
