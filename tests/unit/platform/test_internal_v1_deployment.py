from __future__ import annotations

from pathlib import Path

import pytest
from aima_ugc.bootstrap.internal_v1 import (
    InternalV1ProviderSettings,
    load_internal_v1_provider_settings,
    validate_internal_v1_provider_secret,
)
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import SecretFileError


def _platform_settings(secret_dir: Path) -> PlatformSettings:
    return PlatformSettings(
        data_dir=secret_dir.parent / "data",
        log_dir=secret_dir.parent / "logs",
        secret_dir=secret_dir,
    )


def test_internal_v1_provider_defaults_to_disabled() -> None:
    settings = load_internal_v1_provider_settings({})

    assert settings == InternalV1ProviderSettings(
        enabled=False,
        base_url="https://api.tikhub.io",
        secret_ref="tikhub_api_key",
    )


def test_internal_v1_provider_rejects_unknown_enabled_value() -> None:
    with pytest.raises(ValueError, match="AIMA_TIKHUB_ENABLED"):
        load_internal_v1_provider_settings({"AIMA_TIKHUB_ENABLED": "sometimes"})


def test_internal_v1_provider_enabled_requires_readable_secret(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    provider = InternalV1ProviderSettings(
        enabled=True,
        base_url="https://api.tikhub.io",
        secret_ref="tikhub_api_key",
    )

    with pytest.raises(SecretFileError):
        validate_internal_v1_provider_secret(_platform_settings(secret_dir), provider)


def test_internal_v1_provider_secret_validation_uses_existing_secret_boundary(
    tmp_path: Path,
) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    (secret_dir / "tikhub_api_key").write_text("test-key\n", encoding="utf-8")
    provider = InternalV1ProviderSettings(
        enabled=True,
        base_url="https://api.tikhub.io",
        secret_ref="tikhub_api_key",
    )

    validate_internal_v1_provider_secret(_platform_settings(secret_dir), provider)
