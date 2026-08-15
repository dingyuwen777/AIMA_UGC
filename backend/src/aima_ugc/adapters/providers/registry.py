"""当前已实现 Provider/Platform 的正式 Registry 组装。"""

from aima_ugc.adapters.providers.tikhub.capabilities import TIKHUB_PLATFORM_CAPABILITIES
from aima_ugc.modules.collection.provider_routing import ProviderRegistration, ProviderRegistry


def build_default_provider_registry() -> ProviderRegistry:
    """注册已由真实 Fixture/Probe 证明的 TikHub 五平台能力。"""
    return ProviderRegistry(
        registrations=(
            ProviderRegistration(
                provider="tikhub",
                capabilities=TIKHUB_PLATFORM_CAPABILITIES,
                allowed_base_urls=("https://api.tikhub.io",),
            ),
        )
    )


__all__ = ["build_default_provider_registry"]