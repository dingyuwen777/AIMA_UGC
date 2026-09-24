"""按 Docker Engine 的实际资源生成 Compose override 并启动离线 Release。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

_MIB = 1024 * 1024
_GIB = 1024 * _MIB


def compute_memory_limits(memory_bytes: int) -> dict[str, int]:
    """给常驻服务与启动任务硬上限，并在最坏重叠时保留至少四分之一内存。"""

    if memory_bytes < 6 * _GIB:
        raise RuntimeError("Docker Engine 内存不足 6 GiB，无法安全自动分配 AIMA 服务")
    fractions = {
        "postgres": 0.28,
        "worker": 0.20,
        "api": 0.10,
        "scheduler": 0.04,
        "frontend": 0.04,
    }
    minimums = {
        "postgres": 1024,
        "worker": 512,
        "api": 384,
        "scheduler": 256,
        "frontend": 256,
    }
    limits = {
        service: max(minimums[service], int(memory_bytes * fraction // _MIB))
        for service, fraction in fractions.items()
    }
    one_shot = max(512, int(memory_bytes * 0.08 // _MIB))
    if sum(limits.values()) + one_shot > int(memory_bytes * 0.75 // _MIB):
        raise RuntimeError("Docker Engine 内存不足以保留 25% 宿主机余量")
    limits.update({service: one_shot for service in ("bootstrap", "migrate", "configure")})
    return limits


def compute_cpu_limits(cpu_count: int) -> dict[str, float]:
    """常驻服务与一个启动任务同时运行时保留至少五分之一 CPU。"""

    if cpu_count < 2:
        raise RuntimeError("Docker Engine 少于 2 个可用 CPU，无法安全自动分配 AIMA 服务")
    fractions = {
        "postgres": 0.25,
        "worker": 0.30,
        "api": 0.08,
        "scheduler": 0.03,
        "frontend": 0.04,
    }
    limits = {
        service: int(cpu_count * fraction * 100) / 100 for service, fraction in fractions.items()
    }
    limits.update(
        {
            service: max(0.2, int(cpu_count * 0.08 * 100) / 100)
            for service in ("bootstrap", "migrate", "configure")
        }
    )
    return limits


def render_override(limits_mib: dict[str, int], cpu_limits: dict[str, float]) -> str:
    """只生成非敏感的服务资源覆盖，不持有或复制真实 env 内容。"""

    lines = ["# 由 start_compose.py 自动生成；不要手工维护。", "services:"]
    for service, mib in limits_mib.items():
        lines.extend(
            (f"  {service}:", f"    mem_limit: {mib}m", f"    cpus: {cpu_limits[service]}")
        )
    return "\n".join(lines) + "\n"


def start(*, compose_file: Path, env_file: Path, dry_run: bool = False) -> None:
    """统一离线启动入口；每次部署重新计算，不修改服务器 env。"""

    compose_file = compose_file.resolve(strict=True)
    env_file = env_file.resolve(strict=True)
    docker_info = subprocess.run(
        ["docker", "info", "--format", "{{json .}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(docker_info.stdout)
    memory_bytes = int(info["MemTotal"])
    cpu_count = int(info["NCPU"])
    if memory_bytes <= 0 or cpu_count <= 0:
        raise RuntimeError("Docker Engine 未提供有效的 CPU/内存预算")
    limits = compute_memory_limits(memory_bytes)
    cpu_limits = compute_cpu_limits(cpu_count)
    override = env_file.with_name("compose.auto.yaml")
    # 生成物放在长期配置目录，不修改带校验和的 Release；原子替换避免读到半份配置。
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".compose.auto.", suffix=".yaml", dir=env_file.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(render_override(limits, cpu_limits))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, override)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

    print(
        json.dumps(
            {
                "event": "compose.capacity_selected",
                "docker_cpu_count": cpu_count,
                "docker_memory_mib": memory_bytes // _MIB,
                "service_memory_limits_mib": limits,
                "service_cpu_limits": cpu_limits,
                "worker_replicas": 1,
            },
            ensure_ascii=False,
        )
    )
    base = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(compose_file),
    ]
    windows_overlay = compose_file.with_name("compose.windows.yaml")
    if os.name == "nt" and windows_overlay.is_file():
        base.extend(("-f", str(windows_overlay)))
    base.extend(("-f", str(override)))
    subprocess.run([*base, "config", "--quiet"], check=True, cwd=compose_file.parent)
    if not dry_run:
        subprocess.run(
            [*base, "up", "--no-build", "--pull", "never", "--wait"],
            check=True,
            cwd=compose_file.parent,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="按 Docker Engine 可用资源启动离线 Compose")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--compose-file", type=Path, default=_default_compose_file())
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    start(
        compose_file=arguments.compose_file,
        env_file=arguments.env_file,
        dry_run=arguments.dry_run,
    )
    return 0


def _default_compose_file() -> Path:
    script = Path(__file__).resolve()
    bundled = script.parent / "compose.yaml"
    return bundled if bundled.is_file() else script.parents[2] / "compose.yaml"


if __name__ == "__main__":
    raise SystemExit(main())
