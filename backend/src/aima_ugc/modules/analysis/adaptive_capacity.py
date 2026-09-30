"""LLM 容量的确定性控制规则；不发请求、不读数据库、不改变模型业务协议。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil

CAPACITY_MODE = "adaptive.v1"
GLOBAL_CONCURRENCY_CEILING = 5_000
SHARD_CONCURRENCY_CEILING = 256
INITIAL_CONCURRENCY = 10
VALIDATION_RETRIES = 3
WINDOW_SECONDS = 10.0
TARGET_SHARD_SECONDS = 300
_REFINEMENT_LIMIT = 6
_RECOVERY_WINDOWS = 3
_REPROBE_WINDOWS = 12


@dataclass(frozen=True, slots=True)
class CapacityObservation:
    """一个共享墙钟窗的反馈，Content 与物理 HTTP Attempt 分母独立。"""

    seconds: float
    persisted: int = 0
    failed: int = 0
    validation_failed: int = 0
    requests: int = 0
    started: int = 0
    rate_limited: int = 0
    timeouts: int = 0
    transport_errors: int = 0
    p95_seconds: float = 0.0
    timeout_lower_bound_seconds: float = 0.0
    demand: bool = True


@dataclass(frozen=True, slots=True)
class CapacityState:
    """单 Profile 的有界搜索状态，可作为 JSON 直接持久化。"""

    current: int = INITIAL_CONCURRENCY
    last_safe: int = 0
    safe_bound: int = 0
    historical_safe: int = 0
    unsafe: int | None = None
    phase: str = "exploring"
    rps: float | None = None
    throughput_ewma: float = 0.0
    last_safe_throughput: float = 0.0
    plateau_windows: int = 0
    latency_p95: float = 0.0
    timeout_lower_bound_seconds: float = 0.0
    rate_limit_ratio: float = 0.0
    timeout_ratio: float = 0.0
    transport_error_ratio: float = 0.0
    validation_failure_ratio: float = 0.0
    stable_windows: int = 0
    cooldown_windows: int = 0
    refinements: int = 0
    reason: str = "cold_start"
    last_adjustment_reason: str = "cold_start"

    def warm_start(self) -> CapacityState:
        """配置/Prompt 变化仅降低可信度，历史容量不当作当前安全证明。"""

        return replace(
            self,
            current=max(1, min(32, (self.last_safe or self.current) // 2)),
            last_safe=0,
            safe_bound=0,
            unsafe=None,
            phase="exploring",
            stable_windows=0,
            cooldown_windows=0,
            refinements=0,
            throughput_ewma=0.0,
            last_safe_throughput=0.0,
            plateau_windows=0,
            latency_p95=0.0,
            reason="configuration_warm_start",
            last_adjustment_reason="configuration_warm_start",
        )

    def observe(self, sample: CapacityObservation) -> CapacityState:
        """先快速处理拥塞，再以成功入库速率接受健康候选和有限探测。"""

        if sample.seconds <= 0:
            raise ValueError("观察窗时间必须大于零")
        if sample.requests == 0 and sample.persisted == 0 and sample.failed == 0:
            return self
        physical = max(1, sample.requests)
        terminal = max(1, sample.persisted + sample.failed)
        throughput = sample.persisted / sample.seconds
        updated = replace(
            self,
            throughput_ewma=(
                throughput
                if self.throughput_ewma == 0
                else 0.3 * throughput + 0.7 * self.throughput_ewma
            ),
            rate_limit_ratio=sample.rate_limited / physical,
            timeout_ratio=sample.timeouts / physical,
            transport_error_ratio=sample.transport_errors / physical,
            validation_failure_ratio=sample.validation_failed / terminal,
            timeout_lower_bound_seconds=min(
                180.0, max(self.timeout_lower_bound_seconds, sample.timeout_lower_bound_seconds)
            ),
        )
        congestion = (
            sample.rate_limited > 0
            or sample.timeouts / physical > 0.02
            or sample.transport_errors / physical > 0.02
            or (
                self.latency_p95 > 0
                and sample.p95_seconds > self.latency_p95 * 2
                and throughput < self.throughput_ewma * 0.8
            )
        )
        if congestion:
            lowered = max(1, self.current // 2)
            rps = self.rps
            if sample.rate_limited:
                observed_rate = max(0.1, sample.started / sample.seconds)
                rps = max(0.1, min(rps or observed_rate, observed_rate) * 0.7)
            return replace(
                updated,
                current=lowered,
                last_safe=min(self.last_safe, lowered),
                safe_bound=(self.safe_bound if self.current > self.last_safe else 0),
                unsafe=self.current,
                phase="cooldown",
                rps=rps,
                stable_windows=0,
                cooldown_windows=_RECOVERY_WINDOWS,
                refinements=(
                    _REFINEMENT_LIMIT
                    if self.phase == "reprobing"
                    else self.refinements
                    if self.phase in {"refining", "cooldown"}
                    else 0
                ),
                reason="http_429" if sample.rate_limited else "timeout_transport_or_latency",
            )
        # RPS 是从属保护，即使它暂时让并发未满，也必须能在健康发送窗逐步恢复。
        if sample.persisted and sample.validation_failed / terminal <= 0.01:
            updated = replace(
                updated,
                latency_p95=(
                    sample.p95_seconds
                    if self.latency_p95 == 0
                    else 0.2 * sample.p95_seconds + 0.8 * self.latency_p95
                ),
                rps=(
                    min(10_000.0, self.rps * 1.15)
                    if self.rps is not None and sample.started / sample.seconds >= self.rps * 0.8
                    else self.rps
                ),
            )
        if sample.persisted and sample.timeouts == 0:
            updated = replace(updated, timeout_lower_bound_seconds=0.0)
        # 没有已提交成功或仍在等待首批结果时，不把低样本窗当作健康证明。
        if sample.persisted < min(8, max(1, self.current // 4)) or not sample.demand:
            return replace(updated, reason="insufficient_demand_or_results")
        if sample.validation_failed / terminal > 0.01:
            return replace(
                updated, phase="stable", stable_windows=0, reason="validation_failure_guard"
            )
        if (
            self.current > self.last_safe
            and self.last_safe_throughput > 0
            and throughput < self.last_safe_throughput * 1.05
        ):
            if self.plateau_windows < 1:
                return replace(
                    updated,
                    plateau_windows=self.plateau_windows + 1,
                    reason="confirming_throughput_plateau",
                )
            return replace(
                updated,
                current=self.last_safe,
                unsafe=self.current,
                phase="stable",
                stable_windows=0,
                plateau_windows=0,
                reason="persisted_throughput_plateau",
            )
        updated = replace(
            updated,
            last_safe=self.current,
            historical_safe=max(self.historical_safe, self.current),
            safe_bound=max(self.safe_bound, self.current),
            last_safe_throughput=throughput,
            plateau_windows=0,
        )
        if self.cooldown_windows:
            return replace(
                updated, cooldown_windows=self.cooldown_windows - 1, reason="healthy_cooldown"
            )
        if self.phase == "stable":
            stable = self.stable_windows + 1
            if stable < _REPROBE_WINDOWS or self.current == GLOBAL_CONCURRENCY_CEILING:
                return replace(updated, stable_windows=stable, reason="healthy_stable")
            return replace(
                updated,
                current=min(
                    GLOBAL_CONCURRENCY_CEILING, max(self.current + 1, ceil(self.current * 1.25))
                ),
                unsafe=None,
                phase="reprobing",
                stable_windows=0,
                refinements=0,
                reason="periodic_reprobe",
            )
        if self.unsafe is not None:
            gap = self.unsafe - updated.safe_bound
            if (
                gap <= max(2, ceil(updated.safe_bound * 0.05))
                or self.refinements >= _REFINEMENT_LIMIT
            ):
                return replace(
                    updated,
                    current=updated.safe_bound,
                    phase="stable",
                    stable_windows=0,
                    reason="refinement_complete",
                )
            return replace(
                updated,
                current=updated.safe_bound + max(1, gap // 2),
                phase="refining",
                refinements=self.refinements + 1,
                reason="bounded_refinement",
            )
        candidate = min(GLOBAL_CONCURRENCY_CEILING, self.current * 2)
        return replace(
            updated,
            current=candidate,
            phase="stable" if candidate == self.current else "exploring",
            reason="exponential_probe" if candidate != self.current else "system_ceiling",
        )


def shard_capacity(global_capacity: int, shard_count: int, shard_index: int) -> int:
    """稳定排序后分配整数余数；低容量时允许部分 Shard 为零，份额总和有界。"""

    if not 0 <= shard_index < shard_count:
        raise ValueError("Shard 序号必须属于当前活动集合")
    quotient, remainder = divmod(global_capacity, shard_count)
    return min(SHARD_CONCURRENCY_CEILING, quotient + (shard_index < remainder))


def learned_run_limits(state: CapacityState) -> tuple[int, int]:
    """仅在创建 Run 时由历史估计派生并冻结 Shard size 和 HTTP timeout。"""

    throughput = state.throughput_ewma or INITIAL_CONCURRENCY / 5.0
    jobs = max(1, ceil(state.current / SHARD_CONCURRENCY_CEILING))
    shard_size = min(50_000, max(200, ceil(throughput / jobs * TARGET_SHARD_SECONDS)))
    baseline = min(180, max(15, ceil(state.latency_p95 * 3 + 5))) if state.latency_p95 else 45
    timeout = min(180, max(baseline, ceil(state.timeout_lower_bound_seconds * 1.5 + 5)))
    return shard_size, timeout
