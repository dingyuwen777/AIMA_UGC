"""Windows/Linux 共用的 Compose 启停入口测试。"""

from __future__ import annotations

import json
import os
import runpy
import subprocess
from pathlib import Path

import pytest
from aima_ugc.platform.capacity import ResourceSnapshot, select_job_window, worker_process_limit

_ROOT = Path(__file__).resolve().parents[2]
_START = runpy.run_path(str(_ROOT / "scripts/deploy/start_compose.py"))
_STOP = runpy.run_path(str(_ROOT / "scripts/deploy/stop_compose.py"))
compute_memory_limits = _START["compute_memory_limits"]
compute_cpu_limits = _START["compute_cpu_limits"]
start = _START["start"]
stop = _STOP["stop"]


def test_memory_plan_keeps_headroom_and_refuses_too_small_engine() -> None:
    with pytest.raises(RuntimeError, match="不足 6 GiB"):
        compute_memory_limits(5 * 1024**3)
    small_limits = compute_memory_limits(6 * 1024**3)
    steady = {"postgres", "worker", "api", "scheduler", "frontend"}
    assert sum(small_limits[name] for name in steady) + small_limits["migrate"] <= 6 * 1024 * 0.75
    limits = compute_memory_limits(16 * 1024**3)
    assert set(limits) == steady | {"bootstrap", "migrate", "configure"}
    assert sum(limits[name] for name in steady) + limits["migrate"] <= 16 * 1024 * 0.75
    assert limits["postgres"] > limits["api"]
    cpu = compute_cpu_limits(12)
    assert sum(cpu[name] for name in steady) + cpu["migrate"] <= 12 * 0.80

    server_memory = compute_memory_limits(64 * 1024**3)["worker"]
    server_cpu = compute_cpu_limits(16)["worker"]
    server_worker = ResourceSnapshot(
        server_cpu,
        server_memory * 1024**2,
        (server_memory - 512) * 1024**2,
        "cgroup_v2",
    )
    assert worker_process_limit(server_worker) == select_job_window(server_worker) == 3
    future_memory = compute_memory_limits(128 * 1024**3)["worker"]
    future_worker = ResourceSnapshot(
        compute_cpu_limits(32)["worker"],
        future_memory * 1024**2,
        (future_memory - 1024) * 1024**2,
        "cgroup_v2",
    )
    assert worker_process_limit(future_worker) == select_job_window(future_worker) == 6


def test_start_and_stop_use_external_env_without_copying_it(tmp_path: Path, monkeypatch) -> None:
    compose = tmp_path / "compose.yaml"
    env = tmp_path / "server.env"
    compose.write_text("services: {}\n", encoding="utf-8")
    windows_overlay = tmp_path / "compose.windows.yaml"
    windows_overlay.write_text("services: {}\n", encoding="utf-8")
    env.write_text("PRIVATE_VALUE=must-not-appear-in-override\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(command)
        if command[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps({"NCPU": 8, "MemTotal": 16 * 1024**3})
            )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    start(compose_file=compose, env_file=env, dry_run=True)
    override = tmp_path / "compose.auto.yaml"
    assert override.is_file()
    assert "must-not-appear" not in override.read_text(encoding="utf-8")
    assert "cpus:" in override.read_text(encoding="utf-8")
    assert 'AIMA_AUTO_WORKER_CPU_CORES: "' in override.read_text(encoding="utf-8")
    assert 'AIMA_AUTO_WORKER_MEMORY_MIB: "' in override.read_text(encoding="utf-8")
    assert ["docker", "compose", "--env-file", str(env), "-f", str(compose)] == calls[1][:6]
    if os.name == "nt":
        assert ["-f", str(windows_overlay)] == calls[1][6:8]
    assert calls[1][-2:] == ["config", "--quiet"]

    stop(compose_file=compose, env_file=env)
    if os.name == "nt":
        assert str(windows_overlay) in calls[-1]
    assert calls[-1][-3:] == ["stop", "--timeout", "60"]
    assert "-v" not in calls[-1]
