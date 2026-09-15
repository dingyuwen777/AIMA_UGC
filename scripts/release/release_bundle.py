#!/usr/bin/env python3
"""构建、校验并最终化 AIMA_UGC 离线 Release Bundle。"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

POSTGRES_IMAGE = "postgres:18.4"
PLATFORM = "linux/amd64"
FORMAL_VERSION_PATTERN = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
LOCAL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
EXPECTED_BUNDLE_ENTRIES = frozenset(
    {
        "DEPLOY.md",
        "SHA256SUMS",
        "compose.yaml",
        "env.production.example",
        "images.tar",
        "migration-manifest.json",
        "release-manifest.json",
    }
)
CHECKSUM_TARGETS = (
    "images.tar",
    "compose.yaml",
    "env.production.example",
    "release-manifest.json",
    "migration-manifest.json",
    "DEPLOY.md",
)
DISABLED_SMOKE_RUNTIME_KEYS = frozenset(
    {
        "AIMA_LLM_BASE_URL",
        "AIMA_LLM_PROVIDER_NAME",
        "AIMA_LLM_MODEL",
    }
)

SOURCE_PROFILES: Mapping[str, Mapping[str, str]] = {
    "china": {
        "debian": "https://mirrors.aliyun.com/debian",
        "debian_security": "https://mirrors.aliyun.com/debian-security",
        "pypi": "https://pypi.tuna.tsinghua.edu.cn/simple",
        "npm": "https://registry.npmmirror.com",
    },
    "official": {
        "debian": "http://deb.debian.org/debian",
        "debian_security": "http://deb.debian.org/debian-security",
        "pypi": "https://pypi.org/simple",
        "npm": "https://registry.npmjs.org",
    },
}


class ReleaseBundleError(RuntimeError):
    """表示 Release Bundle 构建、校验或回放失败。"""


@dataclass(frozen=True)
class ImageFacts:
    """保存离线 Bundle 需要冻结的镜像和 Schema 身份。"""

    backend_id: str
    frontend_id: str
    postgres_ref: str
    alembic_head: str
    openapi_sha256: str


def _format_command(arguments: Sequence[str]) -> str:
    """生成不包含环境变量值的可读命令日志。"""
    return " ".join(arguments)


def _run(arguments: Sequence[str], *, cwd: Path, capture: bool = False) -> str:
    """执行外部命令，并把失败转换成稳定的 Release Bundle 错误。"""
    print(f"> {_format_command(arguments)}", flush=True)
    try:
        result = subprocess.run(
            list(arguments),
            cwd=cwd,
            check=False,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ReleaseBundleError(f"无法执行命令：{arguments[0]}：{exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() if capture else ""
        raise ReleaseBundleError(
            f"命令失败（exit={result.returncode}）：{_format_command(arguments)}"
            + (f"\n{detail}" if detail else "")
        )
    return result.stdout if capture else ""


def _git(root: Path, *arguments: str) -> str:
    """读取当前仓库 Git 事实。"""
    return _run(["git", *arguments], cwd=root, capture=True).strip()


def _require_tool(name: str) -> None:
    """确认本机存在 Release 构建所需命令。"""
    if shutil.which(name) is None:
        raise ReleaseBundleError(f"缺少必需命令：{name}")


def validate_version(version: str, *, formal: bool) -> None:
    """校验 Docker tag 与正式 SemVer 版本约束。"""
    pattern = FORMAL_VERSION_PATTERN if formal else LOCAL_VERSION_PATTERN
    if pattern.fullmatch(version) is None:
        if formal:
            raise ReleaseBundleError("Formal 模式版本号必须使用 vMAJOR.MINOR.PATCH，例如 v3.2.0。")
        raise ReleaseBundleError(
            "本地版本必须是合法 Docker tag，只能使用字母、数字、点、下划线或连字符。"
        )


def source_profile(name: str) -> Mapping[str, str]:
    """返回已确认的构建下载源 Profile。"""
    try:
        return SOURCE_PROFILES[name]
    except KeyError as exc:
        raise ReleaseBundleError(f"未知 build source profile：{name}") from exc


def validate_formal_checkout(root: Path) -> str:
    """Formal 本地构建只允许干净且与最新 origin/main 一致的 main。"""
    _require_tool("git")
    if _git(root, "status", "--porcelain"):
        raise ReleaseBundleError("Formal 模式要求 Git 工作区干净。")
    branch = _git(root, "branch", "--show-current")
    if branch != "main":
        raise ReleaseBundleError(
            f"Formal 模式只能从 main 构建；当前分支={branch or '<detached>'}。"
        )
    _run(["git", "fetch", "--quiet", "origin", "main"], cwd=root)
    head = _git(root, "rev-parse", "HEAD")
    remote_main = _git(root, "rev-parse", "refs/remotes/origin/main")
    if head != remote_main:
        raise ReleaseBundleError(
            "Formal 模式要求本地 HEAD 等于最新 origin/main；"
            f"HEAD={head}, origin/main={remote_main}。"
        )
    return head


def resolve_git_sha(root: Path, explicit_sha: str | None, *, formal: bool) -> str:
    """解析 Bundle 要记录的 Git SHA，并执行 Formal checkout 门禁。"""
    if formal:
        formal_sha = validate_formal_checkout(root)
        if explicit_sha is not None and explicit_sha != formal_sha:
            raise ReleaseBundleError("显式 Git SHA 与 Formal checkout HEAD 不一致。")
        return formal_sha
    if explicit_sha:
        return explicit_sha
    _require_tool("git")
    return _git(root, "rev-parse", "HEAD")


def detect_repository(root: Path, explicit_repository: str | None) -> str:
    """解析 manifest 中的仓库身份；无法识别 GitHub URL 时保留本地仓库名。"""
    if explicit_repository:
        return explicit_repository
    try:
        origin = _git(root, "remote", "get-url", "origin")
    except ReleaseBundleError:
        return root.name
    normalized = origin.removesuffix(".git")
    match = re.search(r"github\.com[:/](?P<name>[^/]+/[^/]+)$", normalized)
    return match.group("name") if match is not None else root.name


def _sha256_file(path: Path) -> str:
    """计算单个文件的 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_env_values(
    source: Path,
    destination: Path,
    replacements: Mapping[str, str],
    *,
    drop_keys: frozenset[str] = frozenset(),
) -> None:
    """按 key 精确重写 env 模板，并对必需 replacement 失败关闭。"""
    output: list[str] = []
    seen: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("#") else None
        if key in drop_keys:
            continue
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            output.append(line)
    missing = set(replacements) - seen
    if missing:
        raise ReleaseBundleError(f"env 模板缺少必需字段：{sorted(missing)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(output) + "\n", encoding="utf-8")


def _docker_inspect_json(root: Path, image: str, template: str) -> Any:
    """读取 Docker inspect 的 JSON 模板输出。"""
    raw = _run(
        ["docker", "image", "inspect", image, "--format", template],
        cwd=root,
        capture=True,
    ).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReleaseBundleError(f"无法解析 Docker inspect JSON：{image}") from exc


def build_images(root: Path, version: str, profile_name: str) -> None:
    """按指定下载源 Profile 构建 Linux/AMD64 应用镜像并准备 PostgreSQL。"""
    _require_tool("docker")
    profile = source_profile(profile_name)
    _run(["docker", "version"], cwd=root)
    _run(["docker", "compose", "version"], cwd=root)
    _run(
        [
            "docker",
            "build",
            "--pull",
            "--platform",
            PLATFORM,
            "--target",
            "backend",
            "--build-arg",
            f"AIMA_BUILD_DEBIAN_MIRROR={profile['debian']}",
            "--build-arg",
            f"AIMA_BUILD_DEBIAN_SECURITY_MIRROR={profile['debian_security']}",
            "--build-arg",
            f"AIMA_BUILD_PYPI_INDEX={profile['pypi']}",
            "-t",
            f"aima-ugc-backend:{version}",
            ".",
        ],
        cwd=root,
    )
    _run(
        [
            "docker",
            "build",
            "--pull",
            "--platform",
            PLATFORM,
            "--target",
            "frontend",
            "--build-arg",
            f"AIMA_BUILD_NPM_REGISTRY={profile['npm']}",
            "-t",
            f"aima-ugc-frontend:{version}",
            ".",
        ],
        cwd=root,
    )
    _run(["docker", "pull", "--platform", PLATFORM, POSTGRES_IMAGE], cwd=root)


def collect_image_facts(root: Path, version: str) -> ImageFacts:
    """冻结应用镜像、PostgreSQL digest、Alembic head 与 OpenAPI hash。"""
    backend = f"aima-ugc-backend:{version}"
    frontend = f"aima-ugc-frontend:{version}"
    backend_id = _run(
        ["docker", "image", "inspect", "-f", "{{.Id}}", backend],
        cwd=root,
        capture=True,
    ).strip()
    frontend_id = _run(
        ["docker", "image", "inspect", "-f", "{{.Id}}", frontend],
        cwd=root,
        capture=True,
    ).strip()
    repo_digests = _docker_inspect_json(root, POSTGRES_IMAGE, "{{json .RepoDigests}}")
    if not isinstance(repo_digests, list):
        raise ReleaseBundleError("PostgreSQL RepoDigests 不是数组。")
    postgres_ref = next(
        (
            item
            for item in repo_digests
            if isinstance(item, str) and item.startswith("postgres@sha256:")
        ),
        "",
    )
    if not postgres_ref:
        raise ReleaseBundleError("无法获得官方 PostgreSQL 18.4 镜像 digest。")
    heads_output = _run(
        ["docker", "run", "--rm", backend, "alembic", "heads"],
        cwd=root,
        capture=True,
    )
    heads = [line.split()[0] for line in heads_output.splitlines() if line.strip()]
    if len(heads) != 1 or not heads[0]:
        raise ReleaseBundleError(f"Release 只支持当前单 Alembic head；实际 heads={heads}")
    openapi_path = root / "contracts" / "openapi" / "openapi.json"
    if not openapi_path.is_file():
        raise ReleaseBundleError(f"缺少 OpenAPI 机器事实：{openapi_path}")
    return ImageFacts(
        backend_id=backend_id,
        frontend_id=frontend_id,
        postgres_ref=postgres_ref,
        alembic_head=heads[0],
        openapi_sha256=_sha256_file(openapi_path),
    )


def _release_manifest(
    *,
    version: str,
    repository: str,
    git_sha: str,
    profile_name: str,
    builder_context: str,
    facts: ImageFacts,
    offline_replay: bool,
    strict_replay: bool,
) -> dict[str, Any]:
    """生成 Bundle 的 Release manifest。"""
    profile = source_profile(profile_name)
    return {
        "schema_version": 1,
        "version": version,
        "repository": repository,
        "git_sha": git_sha,
        "built_at": datetime.now(UTC).isoformat(),
        "platform": PLATFORM,
        "builder_context": builder_context,
        "build_source_profile": profile_name,
        "deployment": {
            "mode": "offline-docker-compose",
            "compose_file": "compose.yaml",
            "server_build_required": False,
            "server_pull_required": False,
            "persistent_root": "/data/AIMA_UGC",
        },
        "build_upstreams": {
            "docker": "Docker Hub canonical image references",
            "debian": profile["debian"],
            "debian_security": profile["debian_security"],
            "pypi": profile["pypi"],
            "npm": profile["npm"],
        },
        "images": {
            "backend": {
                "offline_tag": f"aima-ugc-backend:{version}",
                "local_image_id": facts.backend_id,
                "registry_ref": None,
            },
            "frontend": {
                "offline_tag": f"aima-ugc-frontend:{version}",
                "local_image_id": facts.frontend_id,
                "registry_ref": None,
            },
            "postgres": {
                "offline_tag": POSTGRES_IMAGE,
                "registry_ref": facts.postgres_ref,
            },
        },
        "schema": {
            "alembic_head": facts.alembic_head,
            "openapi_sha256": facts.openapi_sha256,
        },
        "verification": {
            "offline_replay": offline_replay,
            "strict_replay": strict_replay if offline_replay else False,
        },
        "integrity": {
            "sha256sums": True,
            "sbom": "not_included_in_this_release_workflow_mvp",
            "independent_signature": "not_included_in_this_release_workflow_mvp",
        },
        "publication": {"github_release": False, "ghcr": False},
    }


def _migration_manifest(version: str, git_sha: str, alembic_head: str) -> dict[str, Any]:
    """生成 Bundle 的 Migration manifest。"""
    return {
        "schema_version": 1,
        "version": version,
        "git_sha": git_sha,
        "alembic_head": alembic_head,
        "upgrade_command": "alembic upgrade head",
        "migration_process": "compose service: migrate",
        "automatic_schema_rollback": False,
        "coordinated_backup_restore": "not_implemented_in_this_release_workflow_mvp",
        "rollback_note": (
            "应用回滚前必须确认目标版本 Migration 兼容性；"
            "当前 Release Builder 不提供数据库自动回滚或协调 Backup/Restore。"
        ),
    }


def _deploy_markdown(version: str) -> str:
    """生成服务器离线部署说明。"""
    return f"""# AIMA_UGC {version} 离线部署

本目录包含已构建的 Linux/AMD64 Backend、Frontend 和 PostgreSQL 18.4 镜像。
服务器不需要重新 build，也不需要从 Docker Hub/GHCR 拉取运行镜像。
是否执行过离线回放验证，以 `release-manifest.json` 的 `verification.offline_replay` 为准；
正式 GitHub Release 会要求该值为 `true`。

## 1. 校验并导入镜像

```bash
sha256sum -c SHA256SUMS
docker load -i images.tar
```

## 2. 准备运行配置

```bash
cp env.production.example env.production
chmod 0600 env.production
```

编辑 `env.production`：公司服务器保持 `AIMA_HOST_ROOT=/data/AIMA_UGC`，
并按实际内网地址、TikHub/LLM 配置填写机器配置。
真实 `env.production` 属于敏感文件，不得提交 Git 或放回 Release 包。

## 3. 启动

```bash
docker compose --env-file env.production config --quiet
docker compose --env-file env.production up -d --no-build --pull never --wait
```

`--no-build --pull never` 是 Release 部署门禁：只运行本包已经导入的镜像。
PostgreSQL、Artifact、日志和内部 Secret 始终保存在 `AIMA_HOST_ROOT`，不属于 Release 生命周期。

## 4. 验证

```bash
docker compose --env-file env.production ps -a
docker compose --env-file env.production exec -T frontend \
  wget -qO- http://127.0.0.1:8080/health/ready
```

不要删除 `AIMA_HOST_ROOT`，不要用带 `-v` 的 Compose 清理命令处理真实业务环境。
当前 Release Builder 不提供 PostgreSQL + Artifact 协调 Backup/Restore 或数据库自动回滚；
有 Migration 的升级仍需按正式备份/回滚策略执行。
"""


def write_bundle_checksums(bundle_dir: Path) -> None:
    """按稳定顺序重建 Bundle 内 SHA256SUMS。"""
    lines: list[str] = []
    for name in CHECKSUM_TARGETS:
        path = bundle_dir / name
        if not path.is_file():
            raise ReleaseBundleError(f"Bundle 缺少 checksum 输入：{name}")
        lines.append(f"{_sha256_file(path)}  {name}")
    (bundle_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_bundle(bundle_dir: Path) -> None:
    """校验 Bundle 文件集合和 SHA256SUMS。"""
    if not bundle_dir.is_dir():
        raise ReleaseBundleError(f"Bundle 目录不存在：{bundle_dir}")
    actual = {path.name for path in bundle_dir.iterdir()}
    if actual != EXPECTED_BUNDLE_ENTRIES:
        raise ReleaseBundleError(f"Release bundle entries mismatch: actual={sorted(actual)}")
    checksum_path = bundle_dir / "SHA256SUMS"
    for raw_line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            expected, name = raw_line.split("  ", 1)
        except ValueError as exc:
            raise ReleaseBundleError(f"无法解析 SHA256SUMS 行：{raw_line}") from exc
        target = bundle_dir / name
        if not target.is_file():
            raise ReleaseBundleError(f"SHA256SUMS 指向不存在文件：{name}")
        actual_hash = _sha256_file(target)
        if actual_hash != expected:
            raise ReleaseBundleError(
                f"SHA256 校验失败：{name} expected={expected} actual={actual_hash}"
            )


def verify_manifest_identity(
    bundle_dir: Path,
    *,
    expected_version: str | None = None,
    expected_git_sha: str | None = None,
    expected_profile: str | None = None,
    require_offline_replay: bool = False,
    require_strict_replay: bool = False,
) -> None:
    """校验候选 Bundle 的版本、revision、下载源 Profile 与回放证据。"""
    path = bundle_dir / "release-manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseBundleError(f"无法读取 release-manifest.json：{path}") from exc
    if not isinstance(manifest, dict):
        raise ReleaseBundleError("release-manifest.json 根节点必须是对象。")
    expected = {
        "version": expected_version,
        "git_sha": expected_git_sha,
        "build_source_profile": expected_profile,
    }
    for key, value in expected.items():
        if value is not None and manifest.get(key) != value:
            raise ReleaseBundleError(
                f"Release manifest {key} 不匹配：expected={value}, actual={manifest.get(key)}"
            )
    verification = manifest.get("verification")
    if require_offline_replay:
        if not isinstance(verification, dict) or verification.get("offline_replay") is not True:
            raise ReleaseBundleError("Release manifest 缺少 offline replay 成功证据。")
    if require_strict_replay:
        if not isinstance(verification, dict) or verification.get("strict_replay") is not True:
            raise ReleaseBundleError("Release manifest 缺少 strict replay 成功证据。")


def create_archive(bundle_dir: Path, archive_path: Path) -> None:
    """把 Bundle 文件直接打入 gzip tar 根目录，并验证可重新读取。"""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz", compresslevel=1) as archive:
        for path in sorted(bundle_dir.iterdir(), key=lambda item: item.name):
            archive.add(path, arcname=path.name, recursive=False)
    if not archive_path.is_file() or archive_path.stat().st_size <= 0:
        raise ReleaseBundleError(f"部署压缩包为空：{archive_path}")
    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())
    if names != EXPECTED_BUNDLE_ENTRIES:
        raise ReleaseBundleError(f"部署压缩包文件集合不匹配：actual={sorted(names)}")


def build_bundle_files(
    *,
    root: Path,
    bundle_dir: Path,
    archive_path: Path,
    version: str,
    repository: str,
    git_sha: str,
    profile_name: str,
    builder_context: str,
    facts: ImageFacts,
    offline_replay: bool,
    strict_replay: bool,
) -> None:
    """写入离线镜像、配置、manifest、说明、校验和与压缩包。"""
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    shutil.copy2(root / "compose.yaml", bundle_dir / "compose.yaml")
    _replace_env_values(
        root / "env.production.example",
        bundle_dir / "env.production.example",
        {"AIMA_IMAGE_TAG": version},
    )
    _run(
        [
            "docker",
            "save",
            "-o",
            str(bundle_dir / "images.tar"),
            f"aima-ugc-backend:{version}",
            f"aima-ugc-frontend:{version}",
            POSTGRES_IMAGE,
        ],
        cwd=root,
    )
    if (bundle_dir / "images.tar").stat().st_size <= 0:
        raise ReleaseBundleError("images.tar 为空。")
    release_manifest = _release_manifest(
        version=version,
        repository=repository,
        git_sha=git_sha,
        profile_name=profile_name,
        builder_context=builder_context,
        facts=facts,
        offline_replay=offline_replay,
        strict_replay=strict_replay,
    )
    migration_manifest = _migration_manifest(version, git_sha, facts.alembic_head)
    (bundle_dir / "release-manifest.json").write_text(
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (bundle_dir / "migration-manifest.json").write_text(
        json.dumps(migration_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (bundle_dir / "DEPLOY.md").write_text(_deploy_markdown(version), encoding="utf-8")
    write_bundle_checksums(bundle_dir)
    verify_bundle(bundle_dir)
    create_archive(bundle_dir, archive_path)


def _find_free_port() -> int:
    """选择仅供本次 smoke 使用的空闲本地端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _find_free_smoke_network(root: Path) -> tuple[str, str]:
    """避开现有 Docker 网段，为本次 smoke 选择独立的 IPv4 /24 网络。"""
    network_ids = [
        line.strip()
        for line in _run(
            ["docker", "network", "ls", "--quiet"], cwd=root, capture=True
        ).splitlines()
        if line.strip()
    ]
    occupied: list[ipaddress.IPv4Network] = []
    if network_ids:
        raw_networks = _run(
            ["docker", "network", "inspect", *network_ids], cwd=root, capture=True
        )
        try:
            networks = json.loads(raw_networks)
        except json.JSONDecodeError as exc:
            raise ReleaseBundleError("无法解析现有 Docker network 信息。") from exc
        for network in networks:
            for config in (network.get("IPAM", {}).get("Config") or []):
                subnet = config.get("Subnet")
                if not subnet:
                    continue
                try:
                    parsed = ipaddress.ip_network(subnet, strict=False)
                except ValueError:
                    continue
                if isinstance(parsed, ipaddress.IPv4Network):
                    occupied.append(parsed)

    for second_octet in range(254, -1, -1):
        for third_octet in range(255, -1, -1):
            candidate = ipaddress.IPv4Network(f"10.{second_octet}.{third_octet}.0/24")
            if not any(candidate.overlaps(existing) for existing in occupied):
                return str(candidate), str(candidate.network_address + 1)
    raise ReleaseBundleError("没有可供离线 smoke 使用的空闲 Docker IPv4 /24 网段。")


def _smoke_env(
    *,
    bundle_dir: Path,
    smoke_root: Path,
    port: int,
    subnet: str,
    gateway: str,
) -> Path:
    """生成只指向临时目录和本地端口的 smoke env。"""
    env_path = smoke_root.parent / f"{smoke_root.name}.env"
    historical_input = smoke_root / "historical-input"
    historical_input.mkdir(parents=True, exist_ok=True)
    _replace_env_values(
        bundle_dir / "env.production.example",
        env_path,
        {
            "AIMA_HTTP_BIND_IP": "127.0.0.1",
            "AIMA_HTTP_PORT": str(port),
            "AIMA_HOST_ROOT": smoke_root.as_posix(),
            "AIMA_HISTORICAL_IMPORT_HOST_ROOT": historical_input.as_posix(),
            "AIMA_HISTORICAL_IMPORT_ROOT": "/data/aima-historical-input",
            "AIMA_DOCKER_SUBNET": subnet,
            "AIMA_DOCKER_GATEWAY": gateway,
            "AIMA_TIKHUB_ENABLED": "false",
        },
        drop_keys=DISABLED_SMOKE_RUNTIME_KEYS,
    )
    return env_path


def _compose_command(
    *,
    root: Path,
    bundle_dir: Path,
    env_path: Path,
    project: str,
    windows_overlay: bool,
) -> list[str]:
    """生成当前宿主对应的离线 smoke Compose 前缀。"""
    command = ["docker", "compose", "-f", str(bundle_dir / "compose.yaml")]
    if windows_overlay:
        overlay = root / "compose.windows.yaml"
        if not overlay.is_file():
            raise ReleaseBundleError("Windows 本地验证缺少 compose.windows.yaml。")
        command.extend(["-f", str(overlay)])
    command.extend(["--env-file", str(env_path), "-p", project])
    return command


def _http_get(url: str) -> None:
    """直连本机 HTTP 端点，避免代理和 HTTPS 环境变量干扰 smoke。"""
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname is None or parsed.port is None:
        raise ReleaseBundleError(f"HTTP smoke URL 非法：{url}")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        if response.status < 200 or response.status >= 400:
            raise ReleaseBundleError(f"HTTP smoke 失败：{url} status={response.status}")
        response.read()
    except (HTTPException, OSError) as exc:
        raise ReleaseBundleError(f"HTTP smoke 失败：{url}：{exc}") from exc
    finally:
        connection.close()


def _cleanup_smoke_root(smoke_root: Path) -> None:
    """只清理本次随机 smoke 根；权限不足时失败关闭且不触碰其他目录。"""
    if not smoke_root.exists():
        return
    try:
        shutil.rmtree(smoke_root)
    except PermissionError as exc:
        raise ReleaseBundleError(
            f"Smoke 临时根包含当前进程无法删除的容器文件：{smoke_root}"
        ) from exc


def replay_bundle(*, root: Path, bundle_dir: Path, version: str, strict_replay: bool) -> None:
    """通过 docker load + no-build/no-pull Compose 验证离线 Bundle。"""
    verify_bundle(bundle_dir)
    windows_overlay = os.name == "nt"
    smoke_parent = Path(tempfile.mkdtemp(prefix="aima-release-smoke-")).resolve()
    smoke_root = smoke_parent / "root"
    smoke_root.mkdir()
    (smoke_root / "postgres").mkdir()
    port = _find_free_port()
    subnet, gateway = _find_free_smoke_network(root)
    env_path = _smoke_env(
        bundle_dir=bundle_dir,
        smoke_root=smoke_root,
        port=port,
        subnet=subnet,
        gateway=gateway,
    )
    project = f"aima-release-smoke-{os.getpid()}"
    compose = _compose_command(
        root=root,
        bundle_dir=bundle_dir,
        env_path=env_path,
        project=project,
        windows_overlay=windows_overlay,
    )
    backend = f"aima-ugc-backend:{version}"
    frontend = f"aima-ugc-frontend:{version}"
    image_refs = (backend, frontend, POSTGRES_IMAGE)
    if strict_replay:
        _run(["docker", "image", "rm", *image_refs], cwd=root)
        for image in image_refs:
            result = subprocess.run(
                ["docker", "image", "inspect", image],
                cwd=root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                raise ReleaseBundleError(
                    f"候选镜像仍可通过 {image} 访问，不能证明离线 Bundle 独立可回放。"
                )
    _run(["docker", "load", "-i", str(bundle_dir / "images.tar")], cwd=root)
    try:
        _run([*compose, "config", "--quiet"], cwd=root)
        _run([*compose, "up", "-d", "--no-build", "--pull", "never", "--wait"], cwd=root)
        for service in ("bootstrap", "migrate", "configure"):
            container_id = _run(
                [*compose, "ps", "-a", "-q", service],
                cwd=root,
                capture=True,
            ).strip()
            if not container_id:
                raise ReleaseBundleError(f"Smoke 缺少容器：{service}")
            exit_code = _run(
                ["docker", "inspect", "-f", "{{.State.ExitCode}}", container_id],
                cwd=root,
                capture=True,
            ).strip()
            if exit_code != "0":
                raise ReleaseBundleError(f"Smoke 服务失败：{service} exit={exit_code}")
        _http_get(f"http://127.0.0.1:{port}/health/ready")
        _http_get(f"http://127.0.0.1:{port}/")
        if not windows_overlay:
            postgres_dir = smoke_root / "postgres" / "18" / "docker"
            if not postgres_dir.is_dir():
                raise ReleaseBundleError(f"Smoke PostgreSQL 持久目录不存在：{postgres_dir}")
        api_log = smoke_root / "runtime" / "logs" / "api.log"
        if not api_log.is_file() or api_log.stat().st_size <= 0:
            raise ReleaseBundleError(f"Smoke API 日志不存在或为空：{api_log}")
    except Exception:
        subprocess.run([*compose, "ps", "-a"], cwd=root, check=False)
        subprocess.run([*compose, "logs", "--no-color"], cwd=root, check=False)
        raise
    finally:
        subprocess.run([*compose, "down", "--remove-orphans", "-v"], cwd=root, check=False)
        env_path.unlink(missing_ok=True)
        _cleanup_smoke_root(smoke_root)
        try:
            smoke_parent.rmdir()
        except OSError as exc:
            raise ReleaseBundleError(f"Smoke 临时父目录清理失败：{smoke_parent}") from exc


def _update_verification(bundle_dir: Path, *, strict_replay: bool) -> None:
    """在成功回放后把 verification 事实写回 manifest 并重建校验和。"""
    path = bundle_dir / "release-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReleaseBundleError("release-manifest.json 根节点必须是对象。")
    manifest["verification"] = {"offline_replay": True, "strict_replay": strict_replay}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_bundle_checksums(bundle_dir)


def build_release(
    *,
    root: Path,
    version: str,
    profile_name: str,
    builder_context: str,
    bundle_dir: Path,
    archive_path: Path,
    explicit_sha: str | None,
    explicit_repository: str | None,
    formal: bool,
    verify: bool,
    strict_replay: bool,
) -> None:
    """执行 Build + Package，并按需执行离线 replay。"""
    root = root.resolve()
    validate_version(version, formal=formal)
    if strict_replay and not verify:
        raise ReleaseBundleError("--strict-replay 必须与 --verify 同时使用。")
    git_sha = resolve_git_sha(root, explicit_sha, formal=formal)
    repository = detect_repository(root, explicit_repository)
    build_images(root, version, profile_name)
    facts = collect_image_facts(root, version)
    bundle_dir = bundle_dir.resolve()
    archive_path = archive_path.resolve()
    build_bundle_files(
        root=root,
        bundle_dir=bundle_dir,
        archive_path=archive_path,
        version=version,
        repository=repository,
        git_sha=git_sha,
        profile_name=profile_name,
        builder_context=builder_context,
        facts=facts,
        offline_replay=False,
        strict_replay=False,
    )
    if verify:
        replay_bundle(
            root=root,
            bundle_dir=bundle_dir,
            version=version,
            strict_replay=strict_replay,
        )
        _update_verification(bundle_dir, strict_replay=strict_replay)
        verify_bundle(bundle_dir)
        create_archive(bundle_dir, archive_path)
    print(f"Bundle: {bundle_dir}")
    print(f"Archive: {archive_path}")
    print(f"Git SHA: {git_sha}")
    print(f"Build source profile: {profile_name}")
    print(f"Offline replay verified: {str(verify).lower()}")


def finalize_publication(
    *,
    bundle_dir: Path,
    archive_path: Path,
    backend_registry_ref: str,
    frontend_registry_ref: str,
) -> None:
    """写入正式 GHCR/Release 发布事实，并通过同一逻辑重建 Bundle archive。"""
    bundle_dir = bundle_dir.resolve()
    verify_bundle(bundle_dir)
    path = bundle_dir / "release-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReleaseBundleError("release-manifest.json 根节点必须是对象。")
    verification = manifest.get("verification")
    if not isinstance(verification, dict) or verification.get("offline_replay") is not True:
        raise ReleaseBundleError("正式发布只能消费已完成 offline replay 的候选 Bundle。")
    images = manifest.get("images")
    if not isinstance(images, dict):
        raise ReleaseBundleError("release-manifest.json 缺少 images。")
    backend = images.get("backend")
    frontend = images.get("frontend")
    if not isinstance(backend, dict) or not isinstance(frontend, dict):
        raise ReleaseBundleError("release-manifest.json 缺少应用镜像记录。")
    backend["registry_ref"] = backend_registry_ref
    frontend["registry_ref"] = frontend_registry_ref
    manifest["publication"] = {
        "github_release": True,
        "ghcr": True,
        "ghcr_visibility": "private",
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_bundle_checksums(bundle_dir)
    verify_bundle(bundle_dir)
    create_archive(bundle_dir, archive_path.resolve())


def _build_parser() -> argparse.ArgumentParser:
    """建立 Release Bundle CLI。"""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="构建离线 Bundle")
    build.add_argument("--root", type=Path, default=Path("."))
    build.add_argument("--version", required=True)
    build.add_argument("--source-profile", choices=tuple(SOURCE_PROFILES), default="china")
    build.add_argument("--builder-context", choices=("local", "github-actions"), default="local")
    build.add_argument("--bundle-dir", type=Path, required=True)
    build.add_argument("--archive-path", type=Path, required=True)
    build.add_argument("--git-sha")
    build.add_argument("--repository")
    build.add_argument("--formal", action="store_true")
    build.add_argument("--verify", action="store_true")
    build.add_argument("--strict-replay", action="store_true")
    verify = subparsers.add_parser("verify", help="校验已有 Bundle 与可选身份约束")
    verify.add_argument("--bundle-dir", type=Path, required=True)
    verify.add_argument("--expected-version")
    verify.add_argument("--expected-git-sha")
    verify.add_argument("--expected-profile", choices=tuple(SOURCE_PROFILES))
    verify.add_argument("--require-offline-replay", action="store_true")
    verify.add_argument("--require-strict-replay", action="store_true")
    finalize = subparsers.add_parser("finalize", help="写入正式发布事实并重建 archive")
    finalize.add_argument("--bundle-dir", type=Path, required=True)
    finalize.add_argument("--archive-path", type=Path, required=True)
    finalize.add_argument("--backend-registry-ref", required=True)
    finalize.add_argument("--frontend-registry-ref", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """解析命令行并执行对应 Release Bundle 动作。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            build_release(
                root=args.root,
                version=args.version,
                profile_name=args.source_profile,
                builder_context=args.builder_context,
                bundle_dir=args.bundle_dir,
                archive_path=args.archive_path,
                explicit_sha=args.git_sha,
                explicit_repository=args.repository,
                formal=args.formal,
                verify=args.verify,
                strict_replay=args.strict_replay,
            )
        elif args.command == "verify":
            bundle_dir = args.bundle_dir.resolve()
            verify_bundle(bundle_dir)
            verify_manifest_identity(
                bundle_dir,
                expected_version=args.expected_version,
                expected_git_sha=args.expected_git_sha,
                expected_profile=args.expected_profile,
                require_offline_replay=args.require_offline_replay,
                require_strict_replay=args.require_strict_replay,
            )
        elif args.command == "finalize":
            finalize_publication(
                bundle_dir=args.bundle_dir,
                archive_path=args.archive_path,
                backend_registry_ref=args.backend_registry_ref,
                frontend_registry_ref=args.frontend_registry_ref,
            )
        else:
            parser.error(f"未知命令：{args.command}")
    except (ReleaseBundleError, OSError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
