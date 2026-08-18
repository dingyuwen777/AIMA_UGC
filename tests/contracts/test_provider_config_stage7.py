"""Stage 7 Provider Config/Platform Route 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.tikhub.capabilities import XHS_TIKHUB_CAPABILITY
from aima_ugc.contracts.collection import ProviderConfigV1, ProviderPlatformRouteV1
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]


def test_provider_config_is_versioned_and_contains_only_secret_reference() -> None:
    config = ProviderConfigV1(
        provider_config_id=uuid4(),
        provider="tikhub",
        display_name="TikHub 主账号",
        base_url="https://api.tikhub.io/",
        secret_ref="providers/tikhub/main/api-key",
        enabled=True,
    )

    assert ProviderConfigV1.model_fields["schema_version"].default == "provider-config.v1"
    assert config.provider == "tikhub"
    assert config.base_url == "https://api.tikhub.io"
    assert "api_key" not in ProviderConfigV1.model_fields
    assert "token" not in ProviderConfigV1.model_fields
    assert config.model_dump(mode="json")["secret_ref"] == "providers/tikhub/main/api-key"


@pytest.mark.parametrize(
    "secret_ref",
    ["", "/absolute/key", "../outside", "providers/../outside", r"providers\\key"],
)
def test_provider_config_rejects_unsafe_secret_reference(secret_ref: str) -> None:
    with pytest.raises(ValidationError):
        ProviderConfigV1(
            provider_config_id=uuid4(),
            provider="tikhub",
            display_name="TikHub",
            base_url="https://api.tikhub.io",
            secret_ref=secret_ref,
            enabled=True,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.tikhub.io",
        "https://user:password@api.tikhub.io",
        "https://api.tikhub.io?token=secret",
        "https://api.tikhub.io#fragment",
        "api.tikhub.io",
    ],
)
def test_provider_config_rejects_unsafe_base_url(base_url: str) -> None:
    with pytest.raises(ValidationError):
        ProviderConfigV1(
            provider_config_id=uuid4(),
            provider="tikhub",
            display_name="TikHub",
            base_url=base_url,
            secret_ref="providers/tikhub/test/api-key",
            enabled=True,
        )


def test_platform_route_requires_config_capability_identity_match() -> None:
    config_id = uuid4()
    route = ProviderPlatformRouteV1(
        provider_config_id=config_id,
        provider="tikhub",
        platform="xhs",
        capability=XHS_TIKHUB_CAPABILITY,
    )
    assert route.provider_config_id == config_id
    assert route.capability.platform == "xhs"

    with pytest.raises(ValidationError, match="Capability"):
        ProviderPlatformRouteV1(
            provider_config_id=config_id,
            provider="other-provider",
            platform="xhs",
            capability=XHS_TIKHUB_CAPABILITY,
        )


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("provider-config.v1.schema.json", ProviderConfigV1),
        ("provider-operations-route.v1.schema.json", ProviderPlatformRouteV1),
    ],
)
def test_fixed_provider_config_schemas_match_pydantic_contract(filename: str, model: type) -> None:
    target = ROOT / "contracts" / "collection" / filename
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == model.model_json_schema()
