"""容器资源探测与有界吞吐调节的行为回归。"""

from pathlib import Path

from aima_ugc.bootstrap.historical_import_http import _same_requested_profile
from aima_ugc.platform.capacity import (
    AdaptiveBatchController,
    AdaptiveJobWindowController,
    AdaptiveTierBatchController,
    ResourceSnapshot,
    detect_resources,
    planned_worker_resources,
    select_chunk_rows,
    select_job_window,
    worker_process_limit,
)


def test_job_window_controller_probes_one_lane_at_a_time_and_reprobes_after_stability() -> None:
    worker = ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")
    tuner = AdaptiveJobWindowController(reprobe_after=3)
    assert tuner.choose(worker, remaining_units=100)[0] == 1
    tuner.succeeded(window=1, contents=2500, duration_ms=2500)
    for _ in range(2):
        assert tuner.choose(worker, remaining_units=100)[:2] == (2, "throughput_probe")
        tuner.succeeded(window=2, contents=5000, duration_ms=3000)
    assert tuner.choose(worker, remaining_units=100)[:2] == (3, "throughput_probe")
    tuner.succeeded(window=3, contents=7500, duration_ms=5000)
    assert tuner.choose(worker, remaining_units=100)[0] == 3
    tuner.succeeded(window=3, contents=7500, duration_ms=5000)
    for _ in range(2):
        assert tuner.choose(worker, remaining_units=100)[:2] == (1, "throughput_probe")
        tuner.succeeded(window=1, contents=2500, duration_ms=2500)
    assert tuner.choose(worker, remaining_units=100)[:2] == (2, "measured_throughput")
    for _ in range(3):
        tuner.succeeded(window=2, contents=5000, duration_ms=3000)
        tuner.choose(worker, remaining_units=100)
    assert tuner.choose(worker, remaining_units=100)[:2] == (3, "throughput_probe")


def test_job_window_controller_respects_resource_database_and_work_limits() -> None:
    worker = ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")
    tuner = AdaptiveJobWindowController()
    tuner.choose(worker, remaining_units=100)
    tuner.succeeded(window=1, contents=2500, duration_ms=2500)
    assert tuner.choose(worker, remaining_units=100, database_headroom=1)[:2] == (
        1,
        "measured_throughput",
    )
    assert tuner.choose(worker, remaining_units=100, database_headroom=2)[0] == 2
    tuner.database_retry()
    assert tuner.choose(worker, remaining_units=100)[1] == "database_retry_cooldown"
    assert tuner.choose(worker, remaining_units=1)[0] == 1


def test_job_window_controller_can_lower_a_two_lane_start_after_measuring_throughput() -> None:
    worker = ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")
    tuner = AdaptiveJobWindowController(initial_window=2)
    for _ in range(2):
        assert tuner.choose(worker, remaining_units=20, database_headroom=2)[0] == 2
        tuner.succeeded(window=2, contents=2000, duration_ms=3000)
    for _ in range(2):
        assert tuner.choose(worker, remaining_units=20, database_headroom=2)[:2] == (
            1,
            "throughput_probe",
        )
        tuner.succeeded(window=1, contents=1000, duration_ms=1000)
    assert tuner.choose(worker, remaining_units=20, database_headroom=2)[0] == 1


def test_detect_resources_uses_cgroup_v2_effective_limits(tmp_path: Path) -> None:
    (tmp_path / "cpu.max").write_text("150000 100000\n", encoding="ascii")
    (tmp_path / "memory.max").write_text(str(1024 * 1024 * 1024), encoding="ascii")
    (tmp_path / "memory.current").write_text(str(300 * 1024 * 1024), encoding="ascii")

    resources = detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=12,
        host_memory_total_bytes=32 * 1024**3,
        host_memory_available_bytes=16 * 1024**3,
    )

    assert resources.cpu_cores == 1.5
    assert resources.memory_limit_bytes == 1024 * 1024 * 1024
    assert resources.memory_available_bytes == 724 * 1024 * 1024
    assert resources.source == "cgroup_v2"


def test_detect_resources_preserves_zero_host_available_memory(tmp_path: Path) -> None:
    resources = detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=8,
        host_memory_total_bytes=16 * 1024**3,
        host_memory_available_bytes=0,
    )
    assert resources.memory_available_bytes == 0
    assert select_chunk_rows(resources) == 500


def test_chunk_selection_uses_memory_without_confusing_api_cpu_with_worker_cpu() -> None:
    ample = ResourceSnapshot(8, 8 * 1024**3, 4 * 1024**3, "host")
    api_with_small_cpu_quota = ResourceSnapshot(0.96, 1582 * 1024**2, 1400 * 1024**2, "cgroup_v2")
    small = ResourceSnapshot(1, 512 * 1024**2, 180 * 1024**2, "cgroup_v2")

    assert select_chunk_rows(ample) == 2000
    assert select_chunk_rows(api_with_small_cpu_quota) == 2000
    assert select_chunk_rows(small) == 500
    assert select_job_window(ample, ceiling=2) == 2
    assert select_job_window(api_with_small_cpu_quota, ceiling=2) == 1
    assert select_job_window(small, ceiling=2) == 1


def test_job_window_tracks_generated_worker_budget_across_machine_sizes() -> None:
    api = ResourceSnapshot(0.96, 1582 * 1024**2, 1400 * 1024**2, "cgroup_v2")
    local = planned_worker_resources(
        api,
        environment={
            "AIMA_AUTO_WORKER_CPU_CORES": "3.59",
            "AIMA_AUTO_WORKER_MEMORY_MIB": "3164",
        },
    )
    server = ResourceSnapshot(4.8, 12 * 1024**3, 11 * 1024**3, "cgroup_v2")
    future = ResourceSnapshot(9.6, 25 * 1024**3, 24 * 1024**3, "cgroup_v2")

    assert select_job_window(local) == worker_process_limit(local) == 2
    assert select_job_window(server) == worker_process_limit(server) == 3
    assert select_job_window(future) == worker_process_limit(future) == 6
    assert select_job_window(server, ceiling=2) == 2
    assert planned_worker_resources(api, environment={}) == api
    assert (
        planned_worker_resources(
            api,
            environment={
                "AIMA_AUTO_WORKER_CPU_CORES": "invalid",
                "AIMA_AUTO_WORKER_MEMORY_MIB": "3164",
            },
        )
        == api
    )


def test_campaign_retry_keeps_original_automatic_choice() -> None:
    existing = {"profile": "aima-monitoring-excel.v1", "chunk_rows": 1000, "max_in_flight_jobs": 1}
    retried = {"profile": "aima-monitoring-excel.v1", "chunk_rows": 2000, "max_in_flight_jobs": 2}

    assert _same_requested_profile(existing, retried)
    assert not _same_requested_profile(existing, {**retried, "profile": "other"})


def test_batch_controller_compares_successful_throughput_then_downshifts_on_pressure() -> None:
    ample = ResourceSnapshot(4, 8 * 1024**3, 4 * 1024**3, "host")
    scarce = ResourceSnapshot(4, 8 * 1024**3, 256 * 1024**2, "cgroup_v2")
    tuner = AdaptiveBatchController(lower=250, upper=500)

    for _ in range(3):
        assert tuner.choose(ample)[0] == 500
        tuner.succeeded(size=500, rows=2000, duration_ms=2000)
    for _ in range(3):
        assert tuner.choose(ample)[0] == 250
        tuner.succeeded(size=250, rows=2000, duration_ms=1400)
    assert tuner.choose(ample)[:2] == (250, "measured_throughput")

    assert tuner.choose(scarce)[:2] == (250, "memory_pressure")
    tuner.database_retry()
    assert tuner.choose(ample)[:2] == (250, "database_retry_cooldown")
    for _ in range(3):
        tuner.succeeded(size=250, rows=2000, duration_ms=1400)
    assert tuner.choose(ample)[:2] == (250, "measured_throughput")


def test_batch_controller_automatically_reprobes_and_promotes_after_workload_changes() -> None:
    ample = ResourceSnapshot(8, 8 * 1024**3, 4 * 1024**3, "host")
    tuner = AdaptiveBatchController(lower=250, upper=500)

    for _ in range(3):
        assert tuner.choose(ample)[0] == 500
        tuner.succeeded(size=500, rows=500, duration_ms=500)
    for _ in range(3):
        assert tuner.choose(ample)[0] == 250
        tuner.succeeded(size=250, rows=250, duration_ms=300)
    for _ in range(24):
        assert tuner.choose(ample)[:2] == (500, "measured_throughput")
        tuner.succeeded(size=500, rows=500, duration_ms=500)

    for _ in range(3):
        assert tuner.choose(ample)[:2] == (250, "periodic_reprobe")
        tuner.succeeded(size=250, rows=250, duration_ms=125)
    assert tuner.choose(ample)[:2] == (250, "measured_throughput")
    for _ in range(24):
        assert tuner.choose(ample)[0] == 250
        tuner.succeeded(size=250, rows=250, duration_ms=125)

    for _ in range(3):
        assert tuner.choose(ample)[:2] == (500, "periodic_reprobe")
        tuner.succeeded(size=500, rows=500, duration_ms=150)
    assert tuner.choose(ample)[:2] == (500, "measured_throughput")


def test_tier_controller_promotes_within_one_operation_only_after_measured_gain() -> None:
    ample = ResourceSnapshot(16, 32 * 1024**3, 20 * 1024**3, "cgroup_v2")
    tuner = AdaptiveTierBatchController(tiers=(250, 500, 1000, 2000, 4000))
    for _ in range(3):
        assert tuner.choose(ample)[0] == 500
        tuner.succeeded(size=500, rows=500, duration_ms=500)
    for _ in range(3):
        assert tuner.choose(ample)[:2] == (1000, "throughput_probe")
        tuner.succeeded(size=1000, rows=1000, duration_ms=600)
    for _ in range(3):
        assert tuner.choose(ample)[:2] == (2000, "throughput_probe")
        tuner.succeeded(size=2000, rows=2000, duration_ms=900)
    assert tuner.choose(ample)[0] == 4000
    assert tuner.choose(ResourceSnapshot(16, 32 * 1024**3, 256 * 1024**2, "cgroup_v2")) == (
        250,
        "memory_pressure",
        4000,
    )
    assert tuner.choose(ResourceSnapshot(16, 32 * 1024**3, 1 * 1024**3, "cgroup_v2"))[:2] == (
        500,
        "resource_limit",
    )


def test_tier_controller_rejects_slow_growth_and_reprobes_later() -> None:
    ample = ResourceSnapshot(16, 32 * 1024**3, 20 * 1024**3, "host")
    tuner = AdaptiveTierBatchController()
    for _ in range(3):
        assert tuner.choose(ample)[0] == 500
        tuner.succeeded(size=500, rows=500, duration_ms=500)
    for _ in range(3):
        assert tuner.choose(ample)[0] == 1000
        tuner.succeeded(size=1000, rows=1000, duration_ms=1200)
    assert tuner.choose(ample)[:2] == (500, "measured_throughput")
    for _ in range(24):
        assert tuner.choose(ample)[0] == 500
        tuner.succeeded(size=500, rows=500, duration_ms=500)
    assert tuner.choose(ample)[:2] == (1000, "throughput_probe")
    tuner.database_retry()
    assert tuner.choose(ample)[:2] == (250, "database_retry_cooldown")


def test_tier_controller_uses_higher_machine_budget_but_caps_long_transactions() -> None:
    # Compose 为 Worker 留出的有效配额比 16 核/64 GiB 宿主机本身小。
    server = ResourceSnapshot(4.8, 12 * 1024**3, 11 * 1024**3, "cgroup_v2")
    future = ResourceSnapshot(9.6, 25 * 1024**3, 24 * 1024**3, "cgroup_v2")
    tuner = AdaptiveTierBatchController()
    for index, size in enumerate(range(500, 7001, 500)):
        duration = max(1, int(size * 0.75**index))
        for _ in range(3):
            assert tuner.choose(server)[0] == size
            tuner.succeeded(size=size, rows=size, duration_ms=duration)
    assert tuner.choose(server)[0] == 7000
    assert tuner.choose(future)[0] == 7500

    unknown = AdaptiveTierBatchController()
    for _ in range(3):
        assert unknown.choose(ResourceSnapshot(100, None, None, "host"))[0] == 500
        unknown.succeeded(size=500, rows=500, duration_ms=500)
    assert unknown.choose(ResourceSnapshot(100, None, None, "host"))[0] == 500

    guarded = AdaptiveTierBatchController()
    for _ in range(3):
        assert guarded.choose(server)[0] == 500
        guarded.succeeded(size=500, rows=500, duration_ms=500)
    assert guarded.choose(server)[0] == 1000
    guarded.succeeded(size=1000, rows=1000, duration_ms=3001)
    assert guarded.choose(server)[0] == 500

    slow_baseline = AdaptiveTierBatchController()
    assert slow_baseline.choose(server)[0] == 500
    slow_baseline.succeeded(size=500, rows=500, duration_ms=3001)
    assert slow_baseline.choose(server)[:2] == (250, "transaction_ceiling")


def test_replay_reversal_shares_start_and_step_but_uses_its_own_resource_budget() -> None:
    from uuid import uuid4

    from aima_ugc.bootstrap.canonical_replay_reversal_worker import (
        PostgresCanonicalReplayReversalJobExecutor,
    )

    executor = object.__new__(PostgresCanonicalReplayReversalJobExecutor)
    executor._retry_jobs = set()
    tuner = executor._new_batch_tuner(uuid4())
    assert tuner.tiers[:4] == (250, 500, 1000, 1500)
    local = ResourceSnapshot(3.59, 3164 * 1024**2, 2938 * 1024**2, "cgroup_v2")
    worker = ResourceSnapshot(4.8, 12 * 1024**3, 11 * 1024**3, "cgroup_v2")
    future = ResourceSnapshot(9.6, 25 * 1024**3, 24 * 1024**3, "cgroup_v2")
    assert tuner.choose(local)[0] == 500
    for index, size in enumerate((500, 1000)):
        duration = max(1, int(size * 0.75**index))
        for _ in range(3):
            assert tuner.choose(worker)[0] == size
            tuner.succeeded(size=size, rows=size, duration_ms=duration)
    assert tuner.choose(worker)[0] == 1500
    assert tuner.choose(future)[0] == 1500
    assert tuner.choose(ResourceSnapshot(4.8, 12 * 1024**3, 256 * 1024**2, "cgroup_v2"))[:2] == (
        250,
        "memory_pressure",
    )
