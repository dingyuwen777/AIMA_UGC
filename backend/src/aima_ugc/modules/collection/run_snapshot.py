"""Collection Run 共用 Provider 配置快照。"""

from __future__ import annotations

from aima_ugc.contracts.platform import PlatformName
from aima_ugc.modules.system.models import ProviderConfig


def provider_run_snapshot(
    provider_config: ProviderConfig,
    *,
    platform: PlatformName,
    config: dict[str, object] | None = None,
) -> dict[str, object]:
    """冻结非 Secret 执行事实；只保存 Secret 引用身份。"""
    return {
        "platform": platform,
        "provider_config_id": str(provider_config.id),
        "provider": provider_config.provider,
        "base_url": provider_config.base_url,
        "secret_ref": provider_config.secret_ref,
        "config": dict(config or {}),
    }


__all__ = ["provider_run_snapshot"]
