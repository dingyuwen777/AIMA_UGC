from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(name: str, relative_path: str) -> ModuleType:
    """从仓库脚本路径加载模块，避免修改源码 package 结构。"""

    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


local_runtime = _load_script_module("aima_local_runtime_test", "scripts/dev/local_runtime.py")
sys.modules["local_runtime"] = local_runtime
backend = _load_script_module("aima_backend_test", "scripts/dev/backend.py")


def test_local_dev_env_template_has_no_unknown_keys() -> None:
    """提交到 Git 的 env.local 模板不能让 launcher 自己产生 unknown warning。"""

    config = local_runtime.load_local_dev_config(ROOT / "env.local.example")

    assert config.unknown_keys == ()


def test_local_dev_env_supports_optional_llm_and_tikhub(tmp_path: Path) -> None:
    """本地 env 支持可选 TikHub/LLM，并把明文 Key 转成外部 Secret File。"""

    env_file = tmp_path / "env.local"
    env_file.write_text(
        "AIMA_TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "AIMA_TIKHUB_API_KEY=tikhub-test\n"
        "AIMA_LLM_BASE_URL=https://llm.example/v1\n"
        "AIMA_LLM_PROVIDER_NAME=example\n"
        "AIMA_LLM_MODEL=test-model\n"
        "AIMA_LLM_API_KEY=llm-test\n"
        "AIMA_HISTORICAL_IMPORT_ROOT=.runtime/historical-input\n"
        "AIMA_DEV_ENABLE_SCHEDULER=true\n",
        encoding="utf-8",
    )

    config = local_runtime.load_local_dev_config(env_file)
    paths = local_runtime.runtime_paths(tmp_path)
    local_runtime.prepare_runtime_directories(paths)
    environment = local_runtime.build_runtime_environment(paths=paths, config=config)

    assert config.tikhub_configured is True
    assert config.llm_configured is True
    assert config.scheduler_enabled is True
    assert environment["AIMA_HISTORICAL_IMPORT_ROOT"] == ".runtime/historical-input"
    assert environment["AIMA_LLM_BASE_URL"] == "https://llm.example/v1"
    assert environment["AIMA_LLM_PROVIDER_NAME"] == "example"
    assert environment["AIMA_LLM_MODEL"] == "test-model"
    assert "AIMA_TIKHUB_API_KEY" not in environment
    assert "AIMA_LLM_API_KEY" not in environment
    assert paths.tikhub_secret_file.read_text(encoding="utf-8").strip() == "tikhub-test"
    assert paths.llm_secret_file.read_text(encoding="utf-8").strip() == "llm-test"


def test_local_dev_env_partial_llm_is_not_enabled(tmp_path: Path) -> None:
    """LLM 配置不完整时不得把半完成配置传入正式 Worker。"""

    env_file = tmp_path / "env.local"
    env_file.write_text(
        "AIMA_LLM_BASE_URL=https://llm.example/v1\n"
        "AIMA_LLM_PROVIDER_NAME=example\n"
        "AIMA_LLM_MODEL=\n"
        "AIMA_LLM_API_KEY=llm-test\n",
        encoding="utf-8",
    )

    config = local_runtime.load_local_dev_config(env_file)
    paths = local_runtime.runtime_paths(tmp_path)
    local_runtime.prepare_runtime_directories(paths)
    environment = local_runtime.build_runtime_environment(paths=paths, config=config)

    assert config.llm_partially_configured is True
    assert config.llm_configured is False
    assert "AIMA_LLM_BASE_URL" not in environment
    assert "AIMA_LLM_PROVIDER_NAME" not in environment
    assert "AIMA_LLM_MODEL" not in environment
    assert not paths.llm_secret_file.exists()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("stopped", "[STOP] PostgreSQL Docker container stopped: aima-ugc-postgres-dev"),
        (
            "already_stopped",
            "[SKIP] PostgreSQL Docker container already stopped: aima-ugc-postgres-dev",
        ),
        ("missing", "[SKIP] PostgreSQL Docker container not found: aima-ugc-postgres-dev"),
    ],
)
def test_backend_postgres_cleanup_logs_exact_container_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected: str,
) -> None:
    monkeypatch.setattr(backend, "stop_postgres_container", lambda: status)

    backend._stop_postgres_for_backend()

    assert expected in capsys.readouterr().out


def test_backend_ctrl_c_stops_children_then_postgres(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """后端中断时必须先停子进程，再停开发用 PostgreSQL。"""

    cleanup_order: list[str] = []
    config = local_runtime.LocalDevConfig(
        tikhub_base_url="https://api.tikhub.io",
        tikhub_api_key=None,
        llm_base_url=None,
        llm_provider_name=None,
        llm_model=None,
        llm_api_key=None,
        historical_import_host_root=None,
        historical_import_root=None,
        scheduler_enabled=False,
        unknown_keys=(),
    )

    monkeypatch.setattr(backend, "prepare_runtime_directories", lambda _paths: None)
    monkeypatch.setattr(backend, "prepare_cursor_secrets", lambda _paths: None)
    monkeypatch.setattr(backend, "ensure_postgres_container", lambda _paths: None)
    monkeypatch.setattr(backend, "build_runtime_environment", lambda **_kwargs: {})
    monkeypatch.setattr(backend, "_run_migration", lambda **_kwargs: None)
    monkeypatch.setattr(backend, "_provision_tikhub", lambda **_kwargs: False)
    monkeypatch.setattr(backend, "_print_feature_status", lambda **_kwargs: None)
    monkeypatch.setattr(
        backend,
        "_start_child",
        lambda name, *_args, **_kwargs: backend.ChildProcess(name, object()),
    )
    monkeypatch.setattr(
        backend,
        "_wait_for_ready",
        lambda _children: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        backend,
        "_stop_child",
        lambda child: cleanup_order.append(f"child:{child.name}"),
    )
    monkeypatch.setattr(
        backend,
        "_stop_postgres_for_backend",
        lambda: cleanup_order.append("postgres"),
    )

    result = backend._run(
        root=tmp_path,
        config=config,
        env_created=False,
        prepare_only=False,
    )

    assert result == 0
    assert cleanup_order == ["child:API", "child:Worker", "postgres"]
