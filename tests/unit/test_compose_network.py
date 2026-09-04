from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _write_env_without_network(tmp_path: Path) -> Path:
    """生成不显式配置 Docker 网段的测试 env，用于验证 Compose 内建默认值。"""
    source = (ROOT / "env.production.example").read_text(encoding="utf-8")
    lines = [
        line
        for line in source.splitlines()
        if not line.startswith(("AIMA_DOCKER_SUBNET=", "AIMA_DOCKER_GATEWAY="))
    ]
    target = tmp_path / "env.production"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _render_app_network(
    env_file: Path,
    compose_files: tuple[Path, ...],
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """调用真实 Docker Compose parser，返回渲染后的 app network 配置。"""
    if shutil.which("docker") is None:
        pytest.skip("当前环境没有 Docker CLI；真实 Compose 解析由 Runtime Acceptance 覆盖")

    command = ["docker", "compose"]
    for compose_file in compose_files:
        command.extend(["-f", str(compose_file)])
    command.extend(["--env-file", str(env_file), "config", "--format", "json"])

    environment = os.environ.copy()
    environment.pop("AIMA_DOCKER_SUBNET", None)
    environment.pop("AIMA_DOCKER_GATEWAY", None)
    environment.update(overrides or {})

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    rendered = json.loads(result.stdout)
    return rendered["networks"]["app"]


def test_canonical_compose_network_has_configurable_ipam() -> None:
    """固定 canonical app bridge 的默认 IPAM，并保留环境覆盖入口。"""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    assert "ipam:" in compose
    assert "subnet: ${AIMA_DOCKER_SUBNET:-10.1.1.0/24}" in compose
    assert "gateway: ${AIMA_DOCKER_GATEWAY:-10.1.1.1}" in compose
    assert "AIMA_DOCKER_SUBNET=10.1.1.0/24" in env_example
    assert "AIMA_DOCKER_GATEWAY=10.1.1.1" in env_example


def test_compose_network_keeps_service_dns_and_windows_single_source() -> None:
    """保持 service DNS 与 Windows storage-only override 的单一网络事实源。"""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    windows_compose = (ROOT / "compose.windows.yaml").read_text(encoding="utf-8")

    assert "AIMA_DB_HOST=postgres" in compose
    assert "network_mode: none" in compose
    assert "ipv4_address:" not in compose
    assert "internal: true" not in compose
    assert "\nnetworks:" not in windows_compose


def test_docker_compose_renders_default_override_and_windows_network(tmp_path: Path) -> None:
    """验证默认 IPAM、环境覆盖和 Windows merge 都由真实 Compose parser 正确渲染。"""
    env_file = _write_env_without_network(tmp_path)
    canonical_files = (ROOT / "compose.yaml",)
    windows_files = (ROOT / "compose.yaml", ROOT / "compose.windows.yaml")

    default_network = _render_app_network(env_file, canonical_files)
    default_config = default_network["ipam"]["config"][0]
    assert default_config["subnet"] == "10.1.1.0/24"
    assert default_config["gateway"] == "10.1.1.1"

    override = {
        "AIMA_DOCKER_SUBNET": "10.77.88.0/24",
        "AIMA_DOCKER_GATEWAY": "10.77.88.1",
    }
    override_network = _render_app_network(env_file, canonical_files, overrides=override)
    override_config = override_network["ipam"]["config"][0]
    assert override_config["subnet"] == "10.77.88.0/24"
    assert override_config["gateway"] == "10.77.88.1"

    windows_network = _render_app_network(env_file, windows_files, overrides=override)
    windows_config = windows_network["ipam"]["config"][0]
    assert windows_config["subnet"] == "10.77.88.0/24"
    assert windows_config["gateway"] == "10.77.88.1"
