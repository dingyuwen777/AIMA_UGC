import logging
from types import SimpleNamespace
from typing import cast

import pytest
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.scheduler import SchedulerTickResult
from aima_ugc.entrypoints import scheduler_main


class _StopLoop(RuntimeError):
    pass


def test_artifact_cleanup_failure_does_not_stop_scheduler_loop(monkeypatch) -> None:
    runtime = cast(
        PlatformRuntime,
        SimpleNamespace(logger=logging.getLogger("test-artifact-cleanup-scheduler")),
    )
    cleanup_calls = 0

    def cleanup(_: PlatformRuntime):
        nonlocal cleanup_calls
        cleanup_calls += 1
        raise RuntimeError("cleanup failed")

    def stop_after_first_tick(_: float) -> None:
        raise _StopLoop

    monkeypatch.setattr(
        scheduler_main,
        "run_scheduler_once",
        lambda _: SchedulerTickResult(scanned=0, initialized=0, enqueued=0, skipped=0),
    )

    with pytest.raises(_StopLoop):
        scheduler_main.run_scheduler_loop(
            runtime,
            poll_seconds=1,
            sleep=stop_after_first_tick,
            monotonic=lambda: 0.0,
            cleanup=cleanup,
        )

    assert cleanup_calls == 1
