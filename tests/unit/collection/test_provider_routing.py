"""Stage 7 Provider Config → Platform Capability 路由测试。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.modules.system.models import ProviderConfig


def _config(*, provider: str = "tikhub", enabled: bool = True) -> ProviderConfig:
    return ProviderConfig(
        id=uuid4(),
        provider=provider,
        display_name="测试 Provider",
        base_url="https://api.tikhub.io",
        secret_ref="providers/tikhub/test/api-key",
        enabled=enabled,
    )


def test_default_registry_resolves_current_xhs_tikhub_capability() -> None:
    registry = build_default_provider_registry()
    config = _config()

    route = registry.resolve(config=config, platform="xhs")

    assert route.provider_config_id == config.id
    assert route.provider == "tikhub"
    assert route.platform == "xhs"
    assert route.capability.operation("keyword_search") is not None


def test_same_provider_type_can_have_multiple_independent_config_instances() -> None:
    registry = build_default_provider_registry()
    first = _config()
    second = _config()

    first_route = registry.resolve(config=first, platform="xhs")
    second_route = registry.resolve(config=second, platform="xhs")

    assert first_route.provider_config_id != second_route.provider_config_id
    assert first_route.capability == second_route.capability


def test_registry_fails_closed_for_disabled_unknown_or_unsupported_routes() -> None:
    registry = build_default_provider_registry()

    with pytest.raises(ValueError, match="禁用"):
        registry.resolve(config=_config(enabled=False), platform="xhs")

    with pytest.raises(ValueError, match="未注册"):
        registry.resolve(config=_config(provider="other-provider"), platform="xhs")

    with pytest.raises(ValueError, match="不支持"):
        registry.resolve(config=_config(), platform="douyin")
