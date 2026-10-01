"""实际长尾日志暴露的容量误判与有限任务回归。"""

from aima_ugc.modules.analysis.adaptive_capacity import CapacityObservation, CapacityState


def test_sparse_validation_repairs_do_not_restart_healthy_capacity_search():
    """重放最新运行：稀疏格式修复不能令充分成功的容量长期停在100。"""
    state = CapacityState(current=100, latency_p95=12, declared_ceiling=2500)
    for index in range(30):
        count = max(20, state.current // 5)
        state = state.observe(
            CapacityObservation(
                seconds=2,
                persisted=count,
                requests=count + 1,
                started=count + 1,
                validation_failed=int(index % 10 == 0),
                p95_seconds=12,
            )
        )
    assert state.current > 100


def test_short_peak_and_trough_cannot_reject_a_healthy_probe():
    """2秒峰值不能成为安全档基线，候选必须跨模型响应周期累计后比较。"""
    state = CapacityState(current=125, last_safe=100, last_safe_throughput=10, latency_p95=12)
    for count in (20, 32, 18, 21, 32, 27):
        state = state.observe(
            CapacityObservation(seconds=2, persisted=count, requests=count, p95_seconds=12)
        )
        assert state.current >= 125
        assert state.unsafe is None


def test_sparse_invalid_immature_sample_cannot_change_search_phase():
    """日志中的1/13格式错误尚未成熟，只等有效证据，不重置搜索。"""
    state = CapacityState(current=100, last_safe=50, phase="exploring")
    result = state.observe(
        CapacityObservation(
            seconds=3.118,
            persisted=12,
            failed=1,
            validation_failed=1,
            requests=13,
            mature=False,
        )
    )
    assert result.phase == state.phase
    assert result.current == 100


def test_idle_gap_discards_unfinished_capacity_evidence():
    """无请求的空闲阶段不能把旧候选计数拼入下一批的快速窗口。"""
    state = CapacityState(current=100, evidence_seconds=4, evidence_persisted=45)
    result = state.observe(CapacityObservation(seconds=60, demand=False))
    assert result.current == 100
    assert result.evidence_seconds == result.evidence_persisted == 0


def test_local_limit_discards_candidate_even_when_success_sample_is_small():
    """三个超时允许闭窗，但本机受限的低样本也必须丢弃候选累计。"""
    state = CapacityState(
        current=100,
        last_safe=50,
        last_safe_throughput=3,
        latency_p95=12,
        evidence_seconds=4,
        evidence_persisted=20,
    )
    result = state.observe(
        CapacityObservation(
            seconds=2,
            persisted=1,
            requests=10,
            timeouts=3,
            local_limited=True,
            demand=True,
        )
    )
    assert result.current == 100 and result.last_safe == 50
    assert result.evidence_seconds == result.evidence_persisted == 0


def test_one_timeout_with_improving_successes_does_not_invent_capacity_boundary() -> None:
    """本次 1/34 超时不能覆盖同时上升的成功吞吐证据。"""
    state = CapacityState(
        current=20,
        last_safe=10,
        safe_bound=10,
        throughput_ewma=0.764,
        last_safe_throughput=0.78,
        latency_p95=16.64,
    )
    result = state.observe(
        CapacityObservation(
            seconds=25.252,
            persisted=32,
            requests=34,
            started=33,
            timeouts=1,
            p95_seconds=64,
            timeout_lower_bound_seconds=45.114,
            demand=True,
        )
    )
    assert result.current > 20
    assert result.unsafe is None


def test_tail_timeout_is_not_evidence_of_saturated_model_capacity() -> None:
    """尾部只有一个慢请求时不将低负载误记成模型容量上限。"""
    state = CapacityState(current=200, last_safe=200)
    result = state.observe(CapacityObservation(seconds=45, requests=1, timeouts=1, demand=False))
    assert result.current == 200
    assert result.unsafe is None


def test_healthy_recovery_does_not_wait_three_latency_scaled_windows() -> None:
    """已有成功证明且时间充分时立即恢复探测，不再等待三个长窗口。"""
    state = CapacityState(
        current=10, last_safe=10, safe_bound=10, unsafe=20, phase="cooldown", cooldown_windows=3
    )
    result = state.observe(
        CapacityObservation(
            seconds=25,
            requests=24,
            persisted=24,
            started=24,
            p95_seconds=32,
            demand=True,
        )
    )
    assert result.current > 10


def test_explicit_rate_quota_does_not_invent_concurrency_ceiling() -> None:
    """明确的发送速率配额优先约束 RPS，不伪造并发拒绝证据。"""
    state = CapacityState(current=100)
    result = state.observe(
        CapacityObservation(seconds=2, requests=20, started=20, rate_limited=5, rate_only_limited=5)
    )
    assert result.current == 100 and result.unsafe is None
    assert result.rps == 7


def test_local_limit_and_immature_cohort_cannot_create_safe_or_unsafe_model_evidence():
    """本地受限和旧阶段结果都不能充当新模型容量的成功证明。"""
    state = CapacityState(current=100)
    for sample in (
        CapacityObservation(seconds=10, persisted=100, requests=100, local_limited=True),
        CapacityObservation(seconds=10, persisted=100, requests=100, mature=False),
    ):
        result = state.observe(sample)
        assert result.current == 100
        assert result.last_safe == 0 and result.unsafe is None
