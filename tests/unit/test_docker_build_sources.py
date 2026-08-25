from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DOCKER_HUB_MIRROR_CONFIG = ROOT / "scripts" / "config" / "docker_hub_mirrors.txt"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


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


def test_release_workflow_uses_official_upstreams_without_changing_local_defaults() -> None:
    assert RELEASE_WORKFLOW.is_file(), "Release workflow has not been implemented yet"
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    # Release keeps its official GitHub-Runner sources together in workflow-level YAML env.
    official_release_sources = (
        "AIMA_BUILD_DEBIAN_MIRROR: http://deb.debian.org/debian",
        "AIMA_BUILD_DEBIAN_SECURITY_MIRROR: http://deb.debian.org/debian-security",
        "AIMA_BUILD_PYPI_INDEX: https://pypi.org/simple",
        "AIMA_BUILD_NPM_REGISTRY: https://registry.npmjs.org",
        "POSTGRES_IMAGE: postgres:18.4",
    )
    for expected in official_release_sources:
        assert expected in workflow

    forbidden_release_sources = (
        "mirrors.aliyun.com",
        "pypi.tuna.tsinghua.edu.cn",
        "registry.npmmirror.com",
        "docker.m.daocloud.io",
    )
    for forbidden in forbidden_release_sources:
        assert forbidden not in workflow

    # Local source defaults stay in Dockerfile/Compose; Release only overrides build args.
    assert "--build-arg AIMA_BUILD_DEBIAN_MIRROR=" in workflow
    assert "--build-arg AIMA_BUILD_PYPI_INDEX=" in workflow
    assert "--build-arg AIMA_BUILD_NPM_REGISTRY=" in workflow


def test_release_workflow_builds_a_replayable_offline_bundle() -> None:
    assert RELEASE_WORKFLOW.is_file(), "Release workflow has not been implemented yet"
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    required_markers = (
        "workflow_dispatch:",
        "version:",
        "refs/heads/main",
        "^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$",
        "linux/amd64",
        "ghcr.io/dingyuwen777/aima-ugc-backend",
        "ghcr.io/dingyuwen777/aima-ugc-frontend",
        "docker save",
        "release-bundle/images.tar",
        "docker load -i release-bundle/images.tar",
        "--no-build",
        "--pull never",
        "release-manifest.json",
        "migration-manifest.json",
        "SHA256SUMS",
        "DEPLOY.md",
        "gh release create",
        '--target "${RELEASE_SHA}"',
    )
    for marker in required_markers:
        assert marker in workflow

    assert "compose.windows.yaml" not in workflow
    assert "AIMA_TIKHUB_API_KEY" not in workflow
    assert "AIMA_LLM_API_KEY" not in workflow
    assert "docker compose down -v" not in workflow


def test_release_pull_request_dry_run_has_no_repository_write_token() -> None:
    assert RELEASE_WORKFLOW.is_file(), "Release workflow has not been implemented yet"
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    header, jobs = workflow.split("jobs:", 1)

    assert "contents: write" not in header
    assert "packages: write" not in header
    assert "contents: read" in header

    assert "publish-release:" in jobs
    publish_job = jobs.split("publish-release:", 1)[1]
    assert "if: github.event_name == 'workflow_dispatch'" in publish_job
    assert "permissions:" in publish_job
    assert "contents: write" in publish_job
    assert "packages: write" in publish_job


def test_environment_setup_uses_one_docker_hub_mirror_source_of_truth() -> None:
    mirrors = _docker_hub_mirrors()
    linux_setup = (ROOT / "scripts" / "setup_dev_environment.sh").read_text(encoding="utf-8")
    windows_cmd = (ROOT / "scripts" / "setup_dev_environment.cmd").read_text(encoding="utf-8")
    windows_mirror_setup_path = ROOT / "scripts" / "dev" / "configure_docker_desktop_mirrors.ps1"
    windows_guide = (
        ROOT / "docs" / "guides" / "03_Windows Docker Desktop Compose运行.md"
    ).read_text(encoding="utf-8")
    docker_guide = (ROOT / "docs" / "guides" / "04_Docker国内构建源与本地重置.md").read_text(
        encoding="utf-8"
    )

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


def test_windows_mirror_setup_validates_effective_state_with_bounded_waits() -> None:
    mirror_setup = (ROOT / "scripts" / "dev" / "configure_docker_desktop_mirrors.ps1").read_text(
        encoding="utf-8"
    )

    assert "$DockerDesktopRestartTimeoutSeconds = 60" in mirror_setup
    assert "$MirrorVerificationTimeoutSeconds = 20" in mirror_setup
    assert "$MirrorProbeTimeoutSeconds = 3" in mirror_setup
    assert "$MirrorProbeCleanupTimeoutMilliseconds = 1000" in mirror_setup
    assert "$MirrorVerificationIntervalSeconds = 1" in mirror_setup
    assert "function Get-DockerRegistryMirrorProbe" in mirror_setup
    assert "function Test-ExpectedMirrorsPresent" in mirror_setup
    assert "function Test-AimaDaemonConfigMatches" in mirror_setup
    assert "System.Diagnostics.ProcessStartInfo" in mirror_setup
    assert "$startInfo.Arguments = 'info --format " in mirror_setup
    assert '"{{range .RegistryConfig.Mirrors}}{{println .}}{{end}}"\'' in mirror_setup
    assert (
        "ConvertFrom-Json"
        not in mirror_setup.split("function Get-DockerRegistryMirrorProbe", 1)[1].split(
            "function Write-EffectiveMirrorState", 1
        )[0]
    )
    assert "$process.WaitForExit($TimeoutSeconds * 1000)" in mirror_setup
    assert "$process.WaitForExit($MirrorProbeCleanupTimeoutMilliseconds)" in mirror_setup
    assert "$process.WaitForExit()" not in mirror_setup
    assert "[Diagnostics.Stopwatch]::StartNew()" in mirror_setup
    assert "--timeout $DockerDesktopRestartTimeoutSeconds" in mirror_setup
    assert "[WAIT]" in mirror_setup
    assert "additional registry mirrors" in mirror_setup.lower()
    assert "$actual.Count -ne $Mirrors.Count" not in mirror_setup
    assert "$MirrorVerificationAttempts" not in mirror_setup
    assert "Wait-DockerEngineReady" not in mirror_setup
