"""有真实跨窗请求生命周期的有限任务与非匀速吞吐回归。"""

from dataclasses import asdict
from datetime import datetime, timedelta
from heapq import heappop, heappush
from threading import Lock

import pytest
from aima_ugc.adapters.llm.capabilities import declared_concurrency
from aima_ugc.adapters.persistence.postgres.analysis_capacity import LATENCY_BUCKETS, empty_window
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState
from aima_ugc.modules.analysis.capacity_telemetry import InFlightMeter
from aima_ugc.platform import capacity as resource_module
from aima_ugc.platform.capacity import ResourceSnapshot, analysis_http_slots
from aima_ugc.platform.time import BEIJING_TIMEZONE

from tests.unit.analysis.test_capacity_diagnostics import _MemoryCapacityRepository, _MemorySession


def test_cpu_pressure_uses_elapsed_system_times_and_clears_unavailable_samples(
    monkeypatch, tmp_path
):
    """高占用与采样失败必须区分，未知不能沿用上一次压力或伪装成空闲。"""
    now = [0.0]
    samples = iter(((100, 50), (200, 51), None, (400, 150), (500, 240)))
    monkeypatch.setattr(resource_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        resource_module.CpuPressureSampler, "_read", staticmethod(lambda: next(samples))
    )
    pressure = resource_module.CpuPressureSampler(cgroup_root=tmp_path)
    assert pressure.sample() is None
    now[0] = 2
    assert pressure.sample() == pytest.approx(0.99)
    now[0] = 4
    assert pressure.sample() is None
    now[0] = 6
    assert pressure.sample() is None
    now[0] = 8
    assert pressure.sample() == pytest.approx(0.1)


def test_database_backpressure_tracks_committed_rate_and_recovers_after_fast_commits():
    """慢入库约束本地待发量，快入库解除背压，控制计数仍只累计已提交结果。"""
    from aima_ugc.bootstrap.analysis_capacity import AnalysisCapacityFeedback

    feedback = object.__new__(AnalysisCapacityFeedback)
    feedback._lock = Lock()
    feedback._delta = empty_window()
    feedback._database_limit = 5000
    feedback._http_seconds = 120.0
    feedback._http_count = 10
    feedback.persisted(succeeded=100, failed=0, validation_failed=0, seconds=5)
    assert feedback._database_limit == 192
    feedback.persisted(succeeded=100, failed=0, validation_failed=0, seconds=0.1)
    assert feedback._database_limit == 240
    assert feedback._delta["persisted"] == 200


def test_in_flight_integral_includes_unfinished_requests_without_double_counting():
    """窗口积分包含尚未完成的占用，下一窗口不会重复累计。"""
    now = [0.0]
    meter = InFlightMeter(lambda: now[0])
    meter.start(1, 0)
    now[0] = 1
    meter.start(2, 1)
    now[0] = 2
    assert meter.take_busy_seconds() == 3
    now[0] = 4
    assert meter.take_busy_seconds() == 4
    now[0] = 5
    assert meter.finish(1) == (5, 0)
    now[0] = 6
    assert meter.finish(2) == (5, 1)
    assert meter.take_busy_seconds() == 3
    assert meter.take_busy_seconds() == 0
    assert meter.active == 0 and meter.peak == 2


def _workload(*, count, capacity, initial=10, timeout=False, local_limit=5000, validation_every=0):
    """服务端只决定完成时刻与拒绝；窗口合并、阶段及搜索均调用正式实现。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    clock = [0.0]
    meter = InFlightMeter(lambda: clock[0])
    row = dict(
        state=asdict(CapacityState(current=initial)),
        window=empty_window(),
        revision=1,
        prompt_sha256="a" * 64,
        window_started_at=base,
        updated_at=base,
        last_adjusted_at=base,
    )
    repository = _MemoryCapacityRepository(_MemorySession(row), base)
    events = []
    unsent = list(range(count))
    completed = 0
    repaired = set()
    completed_by_second = []
    trace = []
    delta = empty_window()
    for second in range(1200):
        clock[0] = float(second)
        while events and events[0][0] <= second:
            _at, identity, rejected, timed_out = heappop(events)
            duration, epoch = meter.finish(identity)
            delta["requests"] += 1
            delta["cohort_requests"] += epoch == row["window"]["epoch"]
            if rejected:
                delta["rate_limited"] += 1
                delta["concurrency_limited"] += 1
                unsent.append(identity)
            elif timed_out:
                delta["timeouts"] += 1
                delta["timeout_lower_bound_seconds"] = duration
                unsent.append(identity)
            else:
                if (
                    validation_every
                    and identity % validation_every == 0
                    and identity not in repaired
                ):
                    repaired.add(identity)
                    unsent.append(identity)
                    delta["validation_failed"] += 1
                else:
                    completed += 1
                    delta["persisted"] += 1
                delta["latency"][
                    next(i for i, upper in enumerate(LATENCY_BUCKETS) if upper >= duration)
                ] += 1
        completed_by_second.append(completed)
        delta.update(
            busy_seconds=meter.take_busy_seconds(),
            demand=bool(unsent),
            epoch=row["window"]["epoch"],
            sample_seconds=1,
            local_limited=local_limit < row["state"]["current"],
        )
        row["window"]["reservations"] = {
            "fake": {"wanted": local_limit, "expires_at": (base + timedelta(hours=1)).isoformat()}
        }
        repository.now = base + timedelta(seconds=second)
        repository.observe(None, "fake", revision=1, prompt_sha256="a" * 64, delta=delta)
        trace.append(row["state"]["current"])
        delta = empty_window()
        while unsent and meter.active < min(row["state"]["current"], local_limit):
            identity = unsent.pop()
            server_capacity = capacity(second) if callable(capacity) else capacity
            rejected = meter.active >= server_capacity
            timed_out = timeout and identity == 0
            if timed_out:
                timeout = False
            duration = 1 if rejected else 45 if timed_out else 10 + identity % 7
            meter.start(identity, row["window"]["epoch"])
            delta["started"] += 1
            heappush(events, (second + duration, identity, rejected, timed_out))
        if completed == count:
            return second, meter.peak, completed_by_second, trace
    return 1200, meter.peak, completed_by_second, trace


def test_200_item_thinking_latency_and_single_long_tail_finish_without_slow_cooldown():
    """有限任务遇到单次长尾仍完成，不进入旧算法的漫长冷却。"""
    elapsed, peak, completed, trace = _workload(count=200, capacity=2500, initial=50, timeout=True)
    assert elapsed < 80
    assert peak > 50
    assert completed[-1] == 200
    assert min(trace[20:]) >= 50


@pytest.mark.parametrize("count", [200, 200000])
def test_sparse_invalid_outputs_finish_every_item_and_keep_searching(count):
    """稀疏HTTP200格式错误仍逐条修复，小任务完整完成、大任务持续利用容量。"""
    elapsed, peak, completed, trace = _workload(
        count=count,
        capacity=2500,
        initial=50,
        validation_every=200,
    )
    assert peak > 50
    if count == 200:
        assert completed[-1] == count and elapsed < 80
    else:
        assert (completed[600] - completed[300]) / 300 >= 2500 / 13 * 0.8
        assert max(trace) >= 2000


@pytest.mark.parametrize("capacity", [100, 500, 2500])
def test_long_workload_with_variable_model_latency_approaches_static_capacity(capacity):
    """非匀速长任务在不同模型容量下逼近相同时延的静态参照。"""
    _elapsed, _peak, completed, trace = _workload(count=200000, capacity=capacity)
    # 排除冷探测后，以相同 10–16 秒模型时延下的静态服务容量作参照。
    observed = (completed[600] - completed[300]) / 300
    assert observed >= capacity / 13 * 0.8, (observed, trace[250:350])
    assert max(trace) <= 5000


def test_local_resource_limit_does_not_poison_model_unsafe_boundary():
    """本地资源较少时仍利用本地槽位，不把机器限制写成模型上界。"""
    elapsed, peak, completed, trace = _workload(count=200, capacity=2500, local_limit=16)
    assert completed[-1] == 200 and elapsed < 220
    assert peak <= 16
    assert max(trace) <= 20


def test_variable_latency_capacity_drop_and_recovery_are_relearned():
    """长请求跨越容量突降和恢复，控制器仍重新逼近服务端可用能力。"""
    _elapsed, _peak, completed, _trace = _workload(
        count=200000, capacity=lambda second: 800 if 300 <= second < 600 else 2500
    )
    assert (completed[590] - completed[500]) / 90 >= 800 / 13 * 0.8
    assert (completed[1100] - completed[900]) / 200 >= 2500 / 13 * 0.8


@pytest.mark.parametrize(
    "cores,available,shards,expected",
    [
        (12, 14 * 1024**3, 1, 1024),
        (12, 14 * 1024**3, 3, 1024),
        (1, 128 * 1024**2, 1, 32),
        (12, 0, 1, 1),
        (0.5, 1024**3, 1, 128),
    ],
)
def test_http_slots_use_available_memory_and_effective_cpu(cores, available, shards, expected):
    """可用内存、有效核数及活动分片共同限定本地 HTTP 槽位。"""
    assert (
        analysis_http_slots(
            ResourceSnapshot(cores, 32 * 1024**3, available, "test"), shard_count=shards
        )
        == expected
    )


def test_official_model_hint_is_scoped_to_verified_endpoint_and_exact_model():
    """只有官方端点的已核验模型可以使用声明额度作为探测提示。"""
    assert declared_concurrency("https://api.deepseek.com/v1", "deepseek-flash") == 2500
    assert declared_concurrency("https://api.deepseek.com", "deepseek-pro") == 500
    assert declared_concurrency("https://proxy.example/v1", "deepseek-flash") is None
    assert declared_concurrency("https://api.deepseek.com", "unknown") is None
