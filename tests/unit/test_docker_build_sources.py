from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docker_image_references_use_official_canonical_names() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    expected_dockerfile_defaults = (
        "ARG AIMA_BUILD_PYTHON_IMAGE=python:3.14.7-slim-trixie",
        "ARG AIMA_BUILD_UV_IMAGE=ghcr.io/astral-sh/uv:0.12.3",
        "ARG AIMA_BUILD_NODE_IMAGE=node:24.19.0-bookworm-slim",
        "ARG AIMA_BUILD_NGINX_IMAGE=nginx:1.30.4-alpine3.24",
    )
    for expected in expected_dockerfile_defaults:
        assert expected in dockerfile

    assert "image: postgres:18.4" in compose
    assert "docker.1ms.run" not in dockerfile
    assert "ghcr.1ms.run" not in dockerfile
    assert "docker.1ms.run" not in compose
    assert "ghcr.1ms.run" not in compose

    # env.production 不再把容器镜像 registry 当成机器配置；镜像身份由仓库固定为官方引用。
    for key in (
        "AIMA_BUILD_PYTHON_IMAGE=",
        "AIMA_BUILD_UV_IMAGE=",
        "AIMA_BUILD_NODE_IMAGE=",
        "AIMA_BUILD_NGINX_IMAGE=",
        "AIMA_POSTGRES_IMAGE=",
    ):
        assert key not in env_example


def test_package_source_defaults_are_official_but_remain_overridable() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    official_defaults = (
        "AIMA_BUILD_DEBIAN_MIRROR=http://deb.debian.org/debian",
        "AIMA_BUILD_DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security",
        "AIMA_BUILD_PYPI_INDEX=https://pypi.org/simple",
        "AIMA_BUILD_NPM_REGISTRY=https://registry.npmjs.org",
    )
    for expected in official_defaults:
        assert expected in dockerfile
        assert expected in env_example

    assert "${AIMA_BUILD_DEBIAN_MIRROR:-http://deb.debian.org/debian}" in compose
    assert "${AIMA_BUILD_DEBIAN_SECURITY_MIRROR:-http://deb.debian.org/debian-security}" in compose
    assert "${AIMA_BUILD_PYPI_INDEX:-https://pypi.org/simple}" in compose
    assert "${AIMA_BUILD_NPM_REGISTRY:-https://registry.npmjs.org}" in compose
