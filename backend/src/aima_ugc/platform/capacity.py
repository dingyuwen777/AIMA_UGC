"""读取进程实际资源边界，供有界吞吐策略使用。"""

from __future__ import annotations

import ctypes
import os
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from math import floor, isfinite
from pathlib import Path
from statistics import median

_MIB = 1024 * 1024
_CGROUP_UNLIMITED = 1 << 60


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """同一时刻可供进程使用的 CPU 与内存预算。"""

    cpu_cores: float
    memory_limit_bytes: int | None
    memory_available_bytes: int | None
    source: str


def detect_resources(
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    host_cpu_count: int | None = None,
    host_memory_total_bytes: int | None = None,
    host_memory_available_bytes: int | None = None,
) -> ResourceSnapshot:
    """优先采用容器配额，无法读取时退回可见宿主机资源。"""

    cpu_count = max(1, host_cpu_count or (os.process_cpu_count() or os.cpu_count() or 1))
    host_total, host_available = _host_memory()
    total = host_total if host_memory_total_bytes is None else host_memory_total_bytes
    available = (
        host_available if host_memory_available_bytes is None else host_memory_available_bytes
    )
    root = Path(cgroup_root)

    quota = _cpu_quota_v2(root)
    limit = _positive_int(root / "memory.max")
    used = _positive_int(root / "memory.current")
    source = "host"
    if quota is not None or (limit is not None and limit < _CGROUP_UNLIMITED):
        source = "cgroup_v2"
    else:
        quota = _cpu_quota_v1(root)
        limit = _positive_int(root / "memory" / "memory.limit_in_bytes")
        used = _positive_int(root / "memory" / "memory.usage_in_bytes")
        if quota is not None or (limit is not None and limit < _CGROUP_UNLIMITED):
            source = "cgroup_v1"

    effective_cpu = min(float(cpu_count), quota) if quota is not None else float(cpu_count)
    effective_limit = (
        min(total, limit)
        if total and limit and limit < _CGROUP_UNLIMITED
        else (total or (limit if limit is not None and limit < _CGROUP_UNLIMITED else None))
    )
    effective_available: int | None
    if limit is not None and limit < _CGROUP_UNLIMITED and used is not None:
        remaining = max(limit - used, 0)
        effective_available = min(available, remaining) if available is not None else remaining
    else:
        effective_available = available
    return ResourceSnapshot(
        cpu_cores=max(effective_cpu, 0.01),
        memory_limit_bytes=effective_limit,
        memory_available_bytes=effective_available,
        source=source,
    )


def select_chunk_rows(resources: ResourceSnapshot) -> int:
    """按可用内存选择冻结粒度；API 的 CPU 配额不代表实际执行的 Worker。"""

    available = resources.memory_available_bytes
    if available is not None and available < 256 * _MIB:
        return 500
    if available is not None and available < 768 * _MIB:
        return 1000
    return 2000


def worker_process_limit(resources: ResourceSnapshot) -> int:
    """按 Worker 容器有效配额给进程池设资源上界。"""

    memory = resources.memory_limit_bytes
    if memory is None:
        return 1
    return max(1, min(floor(resources.cpu_cores / 1.5), memory // (1024 * _MIB)))


def planned_worker_resources(
    api_resources: ResourceSnapshot,
    *,
    environment: Mapping[str, str] | None = None,
) -> ResourceSnapshot:
    """从启动脚本生成的 Compose 环境读取 Worker 预算；缺失时保守使用本进程配额。"""

    values = os.environ if environment is None else environment
    try:
        cpu = float(values["AIMA_AUTO_WORKER_CPU_CORES"])
        memory_mib = int(values["AIMA_AUTO_WORKER_MEMORY_MIB"])
    except KeyError, ValueError:
        return api_resources
    if not isfinite(cpu) or cpu <= 0 or memory_mib <= 0:
        return api_resources
    return ResourceSnapshot(
        cpu_cores=cpu,
        memory_limit_bytes=memory_mib * _MIB,
        memory_available_bytes=api_resources.memory_available_bytes,
        source="compose_worker_budget",
    )


def select_job_window(resources: ResourceSnapshot, *, ceiling: int | None = None) -> int:
    """内存紧张时收窄 Job 积压；API 的 CPU 配额不限制 Worker 并发。"""

    if ceiling is not None and ceiling < 1:
        raise ValueError("Job 窗口上限必须为正整数")
    available = resources.memory_available_bytes
    if available is not None and available < 768 * _MIB:
        return 1
    selected = worker_process_limit(resources)
    return min(selected, ceiling) if ceiling is not None else selected


class AdaptiveJobWindowController:
    """按已完成工作量的墙钟吞吐逐级试探持久 Job 并发窗口。"""

    def __init__(
        self,
        *,
        improvement_margin: float = 0.08,
        reprobe_after: int = 8,
        initial_window: int = 1,
    ) -> None:
        if not 0 < improvement_margin < 1 or reprobe_after < 1 or initial_window < 1:
            raise ValueError("Job 并发反馈参数无效")
        self.improvement_margin = improvement_margin
        self.reprobe_after = reprobe_after
        self._current = initial_window
        self._probe: int | None = None
        self._samples: dict[int, list[float]] = {}
        self._stable_waves = 0
        self._probe_blocked = False
        self._lower_checked = False
        self._cooldown = 0
        self._last_choice: int | None = None

    def choose(
        self,
        resources: ResourceSnapshot,
        *,
        remaining_units: int,
        database_headroom: int | None = None,
    ) -> tuple[int, str, int | None]:
        """资源只限制上界；升档必须由本次任务的已完成吞吐证明。"""

        if remaining_units < 0 or (database_headroom is not None and database_headroom < 1):
            raise ValueError("Job 剩余量和数据库连接余量必须有效")
        maximum = select_job_window(resources)
        if database_headroom is not None:
            maximum = min(maximum, database_headroom)
        maximum = max(1, min(maximum, max(1, remaining_units)))
        if self._cooldown:
            choice, reason = min(maximum, max(1, self._current - 1)), "database_retry_cooldown"
        elif maximum < self._current:
            choice, reason = maximum, "resource_limit"
        elif self._probe is not None and self._probe <= maximum:
            choice, reason = self._probe, "throughput_probe"
        elif (
            not self._probe_blocked
            and self._current < maximum
            and len(self._samples.get(self._current, ())) >= 1
        ):
            self._probe = self._current + 1
            choice, reason = self._probe, "throughput_probe"
        elif (
            self._current > 1
            and not self._lower_checked
            and len(self._samples.get(self._current, ())) >= 2
            and remaining_units >= 2
        ):
            self._probe = self._current - 1
            self._samples.pop(self._probe, None)
            choice, reason = self._probe, "throughput_probe"
        else:
            choice, reason = self._current, "measured_throughput"
        previous = self._last_choice
        self._last_choice = choice
        return choice, reason, previous

    def succeeded(self, *, window: int, contents: int, duration_ms: int) -> None:
        """只比较有实际工作的完整波次，稳定后重新试探上一个失败档。"""

        if self._cooldown:
            self._cooldown -= 1
        if contents < 1 or duration_ms < 1:
            return
        samples = self._samples.setdefault(window, [])
        samples.append(contents * 1000 / duration_ms)
        del samples[:-3]
        if self._probe == window and len(samples) >= 2:
            baseline = self._samples.get(self._current, [])
            if baseline and median(samples) > median(baseline) * (1 + self.improvement_margin):
                lowered = window < self._current
                self._current = window
                self._probe_blocked = lowered
                self._lower_checked = False
            else:
                if window > self._current:
                    self._probe_blocked = True
                else:
                    self._lower_checked = True
            self._probe = None
            self._stable_waves = 0
        elif window == self._current and self._probe is None:
            self._stable_waves += 1
            if self._probe_blocked and self._stable_waves >= self.reprobe_after:
                self._samples.pop(self._current + 1, None)
                self._probe_blocked = False
                self._stable_waves = 0

    def database_retry(self) -> None:
        """瞬时数据库错误后先降档，连续成功波次再恢复探索。"""

        self._cooldown = 3
        self._probe = None


class AdaptiveBatchController:
    """用同一 Worker 的成功批次比较两档吞吐，并在资源压力/数据库重试时降档。"""

    def __init__(self, *, lower: int, upper: int, improvement_margin: float = 0.15) -> None:
        if lower < 1 or upper <= lower or not 0 < improvement_margin < 1:
            raise ValueError("批量调节边界无效")
        self.lower = lower
        self.upper = upper
        self.improvement_margin = improvement_margin
        self._samples: dict[int, list[float]] = {lower: [], upper: []}
        self._cooldown = 0
        self._last_choice: int | None = None
        self._preferred: int | None = None
        self._stable_successes = 0
        self._reprobe_size: int | None = None
        self._reprobe_interval = 24
        self._last_reason: str | None = None

    def choose(self, resources: ResourceSnapshot) -> tuple[int, str, int | None]:
        """返回本批大小、原因，以及上次选择。"""

        available = resources.memory_available_bytes
        if available is not None and available < 768 * _MIB:
            size, reason = self.lower, "memory_pressure"
        elif self._cooldown > 0:
            size, reason = self.lower, "database_retry_cooldown"
        elif self._reprobe_size is not None:
            size, reason = self._reprobe_size, "periodic_reprobe"
        elif len(self._samples[self.upper]) < 3:
            size, reason = self.upper, "baseline_probe"
        elif len(self._samples[self.lower]) < 3:
            size, reason = self.lower, "alternative_probe"
        else:
            upper_time = median(self._samples[self.upper])
            lower_time = median(self._samples[self.lower])
            if self._preferred is None:
                self._preferred = (
                    self.lower
                    if lower_time < upper_time * (1 - self.improvement_margin)
                    else self.upper
                )
            elif self._preferred == self.upper:
                if lower_time < upper_time * (1 - self.improvement_margin):
                    self._preferred = self.lower
            elif upper_time < lower_time * (1 - self.improvement_margin):
                self._preferred = self.upper
            size, reason = self._preferred, "measured_throughput"
        previous = self._last_choice
        self._last_choice = size
        self._last_reason = reason
        return size, reason, previous

    def succeeded(self, *, size: int, rows: int, duration_ms: int) -> None:
        """只把有足够行数的成功批次计入对照，避免尾块与空写入干扰。"""

        if self._cooldown > 0:
            self._cooldown -= 1
        if (
            size not in self._samples
            or rows < self.lower
            or duration_ms <= 0
            or self._last_reason in {"memory_pressure", "database_retry_cooldown"}
        ):
            return
        samples = self._samples[size]
        samples.append(duration_ms / rows)
        del samples[:-3]
        if self._reprobe_size == size and len(samples) == 3:
            self._reprobe_size = None
            self._stable_successes = 0
        elif self._preferred == size and self._reprobe_size is None:
            self._stable_successes += 1
            if self._stable_successes >= self._reprobe_interval:
                alternative = self.lower if size == self.upper else self.upper
                self._samples[alternative].clear()
                self._reprobe_size = alternative
                self._stable_successes = 0

    def database_retry(self) -> None:
        """数据库瞬时失败后连续三个成功批次保持较小档位。"""

        self._cooldown = 3


class AdaptiveTierBatchController:
    """逐级比较相邻批量的实测吞吐，低资源时立即降档。"""

    def __init__(
        self,
        *,
        tiers: tuple[int, ...] = (250, *range(500, 65_501, 500)),
        improvement_margin: float = 0.15,
        transaction_ceiling_ms: int = 3000,
        rows_per_cpu_core: int = 2000,
        memory_mib_per_1000_rows: int = 1536,
    ) -> None:
        if (
            len(tiers) < 2
            or any(left >= right or left < 1 for left, right in zip(tiers, tiers[1:], strict=False))
            or not 0 < improvement_margin < 1
            or transaction_ceiling_ms < 100
            or rows_per_cpu_core < 1
            or memory_mib_per_1000_rows < 1
        ):
            raise ValueError("批量升档阶梯无效")
        self.tiers = tiers
        self.improvement_margin = improvement_margin
        self.transaction_ceiling_ms = transaction_ceiling_ms
        self.rows_per_cpu_core = rows_per_cpu_core
        self.memory_mib_per_1000_rows = memory_mib_per_1000_rows
        self._current = 1
        self._probe: int | None = None
        self._samples: dict[int, list[float]] = {index: [] for index in range(len(tiers))}
        self._stable_successes = 0
        self._probe_blocked = False
        self._cooldown = 0
        self._last_choice: int | None = None
        self._last_reason: str | None = None
        self._downshift_reason: str | None = None

    def choose(self, resources: ResourceSnapshot) -> tuple[int, str, int | None]:
        """下一批读取当时有效资源，且只在相邻档位收益明确时升档。"""

        available = resources.memory_available_bytes
        cpu = resources.cpu_cores
        if available is not None and available < 768 * _MIB:
            maximum = 0
        else:
            # CPU、剩余内存只设探索上界；是否真正升档仍由本 Job 的实测吞吐决定。
            baseline = self.tiers[1]
            memory_ceiling = (
                max(
                    baseline,
                    int(available // (self.memory_mib_per_1000_rows * _MIB)) * 1000,
                )
                if available is not None
                else baseline
            )
            cpu_ceiling = max(baseline, int(cpu * self.rows_per_cpu_core))
            maximum = max(0, bisect_right(self.tiers, min(memory_ceiling, cpu_ceiling)) - 1)
        if maximum == 0:
            index, reason = 0, "memory_pressure"
        elif self._cooldown:
            index, reason = max(0, min(self._current - 1, maximum)), "database_retry_cooldown"
        elif self._downshift_reason is not None:
            index, reason = min(self._current, maximum), self._downshift_reason
            self._downshift_reason = None
        elif self._current > maximum:
            index, reason = maximum, "resource_limit"
        elif self._probe is not None and self._probe <= maximum:
            index, reason = self._probe, "throughput_probe"
        elif (
            not self._probe_blocked
            and len(self._samples[self._current]) >= 3
            and self._current < maximum
        ):
            self._probe = self._current + 1
            index, reason = self._probe, "throughput_probe"
        else:
            index, reason = self._current, "measured_throughput"
        previous = self._last_choice
        size = self.tiers[index]
        self._last_choice = size
        self._last_reason = reason
        return size, reason, previous

    def succeeded(self, *, size: int, rows: int, duration_ms: int) -> None:
        """只比较装满的成功批次，避免尾批和资源降档污染结果。"""

        if self._cooldown:
            self._cooldown -= 1
        if (
            rows < size
            or duration_ms <= 0
            or self._last_reason in {"memory_pressure", "resource_limit", "database_retry_cooldown"}
        ):
            return
        index = self.tiers.index(size)
        if duration_ms > self.transaction_ceiling_ms:
            if self._probe != index and index == self._current and index > 0:
                self._current -= 1
                self._downshift_reason = "transaction_ceiling"
                self._samples[self._current].clear()
            self._probe = None
            self._probe_blocked = True
            self._stable_successes = 0
            return
        samples = self._samples[index]
        samples.append(duration_ms / rows)
        del samples[:-3]
        if self._probe == index and len(samples) == 3:
            baseline = median(self._samples[self._current])
            candidate = median(samples)
            if candidate < baseline * (1 - self.improvement_margin):
                self._current = index
                self._probe_blocked = False
            else:
                self._probe_blocked = True
            self._probe = None
            self._stable_successes = 0
        elif index == self._current and self._probe is None:
            self._stable_successes += 1
            if self._stable_successes >= 24 and self._current + 1 < len(self.tiers):
                self._samples[self._current + 1].clear()
                self._probe = self._current + 1
                self._probe_blocked = False
                self._stable_successes = 0

    def database_retry(self) -> None:
        self._cooldown = 3


def _positive_int(path: Path) -> int | None:
    try:
        value = int(path.read_text(encoding="ascii").strip())
    except OSError, ValueError:
        return None
    return value if value >= 0 else None


def _cpu_quota_v2(root: Path) -> float | None:
    try:
        quota, period = (root / "cpu.max").read_text(encoding="ascii").split()[:2]
        if quota == "max":
            return None
        quota_value, period_value = int(quota), int(period)
        return quota_value / period_value if quota_value > 0 and period_value > 0 else None
    except OSError, ValueError, IndexError:
        return None


def _cpu_quota_v1(root: Path) -> float | None:
    quota = _positive_int(root / "cpu" / "cpu.cfs_quota_us")
    period = _positive_int(root / "cpu" / "cpu.cfs_period_us")
    return quota / period if quota and period else None


def _host_memory() -> tuple[int | None, int | None]:
    if os.name == "nt":

        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong),
                ("available_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended", ctypes.c_ulonglong),
            ]

        status = _MemoryStatus()
        status.length = ctypes.sizeof(status)
        windows_api = getattr(ctypes, "windll", None)
        if windows_api is not None and windows_api.kernel32.GlobalMemoryStatusEx(
            ctypes.byref(status)
        ):
            return int(status.total_physical), int(status.available_physical)
        return None, None
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            name, value = line.split(":", 1)
            if name in {"MemTotal", "MemAvailable"}:
                values[name] = int(value.strip().split()[0]) * 1024
        return values.get("MemTotal"), values.get("MemAvailable")
    except OSError, ValueError, IndexError:
        return None, None
