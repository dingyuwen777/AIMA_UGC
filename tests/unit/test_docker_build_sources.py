from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_docker_image_references_are_fixed_to_official_canonical_names() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    expected_dockerfile_images = (
        "FROM ghcr.io/astral-sh/uv:0.12.3 AS uv-bin",
        "FROM python:3.14.7-slim-trixie AS backend-builder",
        "FROM python:3.14.7-slim-trixie AS backend",
        "FROM node:24.19.0-bookworm-slim AS frontend-builder",
        "FROM nginx:1.30.4-alpine3.24 AS frontend",
    )
    for expected in expected_dockerfile_images:
        assert expected in dockerfile

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

    for third_party_registry in ("docker.1ms.run", "ghcr.1ms.run"):
        assert third_party_registry not in dockerfile
        assert third_party_registry not in compose
        assert third_party_registry not in env_example


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
