"""Provider Config → Platform Capability 的 Provider-neutral 路由。"""

from __future__ import annotations

from dataclasses import dataclass

from aima_ugc.contracts.collection import ProviderPlatformCapabilityV1, ProviderPlatformRouteV1
from aima_ugc.contracts.platform import PlatformName
from aima_ugc.contracts.collection.provider_config import normalize_provider_base_url
from aima_ugc.modules.system.models import ProviderConfig


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """一个已实现 Provider 的运行时注册事实。"""

    provider: str
    capabilities: tuple[ProviderPlatformCapabilityV1, ...]
    allowed_base_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.capabilities:
            raise ValueError("Provider 注册至少需要一个已实现平台 Capability")
        if not self.allowed_base_urls:
            raise ValueError("Provider 注册至少需要一个允许的 Base URL")
        if any(capability.provider != self.provider for capability in self.capabilities):
            raise ValueError("Provider 注册与 Capability 的 Provider 身份不一致")
        normalized_urls = tuple(normalize_provider_base_url(url) for url in self.allowed_base_urls)
        if len(normalized_urls) != len(set(normalized_urls)):
            raise ValueError("Provider 注册存在重复 Base URL")
        object.__setattr__(self, "allowed_base_urls", normalized_urls)
        platforms = [capability.platform for capability in self.capabilities]
        if len(platforms) != len(set(platforms)):
            raise ValueError("Provider 注册存在重复平台 Capability")


class ProviderRegistry:
    """只路由当前已经注册的 Provider/Platform 机器能力，未知组合关闭失败。"""

    def __init__(self, registrations: tuple[ProviderRegistration, ...]) -> None:
        providers = [item.provider for item in registrations]
        if len(providers) != len(set(providers)):
            raise ValueError("Provider Registry 存在重复 Provider")
        self._registrations = {item.provider: item for item in registrations}

    def resolve(self, *, config: ProviderConfig, platform: PlatformName) -> ProviderPlatformRouteV1:
        if not config.enabled:
            raise ValueError(f"Provider 配置已禁用: {config.id}")
        registration = self._registrations.get(config.provider)
        if registration is None:
            raise ValueError(f"Provider 未注册: {config.provider}")

        if normalize_provider_base_url(config.base_url) not in registration.allowed_base_urls:
            raise ValueError(f"Provider Base URL 不在允许列表: {config.provider}")

        capability = next(
            (item for item in registration.capabilities if item.platform == platform),
            None,
        )
        if capability is None:
            raise ValueError(f"Provider {config.provider} 不支持平台: {platform}")

        return ProviderPlatformRouteV1(
            provider_config_id=config.id,
            provider=config.provider,
            platform=platform,
            capability=capability,
        )


__all__ = ["ProviderRegistration", "ProviderRegistry"]
