from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DOCKER_HUB_MIRROR_CONFIG = ROOT / "scripts" / "config" / "docker_hub_mirrors.txt"


def _docker_hub_mirrors() -> tuple[str, ...]:
    assert DOCKER_HUB_MIRROR_CONFIG.is_file()
    mirrors = tuple(
        line
        for raw_line in DOCKER_HUB_MIRROR_CONFIG.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    )
    assert len(mirrors) >= 2
    assert len(mirrors) == len(set(mirrors))
    assert all(mirror.startswith("https://") for mirror in mirrors)
    return mirrors


def test_docker_image_references_are_fixed_to_official_canonical_names() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    expected_dockerfile_images = (
        "FROM python:3.14.7-slim-trixie AS backend-builder",
        "FROM python:3.14.7-slim-trixie AS backend",
        "FROM node:24.19.0-bookworm-slim AS frontend-builder",
        "FROM nginx:1.30.4-alpine3.24 AS frontend",
    )
    for expected in expected_dockerfile_images:
        assert expected in dockerfile

    assert "FROM ghcr.io/" not in dockerfile
    assert '"uv==0.12.3"' in dockerfile
    assert "--only-binary=:all:" in dockerfile
    assert "image: postgres:18.4" in compose

    removed_image_override_keys = (
        "AIMA_BUILD_PYTHON_IMAGE",
        "AIMA_BUILD_UV_IMAGE",
        "AIMA_BUILD_NODE_IMAGE",
        "AIMA_BUILD_NGINX_IMAGE",
        "AIMA_POSTGRES_IMAGE",
    )
    for key in removed_image_override_keys:
        assert key not in dockerfile
        assert key not in compose
        assert key not in env_example

    third_party_registries = (
        "docker.1ms.run",
        *(urlparse(mirror).netloc for mirror in _docker_hub_mirrors()),
    )
    for third_party_registry in third_party_registries:
        assert third_party_registry not in dockerfile
        assert third_party_registry not in compose
        assert third_party_registry not in env_example


def test_package_source_defaults_use_china_mirrors_but_remain_overridable() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    domestic_defaults = (
        "AIMA_BUILD_DEBIAN_MIRROR=https://mirrors.aliyun.com/debian",
        "AIMA_BUILD_DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security",
        "AIMA_BUILD_PYPI_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple",
        "AIMA_BUILD_NPM_REGISTRY=https://registry.npmmirror.com",
    )
    for expected in domestic_defaults:
        assert expected in dockerfile
        assert expected in env_example

    assert "${AIMA_BUILD_DEBIAN_MIRROR:-https://mirrors.aliyun.com/debian}" in compose
    assert (
        "${AIMA_BUILD_DEBIAN_SECURITY_MIRROR:-https://mirrors.aliyun.com/debian-security}"
        in compose
    )
    assert "${AIMA_BUILD_PYPI_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}" in compose
    assert "${AIMA_BUILD_NPM_REGISTRY:-https://registry.npmmirror.com}" in compose


def test_environment_setup_uses_one_docker_hub_mirror_source_of_truth() -> None:
    mirrors = _docker_hub_mirrors()
    linux_setup = (ROOT / "scripts" / "setup_dev_environment.sh").read_text(encoding="utf-8")
    windows_cmd = (ROOT / "scripts" / "setup_dev_environment.cmd").read_text(encoding="utf-8")
    windows_mirror_setup_path = ROOT / "scripts" / "dev" / "configure_docker_desktop_mirrors.ps1"
    windows_guide = (
        ROOT / "docs" / "guides" / "03_Windows Docker Desktop Compose运行.md"
    ).read_text(encoding="utf-8")
    docker_guide = (
        ROOT / "docs" / "guides" / "04_Docker国内构建源与本地重置.md"
    ).read_text(encoding="utf-8")

    assert windows_mirror_setup_path.is_file()
    windows_mirror_setup = windows_mirror_setup_path.read_text(encoding="utf-8")

    assert 'DOCKER_MIRROR_CONFIG="${SCRIPT_DIR}/config/docker_hub_mirrors.txt"' in linux_setup
    assert "config\\docker_hub_mirrors.txt" in windows_mirror_setup
    assert "configure_docker_desktop_mirrors.ps1" in windows_cmd
    assert '"max-download-attempts":5' in linux_setup
    assert "max-download-attempts" in windows_mirror_setup
    assert "docker info" in windows_mirror_setup
    assert "docker desktop restart" in windows_mirror_setup

    for mirror in mirrors:
        assert mirror not in linux_setup
        assert mirror not in windows_mirror_setup
        assert mirror not in windows_guide
        assert mirror not in docker_guide

    assert "scripts/config/docker_hub_mirrors.txt" in windows_guide
    assert "scripts/config/docker_hub_mirrors.txt" in docker_guide
    assert "docker.1ms.run" not in linux_setup
    assert "docker.1ms.run" not in windows_mirror_setup


def test_windows_mirror_setup_retries_until_registry_mirrors_are_applied() -> None:
    mirror_setup = (ROOT / "scripts" / "dev" / "configure_docker_desktop_mirrors.ps1").read_text(
        encoding="utf-8"
    )

    assert "$MirrorVerificationAttempts = 60" in mirror_setup
    assert "$MirrorVerificationIntervalSeconds = 2" in mirror_setup
    assert "function Wait-ExpectedMirrorsApplied" in mirror_setup
    assert (
        "for ($attempt = 1; $attempt -le $MirrorVerificationAttempts; $attempt++)" in mirror_setup
    )
    assert "if (Test-ExpectedMirrorsApplied)" in mirror_setup
    assert "Start-Sleep -Seconds $MirrorVerificationIntervalSeconds" in mirror_setup
    assert (
        "Wait-ExpectedMirrorsApplied -BackupPath $backupPath -ConfigPath $configPath"
        in mirror_setup
    )
    assert "Wait-DockerEngineReady" not in mirror_setup
