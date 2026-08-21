"""Scheduler 进程入口：周期执行持久化 Scheduler tick。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime, run_scheduler_once
from aima_ugc.platform.logging import log_event

_SCHEDULER_POLL_SECONDS = 30.0


def run_scheduler_loop(
    runtime: PlatformRuntime,
    *,
    poll_seconds: float = _SCHEDULER_POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """持续执行短事务 Scheduler tick；空轮询只记 DEBUG。"""
    if poll_seconds <= 0:
        raise ValueError("Scheduler poll_seconds 必须大于 0")

    while True:
        started = time.perf_counter()
        result = run_scheduler_once(runtime)
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        if result.failed:
            level = logging.WARNING
        elif result.initialized or result.enqueued or result.skipped:
            level = logging.INFO
        else:
            level = logging.DEBUG
        log_event(
            runtime.logger,
            level,
            "scheduler.tick.completed",
            "Scheduler tick 已完成",
            scanned=result.scanned,
            initialized=result.initialized,
            enqueued=result.enqueued,
            skipped=result.skipped,
            failed=result.failed,
            duration_ms=duration_ms,
        )
        sleep(poll_seconds)


def main() -> None:
    """启动 Scheduler；Ctrl+C 时关闭共享 Platform runtime。"""
    runtime = create_scheduler_runtime()
    try:
        run_scheduler_loop(runtime)
    except KeyboardInterrupt:
        log_event(
            runtime.logger,
            logging.INFO,
            "scheduler.stopped",
            "Scheduler 收到停止信号",
        )
    finally:
        runtime.close()


__all__ = ["create_scheduler_runtime", "main", "run_scheduler_loop", "run_scheduler_once"]


if __name__ == "__main__":
    main()
