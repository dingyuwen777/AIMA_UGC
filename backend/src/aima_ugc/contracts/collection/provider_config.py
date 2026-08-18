"""Stage 7 Provider 配置实例与平台路由 V1 Contract。"""

from __future__ import annotations

from typing import Literal, Self
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from aima_ugc.contracts.provider.base import PlatformName, ProviderName
from aima_ugc.platform.security import validate_secret_ref

from .models import CollectionBaseModel, ProviderPlatformCapabilityV1


def normalize_provider_base_url(value: str) -> str:
    """规范化 Provider Base URL；带凭据、明文 HTTP、查询或片段均拒绝。"""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Provider Base URL 必须是绝对 HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Provider Base URL 不能内嵌用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("Provider Base URL 不能包含 query 或 fragment")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class ProviderConfigV1(CollectionBaseModel):
    """一个可被多个平台引用的 Provider 配置实例；只保存 Secret 引用。"""

    schema_version: Literal["provider-config.v1"] = "provider-config.v1"
    provider_config_id: UUID
    provider: ProviderName
    display_name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=2048)
    secret_ref: str = Field(min_length=1, max_length=256)
    enabled: bool = True

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Provider 显示名称不能为空")
        return normalized

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return normalize_provider_base_url(value)

    @field_validator("secret_ref")
    @classmethod
    def validate_secret_reference(cls, value: str) -> str:
        return validate_secret_ref(value)


class ProviderPlatformRouteV1(CollectionBaseModel):
    """平台选择具体 Provider Config 后解析出的稳定路由与业务 Capability。"""

    schema_version: Literal["provider-operations-route.v1"] = "provider-operations-route.v1"
    provider_config_id: UUID
    provider: ProviderName
    platform: PlatformName
    capability: ProviderPlatformCapabilityV1

    @model_validator(mode="after")
    def validate_capability_identity(self) -> Self:
        if self.capability.provider != self.provider or self.capability.platform != self.platform:
            raise ValueError("Provider Platform Route 与 Capability 身份不一致")
        return self


__all__ = ["ProviderConfigV1", "ProviderPlatformRouteV1", "normalize_provider_base_url"]
