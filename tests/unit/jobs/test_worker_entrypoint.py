from __future__ import annotations

from collections.abc import Iterator

import pytest
from aima_ugc.entrypoints.worker_main import (
    desired_worker_processes,
    run_worker_loop,
)
from aima_ugc.platform.capacity import ResourceSnapshot, worker_process_limit


class _FakeWorker:
    def __init__(self, results: Iterator[bool]) -> None:
        self._results = results
        self.calls = 0

    def run_once(self) -> bool:
        self.calls += 1
        return next(self._results)


class _FakeReaper:
    def __init__(self, results: Iterator[bool]) -> None:
        self._results = results
        self.calls = 0

    def run_once(self) -> bool:
        self.calls += 1
        return next(self._results)


def test_worker_loop_runs_worker_reaper_and_only_sleeps_when_idle() -> None:
    worker = _FakeWorker(iter((False, True)))
    reaper = _FakeReaper(iter((False,)))
    stop_checks = iter((False, False, True))
    monotonic_values = iter((0.0, 0.0, 1.0))
    sleeps: list[float] = []

    run_worker_loop(  # type: ignore[arg-type]
        worker,
        reaper,
        idle_sleep_seconds=0.25,
        reaper_interval_seconds=5.0,
        sleep=sleeps.append,
        monotonic=lambda: next(monotonic_values),
        stop_requested=lambda: next(stop_checks),
    )

    assert worker.calls == 2
    assert reaper.calls == 1
    assert sleeps == [0.25]


@pytest.mark.parametrize(
    ("idle_sleep_seconds", "reaper_interval_seconds"),
    ((0.0, 5.0), (0.2, 0.0)),
)
def test_worker_loop_rejects_non_positive_intervals(
    idle_sleep_seconds: float,
    reaper_interval_seconds: float,
) -> None:
    worker = _FakeWorker(iter(()))
    reaper = _FakeReaper(iter(()))

    with pytest.raises(ValueError):
        run_worker_loop(  # type: ignore[arg-type]
            worker,
            reaper,
            idle_sleep_seconds=idle_sleep_seconds,
            reaper_interval_seconds=reaper_interval_seconds,
        )


def test_worker_pool_limit_tracks_container_resources_without_a_fixed_machine_tier() -> None:
    local = ResourceSnapshot(3.59, 3164 * 1024**2, 3000 * 1024**2, "cgroup_v2")
    server = ResourceSnapshot(4.8, 12 * 1024**3, 11 * 1024**3, "cgroup_v2")
    future = ResourceSnapshot(9.6, 25 * 1024**3, 24 * 1024**3, "cgroup_v2")
    constrained = ResourceSnapshot(0.6, 512 * 1024**2, 300 * 1024**2, "cgroup_v2")

    assert worker_process_limit(local) == 2
    assert worker_process_limit(server) == 3
    assert worker_process_limit(future) == 6
    assert worker_process_limit(constrained) == 1
    assert worker_process_limit(ResourceSnapshot(16, None, None, "host")) == 1


def test_worker_pool_scales_only_for_available_and_busy_jobs() -> None:
    assert desired_worker_processes(maximum=3, queued=0, busy=0) == 1
    assert desired_worker_processes(maximum=3, queued=1, busy=1) == 2
    assert desired_worker_processes(maximum=3, queued=2, busy=1) == 3
    assert desired_worker_processes(maximum=3, queued=10, busy=1) == 3
