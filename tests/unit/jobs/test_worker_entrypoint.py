from __future__ import annotations

from collections.abc import Iterator

import pytest

from aima_ugc.entrypoints.worker_main import run_worker_loop


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
