from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from aima_ugc.bootstrap.internal_v1 import (
    InternalV1ProviderSettings,
    load_internal_v1_provider_settings,
    validate_internal_v1_llm_settings,
    validate_internal_v1_provider_secret,
)
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.security import SecretFileError


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _platform_settings(secret_dir: Path, **overrides: object) -> PlatformSettings:
    return PlatformSettings(
        data_dir=secret_dir.parent / "data",
        log_dir=secret_dir.parent / "logs",
        secret_dir=secret_dir,
        **overrides,
    )


def _run_prepare_host(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/deploy/prepare_host.py", *args],
        cwd=_repository_root(),
        capture_output=True,
        text=True,
        check=False,
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


def test_external_secret_dir_can_be_separated_without_moving_internal_secrets(
    tmp_path: Path,
) -> None:
    internal_dir = tmp_path / "internal-secrets"
    external_dir = tmp_path / "external-secrets"
    internal_dir.mkdir()
    external_dir.mkdir()
    (internal_dir / "postgres_password").write_text("database-password\n", encoding="utf-8")
    (external_dir / "tikhub_api_key").write_text("provider-key\n", encoding="utf-8")
    (external_dir / "llm_api_key").write_text("llm-key\n", encoding="utf-8")
    provider = InternalV1ProviderSettings(
        enabled=True,
        base_url="https://api.tikhub.io",
        secret_ref="tikhub_api_key",
    )
    settings = _platform_settings(
        internal_dir,
        external_secret_dir=external_dir,
        llm_base_url="https://provider.example/v1",
        llm_model="model-name",
    )

    assert settings.postgres_password_file == internal_dir / "postgres_password"
    assert settings.external_secret_root == external_dir
    assert settings.llm_api_key_file == external_dir / "llm_api_key"
    validate_internal_v1_provider_secret(settings, provider)
    assert validate_internal_v1_llm_settings(settings) is True


def test_load_settings_resolves_external_secret_dir_from_environment(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "AIMA_DATA_DIR": "data",
            "AIMA_LOG_DIR": "logs",
            "AIMA_SECRET_DIR": "internal-secrets",
            "AIMA_EXTERNAL_SECRET_DIR": "external-secrets",
        },
        base_dir=tmp_path,
    )

    assert settings.secret_dir == (tmp_path / "internal-secrets").resolve()
    assert settings.external_secret_root == (tmp_path / "external-secrets").resolve()


def test_internal_v1_llm_absent_is_disabled(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()

    assert validate_internal_v1_llm_settings(_platform_settings(secret_dir)) is False


def test_internal_v1_llm_partial_configuration_fails_closed(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()

    with pytest.raises(ValueError, match="AIMA_LLM_MODEL"):
        validate_internal_v1_llm_settings(
            _platform_settings(
                secret_dir,
                llm_base_url="https://provider.example/v1",
            )
        )


def test_internal_v1_llm_configured_requires_readable_secret(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()

    with pytest.raises(SecretFileError):
        validate_internal_v1_llm_settings(
            _platform_settings(
                secret_dir,
                llm_base_url="https://provider.example/v1",
                llm_model="model-name",
            )
        )


def test_internal_v1_llm_configured_uses_existing_secret_boundary(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    (secret_dir / "llm_api_key").write_text("test-key\n", encoding="utf-8")

    assert (
        validate_internal_v1_llm_settings(
            _platform_settings(
                secret_dir,
                llm_base_url="https://provider.example/v1",
                llm_model="model-name",
            )
        )
        is True
    )


def test_production_env_template_is_single_admin_input_without_database_password() -> None:
    content = (_repository_root() / "env.production.example").read_text(encoding="utf-8")

    assert "AIMA_TIKHUB_API_KEY=" in content
    assert "AIMA_LLM_API_KEY=" in content
    assert "AIMA_DB_PASSWORD=" not in content
    assert "POSTGRES_PASSWORD=" not in content


def test_compose_default_startup_declares_bootstrap_and_automatic_one_shots() -> None:
    content = (_repository_root() / "compose.yaml").read_text(encoding="utf-8")

    assert "  bootstrap:" in content
    assert "service_completed_successfully" in content
    assert 'profiles: ["tools"]' not in content
    assert "AIMA_EXTERNAL_SECRET_DIR=/run/provider-secrets" in content
    assert "AIMA_SECRET_DIR=/run/internal-secrets" in content
    assert "environment: AIMA_TIKHUB_API_KEY" in content
    assert "environment: AIMA_LLM_API_KEY" in content


@pytest.mark.skipif(os.name != "posix", reason="Internal V1 宿主准备只支持 POSIX")
def test_prepare_host_rejects_relative_root_before_privileged_changes() -> None:
    result = _run_prepare_host("--root", "relative-host-root")

    assert result.returncode == 1
    assert "宿主根目录必须是绝对路径" in result.stderr


@pytest.mark.skipif(os.name != "posix", reason="Internal V1 宿主准备只支持 POSIX")
def test_prepare_host_rejects_symlink_root_before_privileged_changes(tmp_path: Path) -> None:
    target = tmp_path / "real-root"
    target.mkdir()
    link = tmp_path / "linked-root"
    link.symlink_to(target, target_is_directory=True)

    result = _run_prepare_host("--root", str(link))

    assert result.returncode == 1
    assert "不允许符号链接" in result.stderr


@pytest.mark.skipif(os.name != "posix", reason="Internal V1 宿主准备只支持 POSIX")
def test_prepare_host_rejects_missing_password_for_initialized_postgres(
    tmp_path: Path,
) -> None:
    cluster = tmp_path / "postgres" / "18" / "docker"
    cluster.mkdir(parents=True)
    (cluster / "PG_VERSION").write_text("18\n", encoding="utf-8")

    result = _run_prepare_host("--root", str(tmp_path))

    assert result.returncode == 1
    assert "已有 PostgreSQL 18 数据" in result.stderr
    assert "postgres_password" in result.stderr
