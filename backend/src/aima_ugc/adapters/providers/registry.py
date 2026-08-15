"""当前已实现 Provider/Platform 的正式 Registry 组装。"""

from aima_ugc.adapters.providers.tikhub.capabilities import XHS_TIKHUB_CAPABILITY
from aima_ugc.modules.collection.provider_routing import ProviderRegistration, ProviderRegistry


def build_default_provider_registry() -> ProviderRegistry:
    """只注册当前已有机器实现的 TikHub + 小红书能力。"""
    return ProviderRegistry(
        registrations=(
            ProviderRegistration(
                provider="tikhub",
                capabilities=(XHS_TIKHUB_CAPABILITY,),
                allowed_base_urls=("https://api.tikhub.io",),
            ),
        )
    )


__all__ = ["build_default_provider_registry"]
