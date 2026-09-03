from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest

from aima_ugc.bootstrap import runtime_config
from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import SecretFileError, read_secret_ref, write_secret_ref
from pydantic import SecretStr
from sqlalchemy.orm import Session


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


def test_database_default_llm_provider_wins_over_legacy_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """已有 DB 默认 LLM 时，环境变量只能是过渡配置，不能覆盖数据库事实。"""

    database_config = ProviderConfig(
        id=uuid4(),
        provider="api.deepseek.com",
        provider_kind="llm",
        display_name="Database LLM",
        base_url="https://api.deepseek.com/v1",
        model="db-model",
        secret_ref="providers/llm/db.key",
        enabled=True,
        is_default=True,
        revision=7,
    )
    _install_fake_provider_repository(
        monkeypatch,
        default=database_config,
        configs=(database_config,),
    )

    resolved = runtime_config.active_llm_provider(
        cast(Session, object()),
        _legacy_llm_settings(tmp_path),
    )

    assert resolved is database_config
    assert resolved.model == "db-model"
    assert resolved.revision == 7


def test_existing_database_llm_configs_disable_legacy_environment_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """DB 已进入 LLM 控制面后，没有活动默认项必须表现为未配置。"""

    non_default = ProviderConfig(
        id=uuid4(),
        provider="api.deepseek.com",
        provider_kind="llm",
        display_name="Non-default LLM",
        base_url="https://api.deepseek.com/v1",
        model="db-model",
        secret_ref="providers/llm/non-default.key",
        enabled=True,
        is_default=False,
    )
    _install_fake_provider_repository(
        monkeypatch,
        default=None,
        configs=(non_default,),
    )

    assert (
        runtime_config.active_llm_provider(
            cast(Session, object()),
            _legacy_llm_settings(tmp_path),
        )
        is None
    )


def _install_fake_provider_repository(
    monkeypatch: pytest.MonkeyPatch,
    *,
    default: ProviderConfig | None,
    configs: tuple[ProviderConfig, ...],
) -> None:
    """替换运行时 Repository，以最小单测锁定 DB/env 优先级语义。"""

    class FakeProviderRepository:
        def __init__(self, _session: object) -> None:
            pass

        def get_default(self, provider_kind: str) -> ProviderConfig | None:
            assert provider_kind == "llm"
            return default

        def list_all(self, *, provider_kind: str | None = None) -> tuple[ProviderConfig, ...]:
            assert provider_kind == "llm"
            return configs

    monkeypatch.setattr(
        runtime_config,
        "PostgresProviderConfigRepository",
        FakeProviderRepository,
    )


def _legacy_llm_settings(tmp_path) -> PlatformSettings:
    """构造与 DB 配置不同的旧环境 LLM，验证其不会越权覆盖数据库。"""

    external_root = tmp_path / "provider-secrets"
    external_root.mkdir(exist_ok=True)
    return PlatformSettings(
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        secret_dir=tmp_path / "internal-secrets",
        external_secret_dir=external_root,
        llm_base_url="https://legacy.example/v1",
        llm_provider_name="legacy.example",
        llm_model="legacy-model",
    )
