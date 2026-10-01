"""自适应容量的可观察行为与动态调度回归。"""

from threading import Event

import pytest
from aima_ugc.contracts.administration import ProviderConfigCreateRequest
from aima_ugc.modules.analysis.adaptive_capacity import (
    GLOBAL_CONCURRENCY_CEILING,
    CapacityObservation,
    CapacityState,
    learned_run_limits,
    shard_capacity,
)
from aima_ugc.modules.analysis.concurrent_labeling import run_bounded_concurrently
from pydantic import ValidationError


def test_executor_can_resume_from_zero_share_without_losing_input() -> None:
    ticks = 0
    completed: list[int] = []

    def tick() -> None:
        nonlocal ticks
        ticks += 1

    result = run_bounded_concurrently(
        range(5),
        task=lambda value: value,
        max_concurrency=4,
        current_capacity=lambda: 0 if ticks < 3 else 2,
        on_tick=tick,
        on_completed=lambda outcomes: completed.extend(item.item for item in outcomes),
    )
    assert sorted(completed) == list(range(5))
    assert result.peak_in_flight <= 2


def test_zero_share_still_observes_cancellation() -> None:
    stopped = Event()
    result = run_bounded_concurrently(
        [1],
        task=lambda value: pytest.fail("零份额不能发请求"),
        max_concurrency=4,
        current_capacity=lambda: 0,
        on_tick=stopped.set,
        stop_requested=stopped.is_set,
        on_completed=lambda _: None,
    )
    assert result.stopped
    assert result.completed == 0


@pytest.mark.parametrize(
    "field,value",
    [("max_concurrency", 100), ("max_rps", 3), ("timeout_seconds", 45), ("max_retries", 3)],
)
def test_llm_create_rejects_explicit_manual_capacity(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match="自动"):
        ProviderConfigCreateRequest.model_validate(
            {
                "provider_kind": "llm",
                "provider": "test",
                "display_name": "测试",
                "base_url": "https://example.invalid/v1",
                "model": "test",
                "api_key": "fake",
                field: value,
            }
        )


def _simulate_window(state: CapacityState, provider_capacity: int) -> tuple[CapacityState, int]:
    """服务端隐藏容量只用于生成响应；控制器只接收与正式链相同的观测。"""

    rate = min(state.current, state.rps) if state.rps is not None else state.current
    requests = round(rate * 10)
    persisted = min(requests, provider_capacity * 10)
    rejected = requests - persisted
    return state.observe(
        CapacityObservation(
            seconds=10,
            persisted=persisted,
            requests=requests,
            started=requests,
            rate_limited=rejected,
            p95_seconds=1.0,
            demand=rate >= state.current * 0.9,
        )
    ), persisted


@pytest.mark.parametrize("capacity", [100, 500, 2500])
def test_unknown_provider_capacity_converges_near_static_oracle(capacity: int) -> None:
    state = CapacityState()
    persisted: list[int] = []
    for _ in range(100):
        state, count = _simulate_window(state, capacity)
        persisted.append(count)
        assert 1 <= state.current <= GLOBAL_CONCURRENCY_CEILING
    # 包含周期探测代价的最后 20 窗，仍需接近静态已知容量且显著超过固定 5。
    assert sum(persisted[-20:]) / (20 * capacity * 10) >= 0.8
    assert sum(persisted[-20:]) > 20 * 5 * 10 * 10
    assert state.historical_safe <= capacity * 1.7


def test_capacity_drop_and_recovery_relearns_without_model_change() -> None:
    state = CapacityState()
    output: list[int] = []
    for capacity in [2500] * 100 + [800] * 70 + [2500] * 100:
        state, count = _simulate_window(state, capacity)
        output.append(count)
    assert sum(output[150:170]) / (20 * 800 * 10) >= 0.8
    assert sum(output[-20:]) / (20 * 2500 * 10) >= 0.8


def test_shares_do_not_multiply_capacity_when_more_shards_than_slots() -> None:
    assert [shard_capacity(2, 5, index) for index in range(5)] == [1, 1, 0, 0, 0]
    assert sum(shard_capacity(100, 7, index) for index in range(7)) == 100
    assert shard_capacity(5000, 1, 0) == 1024


def test_invalid_or_unsaturated_results_cannot_approve_larger_capacity() -> None:
    state = CapacityState()
    observed = state.observe(
        CapacityObservation(
            seconds=10,
            persisted=90,
            failed=10,
            validation_failed=10,
            requests=100,
            started=100,
            p95_seconds=1,
        )
    )
    assert observed.current == state.current
    assert observed.reason == "validation_failure_guard"
    assert (
        state.observe(
            CapacityObservation(seconds=10, persisted=100, requests=100, demand=False)
        ).current
        == state.current
    )


def test_warm_start_and_frozen_limits_are_bounded() -> None:
    learned = CapacityState(
        current=2500, last_safe=2500, historical_safe=2500, throughput_ewma=250, latency_p95=12
    )
    warmed = learned.warm_start()
    assert warmed.current == 1250
    assert warmed.last_safe == 0
    assert warmed.historical_safe == 2500
    assert learned_run_limits(learned) == (25000, 41)


def test_successful_persisted_throughput_plateau_rejects_unhelpful_concurrency() -> None:
    state = CapacityState(current=20, last_safe=10, last_safe_throughput=10.0)
    sample = CapacityObservation(
        seconds=10, persisted=100, requests=200, started=200, p95_seconds=1
    )
    state = state.observe(sample)
    assert state.current == 20 and state.reason == "confirming_throughput_plateau"
    state = state.observe(sample)
    assert state.current == 10 and state.phase == "stable"


def test_rps_can_recover_while_guard_prevents_full_concurrency() -> None:
    state = CapacityState(current=100, rps=10.0)
    observed = state.observe(
        CapacityObservation(
            seconds=10, persisted=100, requests=100, started=100, demand=False, p95_seconds=1
        )
    )
    assert observed.current == 100
    assert observed.rps > state.rps


def test_timeout_without_any_success_informs_next_run_but_not_running_timeout() -> None:
    state = CapacityState()
    _, frozen_timeout = learned_run_limits(state)
    sample = CapacityObservation(
        seconds=50, requests=10, timeouts=10, timeout_lower_bound_seconds=45, p95_seconds=45
    )
    state = state.observe(sample)
    assert state.latency_p95 == 0
    assert learned_run_limits(state)[1] >= 60
    assert frozen_timeout == 120
    for _ in range(10):
        state = state.observe(
            CapacityObservation(
                seconds=200, requests=1, timeouts=1, timeout_lower_bound_seconds=180
            )
        )
    assert learned_run_limits(state)[1] == 180
