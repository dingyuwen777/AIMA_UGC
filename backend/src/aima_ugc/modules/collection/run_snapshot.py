"""Collection Run 共用 Provider 配置快照。"""

from __future__ import annotations

from collections.abc import Mapping

from aima_ugc.contracts.platform import PlatformName
from aima_ugc.modules.system.models import ProviderConfig


def provider_run_snapshot(
    provider_config: ProviderConfig,
    *,
    platform: PlatformName,
    config: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """冻结非 Secret 执行事实；只保存不可变 Secret 引用身份。"""
    return {
        "platform": platform,
        "provider_config_id": str(provider_config.id),
        "provider_kind": provider_config.provider_kind,
        "provider": provider_config.provider,
        "base_url": provider_config.base_url,
        "secret_ref": provider_config.secret_ref,
        "timeout_seconds": provider_config.timeout_seconds,
        "max_retries": provider_config.max_retries,
        "max_concurrency": provider_config.max_concurrency,
        "max_rps": provider_config.max_rps,
        "extra_config": dict(provider_config.extra_config),
        "revision": provider_config.revision,
        "config": dict(config or {}),
    }


__all__ = ["provider_run_snapshot"]