import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from aima_ugc.bootstrap import artifact_cleanup
from aima_ugc.bootstrap.artifact_cleanup import ArtifactCleanupResult
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


def test_artifact_cleanup_until_drained_uses_bounded_batches_and_one_capacity_scan(
    monkeypatch,
) -> None:
    runtime = cast(PlatformRuntime, SimpleNamespace())
    observed_at = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    results = iter(
        (
            ArtifactCleanupResult(
                backfilled=7,
                scanned=500,
                deleted=490,
                failed=2,
                skipped_backend=1,
                drained=False,
            ),
            ArtifactCleanupResult(
                backfilled=0,
                scanned=500,
                deleted=495,
                failed=1,
                skipped_backend=0,
                drained=False,
            ),
            ArtifactCleanupResult(
                backfilled=0,
                scanned=120,
                deleted=118,
                failed=0,
                skipped_backend=0,
                drained=True,
            ),
        )
    )
    once_calls: list[tuple[int, bool, bool]] = []
    capacity_calls = 0

    def fake_once(
        _runtime: PlatformRuntime,
        *,
        now: datetime | None = None,
        limit: int = 100,
        backfill_retention: bool = True,
        include_capacity: bool = True,
    ) -> ArtifactCleanupResult:
        assert now == observed_at
        once_calls.append((limit, backfill_retention, include_capacity))
        return next(results)

    def fake_capacity(
        _runtime: PlatformRuntime,
        *,
        observed_at: datetime,
    ) -> tuple[int, int, int]:
        nonlocal capacity_calls
        capacity_calls += 1
        assert observed_at == datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
        return 5, 4, 1

    monkeypatch.setattr(artifact_cleanup, "run_artifact_cleanup_once", fake_once)
    monkeypatch.setattr(artifact_cleanup, "_run_media_capacity_cleanup", fake_capacity)

    result = artifact_cleanup.run_artifact_cleanup_until_drained(
        runtime,
        now=observed_at,
        batch_limit=500,
        max_batches=20,
    )

    assert once_calls == [
        (500, True, False),
        (500, False, False),
        (500, False, False),
    ]
    assert capacity_calls == 1
    assert result.backfilled == 7
    assert result.scanned == 1125
    assert result.deleted == 1107
    assert result.failed == 4
    assert result.skipped_backend == 1
    assert result.batches == 3
    assert result.drained is True


def test_artifact_cleanup_until_drained_stops_at_max_batches(monkeypatch) -> None:
    runtime = cast(PlatformRuntime, SimpleNamespace())
    observed_at = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    once_calls = 0

    def fake_once(
        _runtime: PlatformRuntime,
        *,
        now: datetime | None = None,
        limit: int = 100,
        backfill_retention: bool = True,
        include_capacity: bool = True,
    ) -> ArtifactCleanupResult:
        nonlocal once_calls
        once_calls += 1
        assert now == observed_at
        assert limit == 500
        assert include_capacity is False
        assert backfill_retention is (once_calls == 1)
        return ArtifactCleanupResult(
            backfilled=1 if once_calls == 1 else 0,
            scanned=500,
            deleted=500,
            failed=0,
            skipped_backend=0,
            drained=False,
        )

    monkeypatch.setattr(artifact_cleanup, "run_artifact_cleanup_once", fake_once)
    monkeypatch.setattr(
        artifact_cleanup,
        "_run_media_capacity_cleanup",
        lambda _runtime, *, observed_at: (0, 0, 0),
    )

    result = artifact_cleanup.run_artifact_cleanup_until_drained(
        runtime,
        now=observed_at,
        batch_limit=500,
        max_batches=2,
    )

    assert once_calls == 2
    assert result.backfilled == 1
    assert result.scanned == 1000
    assert result.deleted == 1000
    assert result.batches == 2
    assert result.drained is False
