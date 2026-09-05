"""锁定本地/生产 env、Compose 与源码 launcher 的共享配置契约。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPTS = ROOT / "scripts" / "dev"
if str(DEV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DEV_SCRIPTS))

from local_runtime import build_runtime_environment, load_local_dev_config, runtime_paths  # noqa: E402


HISTORICAL_RUNTIME_INTERPOLATION = "${AIMA_HISTORICAL_IMPORT_ROOT:-/data/aima-historical-input}"


def test_shared_env_local_is_valid_for_source_launcher(tmp_path: Path) -> None:
    """共享 env.local 的 Docker 字段不应被源码 launcher 误报，源码应使用宿主历史路径。"""

    config = load_local_dev_config(ROOT / "env.local.example")

    assert config.unknown_keys == ()
    assert config.historical_import_host_root == "./.runtime/historical-input"
    assert config.historical_import_root == "/data/aima-historical-input"

    environment = build_runtime_environment(paths=runtime_paths(tmp_path), config=config)
    assert environment["AIMA_HISTORICAL_IMPORT_ROOT"] == "./.runtime/historical-input"


def test_source_launcher_keeps_legacy_historical_root_compatible(tmp_path: Path) -> None:
    """旧 env.local 只有 runtime root 时仍应作为源码历史目录兼容回退。"""

    env_file = tmp_path / "env.local"
    env_file.write_text(
        "AIMA_HISTORICAL_IMPORT_ROOT=.runtime/legacy-historical-input\n"
        "AIMA_DEV_ENABLE_SCHEDULER=false\n",
        encoding="utf-8",
    )

    config = load_local_dev_config(env_file)
    environment = build_runtime_environment(paths=runtime_paths(tmp_path), config=config)

    assert config.unknown_keys == ()
    assert environment["AIMA_HISTORICAL_IMPORT_ROOT"] == ".runtime/legacy-historical-input"


def test_removed_analysis_shard_env_is_rejected_as_unknown(tmp_path: Path) -> None:
    """已失效的 Shard Size 环境变量不得继续被 launcher 静默接受。"""

    env_file = tmp_path / "env.local"
    env_file.write_text("AIMA_ANALYSIS_RUN_SHARD_SIZE=1\n", encoding="utf-8")

    config = load_local_dev_config(env_file)

    assert config.unknown_keys == ("AIMA_ANALYSIS_RUN_SHARD_SIZE",)


def test_compose_uses_one_configurable_historical_runtime_root() -> None:
    """canonical 与 Windows Compose 的 backend 环境和 bind target 必须共享同一 runtime root。"""

    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    windows = (ROOT / "compose.windows.yaml").read_text(encoding="utf-8")
    environment_line = f"AIMA_HISTORICAL_IMPORT_ROOT={HISTORICAL_RUNTIME_INTERPOLATION}"
    target_line = f"target: {HISTORICAL_RUNTIME_INTERPOLATION}"

    assert environment_line in compose
    assert compose.count(target_line) == 4
    assert windows.count(target_line) == 4
    assert "target: /data/aima-historical-input" not in compose
    assert "target: /data/aima-historical-input" not in windows


def test_env_examples_expose_only_real_runtime_boundaries() -> None:
    """本地模板覆盖源码+Compose，生产模板暴露真实服务器配置且不保留假配置。"""

    local_text = (ROOT / "env.local.example").read_text(encoding="utf-8")
    local_config = load_local_dev_config(ROOT / "env.local.example")
    production = (ROOT / "env.production.example").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert local_config.unknown_keys == ()
    assert local_config.historical_import_host_root == "./.runtime/historical-input"
    assert local_config.historical_import_root == "/data/aima-historical-input"
    assert "AIMA_HOST_ROOT=./.runtime/compose" in local_text
    assert "AIMA_HISTORICAL_IMPORT_ROOT=/data/aima-historical-input" in production
    assert "AIMA_ANALYSIS_RUN_SHARD_SIZE" not in local_text
    assert "AIMA_ANALYSIS_RUN_SHARD_SIZE" not in production
    assert "AIMA_ANALYSIS_RUN_SHARD_SIZE" not in compose


def test_runtime_documentation_uses_env_local_for_local_compose() -> None:
    """长期运行文档必须把本地源码、本地 Compose 与服务器 Compose 的 env 入口写清楚。"""

    documentation = (ROOT / "docs" / "02_环境运行与部署.md").read_text(encoding="utf-8")
    windows_guide = (
        ROOT / "docs" / "guides" / "03_Windows Docker Desktop Compose运行.md"
    ).read_text(encoding="utf-8")

    local_linux = "docker compose --env-file env.local up -d --build --wait"
    local_windows = (
        "docker compose -f compose.yaml -f compose.windows.yaml --env-file env.local "
        "up -d --build --wait"
    )
    production = "docker compose --env-file env.production up -d --build --wait"

    assert local_linux in documentation
    assert local_windows in documentation
    assert production in documentation
    assert "env.local **只属于源码开发 launcher 的输入界面" not in documentation

    assert "copy env.local.example env.local" in windows_guide
    assert "Copy-Item env.local.example env.local" in windows_guide
    assert local_windows in windows_guide
    assert production in windows_guide


def test_windows_tooling_validates_the_local_compose_env() -> None:
    """Windows Tooling 的真实 Compose CLI 校验必须使用正式本地 env.local 入口。"""

    tooling = (ROOT / ".github" / "workflows" / "tooling.yml").read_text(encoding="utf-8")

    assert "Copy-Item env.local.example env.local" in tooling
    assert (
        "docker compose -f compose.yaml -f compose.windows.yaml --env-file env.local config "
        "--services"
    ) in tooling
    assert "Copy-Item env.production.example env.production" not in tooling
