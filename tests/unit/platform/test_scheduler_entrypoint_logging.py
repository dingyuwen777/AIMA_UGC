from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast

import pytest
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.scheduler import SchedulerTickResult
from aima_ugc.entrypoints import scheduler_main


class _StopLoop(RuntimeError):
    pass


@pytest.mark.parametrize(
    ("result", "expected_level"),
    [
        (
            SchedulerTickResult(scanned=0, initialized=0, enqueued=0, skipped=0, failed=0),
            logging.DEBUG,
        ),
        (
            SchedulerTickResult(scanned=3, initialized=1, enqueued=0, skipped=0, failed=0),
            logging.INFO,
        ),
        (
            SchedulerTickResult(scanned=3, initialized=0, enqueued=1, skipped=1, failed=0),
            logging.INFO,
        ),
        (
            SchedulerTickResult(scanned=3, initialized=0, enqueued=0, skipped=0, failed=1),
            logging.WARNING,
        ),
    ],
)
def test_scheduler_tick_only_uses_info_when_work_happened(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    result: SchedulerTickResult,
    expected_level: int,
) -> None:
    logger = logging.getLogger("aima_ugc.test.scheduler.loop")
    runtime = cast(PlatformRuntime, SimpleNamespace(logger=logger))
    monkeypatch.setattr(scheduler_main, "run_scheduler_once", lambda _runtime: result)

    def stop_after_first_tick(_seconds: float) -> None:
        raise _StopLoop

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        with pytest.raises(_StopLoop):
            scheduler_main.run_scheduler_loop(runtime, sleep=stop_after_first_tick)

    records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "scheduler.tick.completed"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == expected_level
    assert record.scanned == result.scanned
    assert record.initialized == result.initialized
    assert record.enqueued == result.enqueued
    assert record.skipped == result.skipped
    assert record.failed == result.failed
