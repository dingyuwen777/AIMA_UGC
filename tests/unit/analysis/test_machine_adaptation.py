"""机器适配回归覆盖启动包装层、实际负载与容器 CPU 配额。"""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_capacity import empty_window
from aima_ugc.entrypoints import worker_main
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState
from aima_ugc.platform import capacity
from aima_ugc.platform.time import BEIJING_TIMEZONE

from tests.unit.analysis.test_capacity_diagnostics import (
    _MemoryCapacityRepository,
    _MemorySession,
    _profile,
)


def test_worker_pool_expands_when_launcher_pid_differs_from_lease_owner(monkeypatch):
    """模拟 Windows venv 包装层；父进程必须认出实际持有 Lease 的子 Worker。"""
    children = []
    busy = set()
    clock = [0.0]
    session = SimpleNamespace(begin=nullcontext, close=lambda: None)
    runtime = SimpleNamespace(
        database=SimpleNamespace(new_session=lambda: session),
        logger=logging.getLogger("test.machine_pool"),
        close=lambda: None,
    )

    def spawn(args, **kwargs):
        """启动 PID 与执行 PID 有意不同，实际 Lease 使用子进程继承的身份。"""
        env = kwargs.get("env", {})
        owner = env.get("_AIMA_WORKER_LEASE_OWNER", f"host:{9000 + len(children)}")
        child = SimpleNamespace(
            pid=1000 + len(children), poll=lambda: None, terminate=lambda: None, wait=lambda: 0
        )
        children.append(child)
        if len(children) == 1:
            busy.add(owner)
        return child

    def sleep(seconds):
        """有界推进真实进程池循环，不启动进程、不连接数据库。"""
        clock[0] += seconds
        if clock[0] >= 6:
            raise KeyboardInterrupt

    monkeypatch.setattr(worker_main, "create_worker_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(worker_main.subprocess, "Popen", spawn)
    monkeypatch.setattr(worker_main.socket, "gethostname", lambda: "host")
    monkeypatch.setattr(worker_main.signal, "signal", lambda *args: None)
    monkeypatch.setattr(worker_main.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(worker_main.time, "sleep", sleep)
    monkeypatch.setattr(
        worker_main,
        "detect_resources",
        lambda: capacity.ResourceSnapshot(12, 32 * 1024**3, 12 * 1024**3, "host"),
    )
    monkeypatch.setattr(
        worker_main,
        "PostgresJobRepository",
        lambda session: SimpleNamespace(
            pool_pressure=lambda *, lease_owners, **kwargs: (1, busy & lease_owners)
        ),
    )
    worker_main._run_worker_pool()
    assert len(children) >= 2


def test_underfilled_window_cannot_rollback_or_learn_model_capacity():
    """真实日志中的 1024 目标/111 在途不能证明 1024 是模型上界。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    before = CapacityState(
        current=1024,
        last_safe=782,
        last_safe_throughput=23.187,
        throughput_ewma=13.817,
        latency_p95=73,
        plateau_windows=1,
    )
    row["state"] = asdict(before)
    repo = _MemoryCapacityRepository(_MemorySession(row), base + timedelta(seconds=2))
    delta = empty_window()
    delta.update(requests=28, persisted=28, cohort_requests=28, busy_seconds=222, demand=True)
    diagnostics = {}
    repo.observe(
        uuid4(),
        "test",
        revision=1,
        prompt_sha256="a" * 64,
        delta=delta,
        diagnostics=diagnostics,
    )
    assert row["state"]["current"] == 1024
    assert row["state"]["unsafe"] is None
    assert row["state"]["last_safe"] == 782
    assert row["state"]["throughput_ewma"] == before.throughput_ewma
    assert diagnostics["accepted_demand"] is False


def test_worker_pool_only_shrinks_idle_stable_lease_owners(monkeypatch):
    """内存缩容时，即使最后启动的包装 PID 不同，也不能终止其忙碌解释器。"""
    children = []
    busy = set()
    terminated = []
    before_cleanup = []
    clock = [0.0]
    session = SimpleNamespace(begin=nullcontext, close=lambda: None)
    runtime = SimpleNamespace(
        database=SimpleNamespace(new_session=lambda: session),
        logger=logging.getLogger("test.machine_shrink"),
        close=lambda: None,
    )

    def spawn(args, **kwargs):
        """第一和最后一个 Worker 持有 Lease，中间两个处于空闲状态。"""
        pid = 1000 + len(children)
        owner = kwargs["env"]["_AIMA_WORKER_LEASE_OWNER"]
        child = SimpleNamespace(
            pid=pid,
            poll=lambda: 0 if owner in terminated else None,
            terminate=lambda: terminated.append(owner),
            wait=lambda: 0,
        )
        children.append(child)
        if len(children) in {1, 4}:
            busy.add(owner)
        return child

    def sleep(seconds):
        """在 finally 清理前保存缩容行为，避免把正常退出混作缩容。"""
        clock[0] += seconds
        if clock[0] >= 12:
            before_cleanup.extend(terminated)
            raise KeyboardInterrupt

    monkeypatch.setattr(worker_main, "create_worker_runtime", lambda **kwargs: runtime)
    monkeypatch.setattr(worker_main.subprocess, "Popen", spawn)
    monkeypatch.setattr(worker_main.signal, "signal", lambda *args: None)
    monkeypatch.setattr(worker_main.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(worker_main.time, "sleep", sleep)
    monkeypatch.setattr(
        worker_main,
        "detect_resources",
        lambda: capacity.ResourceSnapshot(
            12, 32 * 1024**3, (512 * 1024**2 if clock[0] >= 6 else 12 * 1024**3), "host"
        ),
    )
    monkeypatch.setattr(
        worker_main,
        "PostgresJobRepository",
        lambda session: SimpleNamespace(
            pool_pressure=lambda *, lease_owners, **kwargs: (
                0 if clock[0] >= 6 else 3,
                busy & lease_owners,
            )
        ),
    )
    worker_main._run_worker_pool()
    assert len(children) == 4
    assert before_cleanup
    assert busy.isdisjoint(before_cleanup)


@pytest.mark.parametrize("version", [1, 2])
def test_cpu_pressure_measures_container_quota_instead_of_idle_host(tmp_path, monkeypatch, version):
    """宿主机很空闲也不能掩盖只有半核配额的容器已经饱和。"""
    if version == 2:
        (tmp_path / "cpu.max").write_text("50000 100000", encoding="ascii")
        usage = tmp_path / "cpu.stat"
    else:
        (tmp_path / "cpu").mkdir()
        (tmp_path / "cpuacct").mkdir()
        (tmp_path / "cpu/cpu.cfs_quota_us").write_text("50000", encoding="ascii")
        (tmp_path / "cpu/cpu.cfs_period_us").write_text("100000", encoding="ascii")
        usage = tmp_path / "cpuacct/cpuacct.usage"

    def write_usage(value):
        """按内核协议提供微秒或纳秒计数，不依赖宿主机实际负载。"""
        text = f"usage_usec {value}\n" if version == 2 else str(value * 1000)
        usage.write_text(text, encoding="ascii")

    write_usage(1000000)
    clock = [0.0]
    host = iter([(100, 90), (200, 180), (300, 270)])
    monkeypatch.setattr(capacity, "monotonic", lambda: clock[0])
    monkeypatch.setattr(capacity.CpuPressureSampler, "_read", staticmethod(lambda: next(host)))
    sampler = capacity.CpuPressureSampler(cgroup_root=tmp_path)
    clock[0] = 2
    write_usage(1950000)
    assert sampler.sample() == pytest.approx(0.95)
    clock[0] = 4
    write_usage(100)
    assert sampler.sample() is None


def test_cpu_quota_change_requires_a_new_baseline(tmp_path, monkeypatch):
    """动态调整配额后不能用旧分母计算当前压力。"""
    (tmp_path / "cpu.max").write_text("50000 100000", encoding="ascii")
    (tmp_path / "cpu.stat").write_text("usage_usec 1000000\n", encoding="ascii")
    clock = [0.0]
    monkeypatch.setattr(capacity, "monotonic", lambda: clock[0])
    sampler = capacity.CpuPressureSampler(cgroup_root=tmp_path)
    (tmp_path / "cpu.max").write_text("200000 100000", encoding="ascii")
    (tmp_path / "cpu.stat").write_text("usage_usec 4000000\n", encoding="ascii")
    clock[0] = 2
    assert sampler.sample() is None
    (tmp_path / "cpu.stat").write_text("usage_usec 7000000\n", encoding="ascii")
    clock[0] = 4
    assert sampler.sample() == pytest.approx(0.75)
