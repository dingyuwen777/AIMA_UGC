from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.security import SecretFileError, read_secret_ref, write_secret_ref
from pydantic import SecretStr


def test_llm_provider_keeps_domain_style_identity_for_pricing_compatibility() -> None:
    config = ProviderConfig(
        id=uuid4(),
        provider="api.deepseek.com",
        provider_kind="llm",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-pro",
        secret_ref="llm_api_key",
        enabled=True,
        is_default=True,
    )

    assert config.provider == "api.deepseek.com"
    assert config.safe_runtime_snapshot()["provider"] == "api.deepseek.com"


def test_collection_provider_still_uses_collection_contract_identity_rules() -> None:
    with pytest.raises(ValueError):
        ProviderConfig(
            id=uuid4(),
            provider="api.tikhub.io",
            provider_kind="collection",
            display_name="TikHub",
            base_url="https://api.tikhub.io",
            secret_ref="tikhub_api_key",
            enabled=True,
        )


def test_provider_secret_writer_is_immutable(tmp_path) -> None:
    root = tmp_path / "provider-secrets"
    root.mkdir()
    reference = "providers/runtime-test/key-1.key"

    write_secret_ref(root, reference, SecretStr("first-value"))
    assert read_secret_ref(root, reference).get_secret_value() == "first-value"
    with pytest.raises(SecretFileError):
        write_secret_ref(root, reference, SecretStr("second-value"))
    assert read_secret_ref(root, reference).get_secret_value() == "first-value"


def test_collection_run_snapshot_freezes_provider_runtime_revision() -> None:
    config = ProviderConfig(
        id=uuid4(),
        provider="tikhub",
        provider_kind="collection",
        display_name="TikHub",
        base_url="https://api.tikhub.io",
        secret_ref="providers/tikhub/key-2.key",
        timeout_seconds=61,
        max_retries=4,
        max_concurrency=7,
        max_rps=3,
        revision=9,
        enabled=True,
    )

    snapshot = provider_run_snapshot(config, platform="xiaohongshu")

    assert snapshot["timeout_seconds"] == 61
    assert snapshot["max_retries"] == 4
    assert snapshot["max_concurrency"] == 7
    assert snapshot["max_rps"] == 3
    assert snapshot["revision"] == 9
    assert snapshot["secret_ref"] == "providers/tikhub/key-2.key"
