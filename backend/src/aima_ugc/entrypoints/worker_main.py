"""Worker 进程正式装配与常驻执行入口。"""

from __future__ import annotations

import logging
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.voice_plaza_projection_worker import (
    ensure_voice_plaza_projection_backfill_job,
)
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_reaper,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.platform.capacity import detect_resources, worker_process_limit
from aima_ugc.platform.jobs import JobReaper, JobWorker
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.time import beijing_now

_WORKER_LEASE_SECONDS = 120
_RETRY_DELAY_SECONDS = 5
_IDLE_SLEEP_SECONDS = 0.2
_REAPER_INTERVAL_SECONDS = 5.0
_POOL_POLL_SECONDS = 2.0
_POOL_IDLE_DOWNSHIFT_SECONDS = 30.0
_MIB = 1024 * 1024
_STARTUP_FAILURE_WINDOW_SECONDS = 30.0
_MAX_RESTART_DELAY_SECONDS = 60.0


@dataclass(slots=True)
class _WorkerRestartBackoff:
    """连续快速退出时放慢补位；稳定运行后的退出重新计数。"""

    consecutive_failures: int = 0
    retry_not_before: float = 0.0

    def record_exit(self, *, started_at: float, now: float, exit_code: int) -> float:
        """返回下一次补位前的等待秒数。"""

        if exit_code == 0 or now - started_at >= _STARTUP_FAILURE_WINDOW_SECONDS:
            self.consecutive_failures = 0
            self.retry_not_before = now
            return 0.0
        self.consecutive_failures += 1
        delay = (
            min(_MAX_RESTART_DELAY_SECONDS, float(2 ** min(self.consecutive_failures - 1, 6)))
            if self.consecutive_failures >= 3
            else 0.0
        )
        self.retry_not_before = now + delay
        return delay

    def can_spawn(self, *, now: float) -> bool:
        """退避未结束时不补位，已运行的子进程继续执行。"""

        return now >= self.retry_not_before


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


def desired_worker_processes(*, maximum: int, queued: int, busy: int) -> int:
    """只为真实等待和运行中的 Job 扩容，至少保留一个常驻进程。"""

    return min(maximum, max(1, queued + busy))


def _run_single_worker() -> None:
    """每个子进程独立持有 Runtime、数据库连接和 Job Lease。"""

    runtime = create_worker_runtime(log_instance=uuid4())
    registry = create_collection_job_registry(runtime=runtime)
    projection_job = ensure_voice_plaza_projection_backfill_job(runtime)
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
        voice_plaza_projection_job_id=(
            str(projection_job.id) if projection_job is not None else None
        ),
    )
    resources = detect_resources()
    log_event(
        runtime.logger,
        logging.INFO,
        "worker.capacity_detected",
        "Worker 可用资源已探测",
        worker_id=worker_id,
        source=resources.source,
        cpu_cores=resources.cpu_cores,
        memory_limit_mib=(
            resources.memory_limit_bytes // (1024 * 1024)
            if resources.memory_limit_bytes is not None
            else None
        ),
        memory_available_mib=(
            resources.memory_available_bytes // (1024 * 1024)
            if resources.memory_available_bytes is not None
            else None
        ),
    )
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    try:
        run_worker_loop(worker, reaper, stop_requested=lambda: stopping)
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


def _pool_pressure(
    runtime: PlatformRuntime,
    children: dict[int, subprocess.Popen[bytes]],
    maximum: int,
) -> tuple[int, set[str]]:
    """只读当前可领取队列和本容器在途 Lease，不扫描历史 Job。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            owners = {f"{socket.gethostname()}:{pid}" for pid in children}
            return PostgresJobRepository(session).pool_pressure(
                lease_owners=owners,
                queued_limit=maximum,
                now=beijing_now(),
            )
    finally:
        session.close()


def _run_worker_pool() -> None:
    """在容器总配额内按队列升档，空闲时只收缩没有在途 Job 的进程。"""

    runtime = create_worker_runtime(log_instance=uuid4())
    children: dict[int, subprocess.Popen[bytes]] = {}
    child_started_at: dict[int, float] = {}
    stopping = False
    idle_since: float | None = None
    restart_backoff = _WorkerRestartBackoff()

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    def spawn() -> None:
        child = subprocess.Popen(
            [sys.executable, "-m", "aima_ugc.entrypoints.worker_main", "--child"]
        )
        children[child.pid] = child
        child_started_at[child.pid] = time.monotonic()

    signal.signal(signal.SIGTERM, request_stop)
    try:
        initial_resources = detect_resources()
        log_event(
            runtime.logger,
            logging.INFO,
            "capacity.worker_pool_started",
            "Worker 自适应进程池已启动",
            maximum_processes=worker_process_limit(initial_resources),
            cpu_cores=initial_resources.cpu_cores,
            memory_limit_mib=(
                initial_resources.memory_limit_bytes // _MIB
                if initial_resources.memory_limit_bytes is not None
                else None
            ),
        )
        spawn()
        while not stopping:
            for pid, child in tuple(children.items()):
                if (exit_code := child.poll()) is not None:
                    del children[pid]
                    now = time.monotonic()
                    delay = restart_backoff.record_exit(
                        started_at=child_started_at.pop(pid),
                        now=now,
                        exit_code=exit_code,
                    )
                    if exit_code != 0:
                        log_event(
                            runtime.logger,
                            logging.WARNING,
                            "capacity.worker_process_exited",
                            "Worker 子进程异常退出",
                            worker_pid=pid,
                            exit_code=exit_code,
                            recent_failures=restart_backoff.consecutive_failures,
                            restart_delay_seconds=delay,
                        )
            if restart_backoff.consecutive_failures >= 3 and not children:
                raise RuntimeError("Worker 子进程连续异常退出")
            resources = detect_resources()
            maximum = worker_process_limit(resources)
            queued, busy_owners = _pool_pressure(runtime, children, maximum)
            desired = desired_worker_processes(
                maximum=maximum, queued=queued, busy=len(busy_owners)
            )
            memory_pressure = (
                resources.memory_available_bytes is not None
                and resources.memory_available_bytes < 768 * _MIB
            )
            if memory_pressure:
                desired = 1
            if len(children) < desired:
                if restart_backoff.can_spawn(now=time.monotonic()):
                    spawn()
                    idle_since = None
                    log_event(
                        runtime.logger,
                        logging.INFO,
                        "capacity.worker_pool_resized",
                        "Worker 并行进程已扩容",
                        active_processes=len(children),
                        desired_processes=desired,
                        maximum_processes=maximum,
                        queued_jobs=queued,
                        busy_processes=len(busy_owners),
                        available_memory_mib=(
                            resources.memory_available_bytes // _MIB
                            if resources.memory_available_bytes is not None
                            else None
                        ),
                    )
            elif len(children) > desired:
                now = time.monotonic()
                if idle_since is None:
                    idle_since = now - _POOL_IDLE_DOWNSHIFT_SECONDS if memory_pressure else now
                elif now - idle_since >= _POOL_IDLE_DOWNSHIFT_SECONDS:
                    idle = next(
                        (
                            child
                            for pid, child in reversed(tuple(children.items()))
                            if f"{socket.gethostname()}:{pid}" not in busy_owners
                        ),
                        None,
                    )
                    if idle is not None:
                        idle.terminate()
                        idle_since = now
                        log_event(
                            runtime.logger,
                            logging.INFO,
                            "capacity.worker_pool_resized",
                            "空闲 Worker 进程开始缩容",
                            active_processes=len(children),
                            desired_processes=desired,
                            maximum_processes=maximum,
                            queued_jobs=queued,
                            busy_processes=len(busy_owners),
                        )
            else:
                idle_since = None
            time.sleep(_POOL_POLL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
        for child in children.values():
            child.wait()
        runtime.close()


def main() -> None:
    """启动按有效资源和 Job 队列调节的 Worker 进程池。"""

    if sys.argv[1:] == ["--child"]:
        _run_single_worker()
    else:
        _run_worker_pool()


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
