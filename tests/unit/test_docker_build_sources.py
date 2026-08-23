from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKER_HUB_MIRRORS = (
    "https://docker.1panel.live",
    "https://hub.1panel.dev",
    "https://docker.m.daocloud.io",
)


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

    for third_party_registry in (
        "docker.1ms.run",
        "docker.1panel.live",
        "hub.1panel.dev",
        "docker.m.daocloud.io",
    ):
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
    assert (
        "${AIMA_BUILD_PYPI_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}" in compose
    )
    assert "${AIMA_BUILD_NPM_REGISTRY:-https://registry.npmmirror.com}" in compose


def test_environment_setup_configures_multiple_docker_hub_mirrors() -> None:
    linux_setup = (ROOT / "scripts" / "setup_dev_environment.sh").read_text(
        encoding="utf-8"
    )
    windows_cmd = (ROOT / "scripts" / "setup_dev_environment.cmd").read_text(
        encoding="utf-8"
    )
    windows_mirror_setup_path = (
        ROOT / "scripts" / "dev" / "configure_docker_desktop_mirrors.ps1"
    )

    assert windows_mirror_setup_path.is_file()
    windows_mirror_setup = windows_mirror_setup_path.read_text(encoding="utf-8")
    for mirror in DOCKER_HUB_MIRRORS:
        assert mirror in linux_setup
        assert mirror in windows_mirror_setup

    assert "DOCKER_REGISTRY_MIRRORS=(" in linux_setup
    assert '"max-download-attempts":5' in linux_setup
    assert "configure_docker_desktop_mirrors.ps1" in windows_cmd
    assert "max-download-attempts" in windows_mirror_setup
    assert "docker info" in windows_mirror_setup
    assert "docker.1ms.run" not in linux_setup
    assert "docker.1ms.run" not in windows_mirror_setup
