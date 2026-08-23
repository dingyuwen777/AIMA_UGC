from __future__ import annotations

from pathlib import Path

from scripts.dev.local_runtime import (
    LocalDevError,
    build_runtime_environment,
    ensure_env_local,
    frontend_dependencies_stale,
    load_local_dev_config,
    parse_env_file,
    prepare_runtime_directories,
    record_frontend_lock_fingerprint,
    runtime_paths,
)


def test_env_local_is_created_from_template_and_parser_preserves_secret_equals(tmp_path: Path) -> None:
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
        "AIMA_LLM_BASE_URL=https://llm.example/v1\n"
        "AIMA_LLM_MODEL=\n"
        "AIMA_LLM_API_KEY=secret\n",
        encoding="utf-8",
    )

    config = load_local_dev_config(env_path)

    assert config.llm_configured is False
    assert config.llm_partially_configured is True


def test_runtime_environment_materializes_optional_secrets_not_secret_env_vars(
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

    assert paths.tikhub_secret_file.read_text(encoding="utf-8").strip() == "tikhub-local-key"
    assert paths.llm_secret_file.read_text(encoding="utf-8").strip() == "llm-local-key"
    assert environment["AIMA_LLM_BASE_URL"] == "https://llm.example/v1"
    assert environment["AIMA_LLM_PROVIDER_NAME"] == "fixture"
    assert environment["AIMA_LLM_MODEL"] == "fixture-model"
    assert "AIMA_LLM_API_KEY" not in environment
    assert "AIMA_TIKHUB_API_KEY" not in environment


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
