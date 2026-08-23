from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_local_runtime() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "local_runtime.py"
    spec = importlib.util.spec_from_file_location("aima_test_local_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载本地开发 helper：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_LOCAL_RUNTIME = _load_local_runtime()
LocalDevError = _LOCAL_RUNTIME.LocalDevError
build_runtime_environment = _LOCAL_RUNTIME.build_runtime_environment
ensure_env_local = _LOCAL_RUNTIME.ensure_env_local
ensure_random_secret = _LOCAL_RUNTIME.ensure_random_secret
frontend_dependencies_stale = _LOCAL_RUNTIME.frontend_dependencies_stale
load_local_dev_config = _LOCAL_RUNTIME.load_local_dev_config
parse_env_file = _LOCAL_RUNTIME.parse_env_file
prepare_runtime_directories = _LOCAL_RUNTIME.prepare_runtime_directories
record_frontend_lock_fingerprint = _LOCAL_RUNTIME.record_frontend_lock_fingerprint
runtime_paths = _LOCAL_RUNTIME.runtime_paths


def test_env_local_is_created_from_template_and_parser_preserves_secret_equals(
    tmp_path: Path,
) -> None:
    template = tmp_path / "env.local.example"
    template.write_text(
        "# comment\nAIMA_TIKHUB_API_KEY='abc==123'\nAIMA_DEV_ENABLE_SCHEDULER=false\n",
        encoding="utf-8",
    )

    env_path, created = ensure_env_local(tmp_path)
    values = parse_env_file(env_path)

    assert created is True
    assert values["AIMA_TIKHUB_API_KEY"] == "abc==123"
    second_path, second_created = ensure_env_local(tmp_path)
    assert second_path == env_path
    assert second_created is False


def test_local_config_keeps_optional_features_disabled_when_blank(tmp_path: Path) -> None:
    env_path = tmp_path / "env.local"
    env_path.write_text(
        "AIMA_TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "AIMA_TIKHUB_API_KEY=\n"
        "AIMA_LLM_BASE_URL=\n"
        "AIMA_LLM_PROVIDER_NAME=\n"
        "AIMA_LLM_MODEL=\n"
        "AIMA_LLM_API_KEY=\n"
        "AIMA_DEV_ENABLE_SCHEDULER=false\n",
        encoding="utf-8",
    )

    config = load_local_dev_config(env_path)

    assert config.tikhub_configured is False
    assert config.llm_configured is False
    assert config.llm_partially_configured is False
    assert config.scheduler_enabled is False


def test_local_config_marks_partial_llm_without_failing_base_runtime(tmp_path: Path) -> None:
    env_path = tmp_path / "env.local"
    env_path.write_text(
        "AIMA_LLM_BASE_URL=https://llm.example/v1\nAIMA_LLM_MODEL=\nAIMA_LLM_API_KEY=secret\n",
        encoding="utf-8",
    )

    config = load_local_dev_config(env_path)

    assert config.llm_configured is False
    assert config.llm_partially_configured is True


def test_runtime_environment_uses_separate_internal_and_external_secret_roots(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "env.local"
    env_path.write_text(
        "AIMA_TIKHUB_API_KEY=tikhub-local-key\n"
        "AIMA_LLM_BASE_URL=https://llm.example/v1\n"
        "AIMA_LLM_PROVIDER_NAME=fixture\n"
        "AIMA_LLM_MODEL=fixture-model\n"
        "AIMA_LLM_API_KEY=llm-local-key\n",
        encoding="utf-8",
    )
    paths = runtime_paths(tmp_path)
    prepare_runtime_directories(paths)
    config = load_local_dev_config(env_path)

    environment = build_runtime_environment(paths=paths, config=config)

    assert paths.internal_secrets == tmp_path / ".runtime" / "internal-secrets"
    assert paths.external_secrets == tmp_path / ".runtime" / "secrets"
    assert paths.tikhub_secret_file.parent == paths.external_secrets
    assert paths.llm_secret_file.parent == paths.external_secrets
    assert paths.postgres_password_file.parent == paths.internal_secrets
    assert paths.tikhub_secret_file.read_text(encoding="utf-8").strip() == "tikhub-local-key"
    assert paths.llm_secret_file.read_text(encoding="utf-8").strip() == "llm-local-key"
    assert environment["AIMA_SECRET_DIR"] == str(paths.internal_secrets)
    assert environment["AIMA_EXTERNAL_SECRET_DIR"] == str(paths.external_secrets)
    assert environment["AIMA_LLM_BASE_URL"] == "https://llm.example/v1"
    assert environment["AIMA_LLM_PROVIDER_NAME"] == "fixture"
    assert environment["AIMA_LLM_MODEL"] == "fixture-model"
    assert "AIMA_LLM_API_KEY" not in environment
    assert "AIMA_TIKHUB_API_KEY" not in environment


def test_legacy_postgres_password_is_not_reused_for_new_internal_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime_paths(tmp_path)
    prepare_runtime_directories(paths)
    legacy = paths.external_secrets / "postgres_password"
    legacy.write_text(f"{'l' * 48}\n", encoding="utf-8")
    generated = "generated-internal-postgres-password-000000000000"
    monkeypatch.setattr(_LOCAL_RUNTIME.secrets, "token_urlsafe", lambda _size: generated)

    value = ensure_random_secret(paths.postgres_password_file, min_characters=32)

    assert value == generated
    assert paths.postgres_password_file.read_text(encoding="utf-8").strip() == generated
    assert legacy.read_text(encoding="utf-8").strip() == "l" * 48


def test_internal_secret_symlink_fails_closed(tmp_path: Path) -> None:
    paths = runtime_paths(tmp_path)
    prepare_runtime_directories(paths)
    outside = tmp_path / "outside-secret"
    outside.write_text(f"{'x' * 48}\n", encoding="utf-8")
    try:
        paths.postgres_password_file.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"当前平台无法创建测试符号链接：{exc}")

    with pytest.raises(LocalDevError, match="符号链接"):
        ensure_random_secret(paths.postgres_password_file, min_characters=32)

    assert outside.read_text(encoding="utf-8").strip() == "x" * 48


def test_frontend_dependency_fingerprint_detects_lock_change(tmp_path: Path) -> None:
    paths = runtime_paths(tmp_path)
    prepare_runtime_directories(paths)
    frontend = tmp_path / "frontend"
    (frontend / "node_modules").mkdir(parents=True)
    lock = frontend / "package-lock.json"
    lock.write_text('{"lockfileVersion":3}\n', encoding="utf-8")

    assert frontend_dependencies_stale(paths, frontend) is True
    record_frontend_lock_fingerprint(paths, frontend)
    assert frontend_dependencies_stale(paths, frontend) is False

    lock.write_text('{"lockfileVersion":3,"changed":true}\n', encoding="utf-8")
    assert frontend_dependencies_stale(paths, frontend) is True


def test_env_parser_rejects_non_assignment_line(tmp_path: Path) -> None:
    env_path = tmp_path / "env.local"
    env_path.write_text("not-an-assignment\n", encoding="utf-8")

    try:
        parse_env_file(env_path)
    except LocalDevError as exc:
        assert "KEY=value" in str(exc)
    else:
        raise AssertionError("invalid env.local line must fail")
