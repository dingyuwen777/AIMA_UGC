"""LLM 容量的确定性控制规则；不发请求、不读数据库、不改变模型业务协议。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, sqrt

CAPACITY_MODE = "adaptive.v2"
CONTROL_VERSION = 3
SUPPORTED_CAPACITY_MODES = frozenset({"adaptive.v1", CAPACITY_MODE})
GLOBAL_CONCURRENCY_CEILING = 5_000
SHARD_CONCURRENCY_CEILING = 1_024
INITIAL_CONCURRENCY = 10
VALIDATION_RETRIES = 3
WINDOW_SECONDS = 2.0
TARGET_SHARD_SECONDS = 300
_REFINEMENT_LIMIT = 6
_RECOVERY_SECONDS = 4.0
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
    mature: bool = True
    local_limited: bool = False
    concurrency_limited: int = 0
    rate_only_limited: int = 0
    available_concurrency: int = GLOBAL_CONCURRENCY_CEILING
    cohort_requests: int = 0


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
    control_version: int = CONTROL_VERSION
    cooldown_seconds: float = 0.0
    congestion_windows: int = 0
    declared_ceiling: int | None = None
    execution_limited: bool = False
    evidence_seconds: float = 0.0
    evidence_persisted: int = 0
    evidence_failed: int = 0
    evidence_validation_failed: int = 0

    def warm_start(self) -> CapacityState:
        """配置/Prompt 变化仅降低可信度，历史容量不当作当前安全证明。"""

        return replace(
            self,
            current=min(
                self.declared_ceiling or GLOBAL_CONCURRENCY_CEILING,
                max(INITIAL_CONCURRENCY, (self.last_safe or self.current) // 2),
            ),
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
            cooldown_seconds=0.0,
            congestion_windows=0,
            reason="configuration_warm_start",
            last_adjustment_reason="configuration_warm_start",
        ).clear_evidence()

    def clear_evidence(self) -> CapacityState:
        """容量/身份改变后丢弃旧候选累计，既有成功结果和物理预留不受影响。"""

        return replace(
            self,
            evidence_seconds=0,
            evidence_persisted=0,
            evidence_failed=0,
            evidence_validation_failed=0,
        )

    def observe(self, sample: CapacityObservation) -> CapacityState:
        """先快速处理拥塞，再以成功入库速率接受健康候选和有限探测。"""

        observed = self._observe(sample)
        return observed.clear_evidence() if observed.current != self.current else observed

    def _observe(self, sample: CapacityObservation) -> CapacityState:
        """快速错误控制与跨响应周期的性能证据分开，稀疏修复不重置搜索。"""

        if sample.seconds <= 0:
            raise ValueError("观察窗时间必须大于零")
        if sample.requests == 0 and sample.persisted == 0 and sample.failed == 0:
            return self if sample.demand and not sample.local_limited else self.clear_evidence()
        physical = max(1, sample.requests)
        terminal = max(1, sample.persisted + sample.failed)
        throughput = sample.persisted / sample.seconds
        updated = replace(
            self,
            throughput_ewma=(
                throughput
                if self.throughput_ewma == 0
                else 0.3 * throughput + 0.7 * self.throughput_ewma
            )
            if sample.demand and sample.mature and not sample.local_limited
            else self.throughput_ewma,
            rate_limit_ratio=sample.rate_limited / physical,
            timeout_ratio=sample.timeouts / physical,
            transport_error_ratio=sample.transport_errors / physical,
            validation_failure_ratio=sample.validation_failed / terminal,
            timeout_lower_bound_seconds=min(
                180.0, max(self.timeout_lower_bound_seconds, sample.timeout_lower_bound_seconds)
            ),
        )
        # 单次长尾、低负载尾窗和本地资源限制都不能证明上游容量边界。
        noisy = (
            sample.timeouts + sample.transport_errors >= 3
            and (sample.timeouts + sample.transport_errors) / physical >= 0.1
        )
        latency_collapse = (
            sample.mature
            and self.latency_p95 > 0
            and sample.p95_seconds > self.latency_p95 * 2
            and throughput < self.throughput_ewma * 0.8
        )
        sustained = self.congestion_windows + 1 if noisy or latency_collapse else 0
        updated = replace(
            updated,
            congestion_windows=sustained,
            cooldown_seconds=max(0.0, self.cooldown_seconds - sample.seconds),
        )
        concurrency_rejection = sample.rate_limited > sample.rate_only_limited
        congestion = concurrency_rejection or (
            sample.demand
            and not sample.local_limited
            and (sustained >= 2 or (noisy and sample.persisted == 0 and physical >= 8))
        )
        if congestion:
            lowered = max(1, self.current // 2)
            rps = self.rps
            if sample.rate_limited and not sample.concurrency_limited:
                observed_rate = max(0.1, sample.started / sample.seconds)
                rps = max(0.1, min(rps or observed_rate, observed_rate) * 0.7)
            return replace(
                updated,
                current=lowered,
                last_safe=min(self.last_safe, lowered),
                safe_bound=(self.safe_bound if self.current > self.last_safe else 0),
                unsafe=self.current if sample.concurrency_limited or sustained >= 2 else None,
                phase="cooldown",
                rps=rps,
                stable_windows=0,
                cooldown_windows=0,
                cooldown_seconds=_RECOVERY_SECONDS,
                refinements=(
                    _REFINEMENT_LIMIT
                    if self.phase == "reprobing"
                    else self.refinements
                    if self.phase in {"refining", "cooldown"}
                    else 0
                ),
                reason="http_429" if sample.rate_limited else "sustained_service_congestion",
            )
        # RPS 是从属保护，即使它暂时让并发未满，也必须能在健康发送窗逐步恢复。
        if sample.persisted:
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
        if sample.rate_only_limited:
            observed_rate = max(0.1, sample.started / sample.seconds)
            return replace(
                updated,
                rps=max(0.1, min(self.rps or observed_rate, observed_rate) * 0.7),
                reason="request_rate_limited",
            )
        if sample.local_limited:
            return replace(updated.clear_evidence(), reason="local_capacity_limit")
        # 没有已提交成功或仍在等待首批结果时，不把低样本窗当作健康证明。
        if sample.persisted < min(8, max(2, ceil(self.current * 0.05))) or not sample.demand:
            return replace(
                updated if sample.demand else updated.clear_evidence(),
                reason="insufficient_demand_or_results",
            )
        if not sample.mature:
            return replace(updated, reason="waiting_for_probe_cohort")
        updated = replace(
            updated,
            evidence_seconds=self.evidence_seconds + sample.seconds,
            evidence_persisted=self.evidence_persisted + sample.persisted,
            evidence_failed=self.evidence_failed + sample.failed,
            evidence_validation_failed=self.evidence_validation_failed + sample.validation_failed,
            stable_windows=self.stable_windows + int(self.phase == "stable"),
        )
        evidence_terminal = max(1, updated.evidence_persisted + updated.evidence_failed)
        # 少量可修复格式错误不是容量证据；大量异常先暂停探测，仍严格修复每条。
        if (
            evidence_terminal >= 100
            and updated.evidence_validation_failed >= 5
            and updated.evidence_validation_failed / evidence_terminal > 0.01
        ):
            return replace(updated.clear_evidence(), reason="validation_failure_guard")
        # 成功量/墙钟总时长避免批量提交峰值；至少覆盖已学习响应周期且样本充分。
        horizon = max(
            WINDOW_SECONDS,
            (self.latency_p95 * 0.5)
            if self.latency_p95
            else min(sample.p95_seconds, sample.seconds),
        )
        if self.phase == "cooldown":
            # 已知安全档的恢复不重新等待完整性能试验；硬错误仍走前面的快速控制。
            horizon = WINDOW_SECONDS
        enough_results = min(100, max(2, ceil(self.current * 0.5)))
        if self.last_safe == 0:
            # 首档没有吞吐比较基线，成熟的首批成功用于开始有界探测，避免小任务等满一批。
            enough_results = min(100, max(2, ceil(self.current * 0.2)))
        if self.phase == "cooldown":
            enough_results = min(8, enough_results)
        # 大幅收益可较早接受，扣除计数波动余量；不足收益的回退仍需两个完整证据块。
        clear_gain = (
            self.current > self.last_safe
            and self.last_safe_throughput > 0
            and updated.evidence_seconds >= WINDOW_SECONDS * 2
            and updated.evidence_persisted >= max(8, ceil(self.current * 0.2))
            and (updated.evidence_persisted - 2 * sqrt(updated.evidence_persisted))
            / updated.evidence_seconds
            > self.last_safe_throughput * 1.05
        )
        if (
            updated.evidence_seconds < horizon or updated.evidence_persisted < enough_results
        ) and not clear_gain:
            return replace(updated, reason="collecting_capacity_evidence")
        throughput = updated.evidence_persisted / updated.evidence_seconds
        updated = updated.clear_evidence()
        if (
            sample.mature
            and not sample.local_limited
            and self.phase != "cooldown"
            and self.current > self.last_safe
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
        if updated.cooldown_seconds:
            return replace(updated, reason="healthy_cooldown")
        if self.phase == "stable" and not (
            self.execution_limited and sample.available_concurrency > self.current
        ):
            stable = updated.stable_windows
            if stable < _REPROBE_WINDOWS or self.current >= (
                self.declared_ceiling or GLOBAL_CONCURRENCY_CEILING
            ):
                return replace(updated, stable_windows=stable, reason="healthy_stable")
            return replace(
                updated,
                current=min(
                    self.declared_ceiling or GLOBAL_CONCURRENCY_CEILING,
                    sample.available_concurrency,
                    max(self.current + 1, ceil(self.current * 1.25)),
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
        candidate = min(
            self.declared_ceiling or GLOBAL_CONCURRENCY_CEILING,
            max(self.current, sample.available_concurrency),
            self.current * 2,
        )
        return replace(
            updated,
            current=candidate,
            phase="stable" if candidate == self.current else "exploring",
            execution_limited=candidate == self.current
            and self.current < (self.declared_ceiling or GLOBAL_CONCURRENCY_CEILING),
            reason="exponential_probe" if candidate != self.current else "execution_ceiling",
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
    baseline = min(180, max(30, ceil(state.latency_p95 * 3 + 5))) if state.latency_p95 else 120
    timeout = min(180, max(baseline, ceil(state.timeout_lower_bound_seconds * 1.5 + 5)))
    return shard_size, timeout
