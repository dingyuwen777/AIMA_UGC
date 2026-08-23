"""Worker 进程正式装配与常驻执行入口。"""

from __future__ import annotations

import logging
import os
import socket
import time
from collections.abc import Callable

from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_reaper,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.platform.jobs import JobReaper, JobWorker
from aima_ugc.platform.logging import log_event

_WORKER_LEASE_SECONDS = 120
_RETRY_DELAY_SECONDS = 5
_IDLE_SLEEP_SECONDS = 0.2
_REAPER_INTERVAL_SECONDS = 5.0


def run_worker_loop(
    worker: JobWorker,
    reaper: JobReaper,
    *,
    idle_sleep_seconds: float = _IDLE_SLEEP_SECONDS,
    reaper_interval_seconds: float = _REAPER_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    stop_requested: Callable[[], bool] | None = None,
) -> None:
    """持续 Claim Job，并以低频 Reaper 收敛超时/取消状态。"""

    if idle_sleep_seconds <= 0:
        raise ValueError("Worker idle_sleep_seconds 必须大于 0")
    if reaper_interval_seconds <= 0:
        raise ValueError("Worker reaper_interval_seconds 必须大于 0")
    should_stop = stop_requested or (lambda: False)
    next_reap_at = monotonic()

    while not should_stop():
        did_work = worker.run_once()
        did_reap = False
        now = monotonic()
        if now >= next_reap_at:
            did_reap = reaper.run_once()
            next_reap_at = now + reaper_interval_seconds
        if not did_work and not did_reap:
            sleep(idle_sleep_seconds)


def main() -> None:
    """启动正式 PostgreSQL Job Worker；Ctrl+C 时关闭共享 Runtime。"""

    runtime = create_worker_runtime()
    registry = create_collection_job_registry(runtime=runtime)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id=worker_id,
        lease_seconds=_WORKER_LEASE_SECONDS,
        retry_delay_seconds=_RETRY_DELAY_SECONDS,
    )
    reaper = create_job_reaper(
        runtime=runtime,
        registry=registry,
        retry_delay_seconds=_RETRY_DELAY_SECONDS,
    )
    log_event(
        runtime.logger,
        logging.INFO,
        "worker.started",
        "Worker 已启动",
        worker_id=worker_id,
        supported_job_types=registry.supported_types,
    )
    try:
        run_worker_loop(worker, reaper)
    except KeyboardInterrupt:
        log_event(
            runtime.logger,
            logging.INFO,
            "worker.stopped",
            "Worker 收到停止信号",
            worker_id=worker_id,
        )
    finally:
        runtime.close()


__all__ = [
    "create_collection_job_registry",
    "create_job_reaper",
    "create_job_worker",
    "create_worker_runtime",
    "main",
    "run_worker_loop",
]


if __name__ == "__main__":
    main()
