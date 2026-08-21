"""Job Worker 与 Platform Reaper 的生产执行框架。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from aima_ugc.platform.logging import log_event, log_exception_event

from .models import JobExecutionFence, JobHandlerResult, JobRecord, LeaseLostError
from .registry import JobRegistry

if TYPE_CHECKING:
    from aima_ugc.adapters.persistence.postgres.jobs import (
        PostgresJobRepository as PostgresJobRepositoryType,
    )


type SessionFactory = Callable[[], Session]

logger = logging.getLogger(__name__)


def _repository(session: Session) -> PostgresJobRepositoryType:
    # 延迟导入避免 Platform Job 包与 PostgreSQL Adapter 形成初始化环。
    from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository

    return PostgresJobRepository(session)


class JobExecutionContext:
    """Handler 的短事务 Heartbeat/Fencing 边界。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        job_id: UUID,
        lease_token: str,
        lease_seconds: int,
        initial_progress: int,
    ) -> None:
        self._session_factory = session_factory
        self._job_id = job_id
        self._lease_token = lease_token
        self._lease_seconds = lease_seconds
        self._progress = initial_progress
        self._progress_lock = Lock()
        self._heartbeat_error: Exception | None = None

    @property
    def fence(self) -> JobExecutionFence:
        """返回仅供当前 Handler 内存传递的 Fencing 能力。"""
        return JobExecutionFence(job_id=self._job_id, lease_token=self._lease_token)

    def heartbeat(self, *, progress: int) -> None:
        session = self._session_factory()
        try:
            with session.begin():
                _repository(session).heartbeat(
                    job_id=self._job_id,
                    lease_token=self._lease_token,
                    lease_seconds=self._lease_seconds,
                    progress=progress,
                )
        finally:
            session.close()
        with self._progress_lock:
            self._progress = progress

    def cancel_requested(self) -> bool:
        session = self._session_factory()
        try:
            with session.begin():
                return _repository(session).cancel_requested(
                    job_id=self._job_id,
                    lease_token=self._lease_token,
                )
        finally:
            session.close()

    def _current_progress(self) -> int:
        with self._progress_lock:
            return self._progress

    def _set_heartbeat_error(self, error: Exception) -> None:
        self._heartbeat_error = error

    def _raise_heartbeat_error(self) -> None:
        if self._heartbeat_error is not None:
            raise self._heartbeat_error


class _HeartbeatLoop:
    """按 Lease 的三分之一周期续租，不把外部工作放入数据库事务。"""

    def __init__(self, context: JobExecutionContext, *, lease_seconds: int) -> None:
        self._context = context
        self._interval_seconds = lease_seconds / 3
        self._stop = Event()
        self._thread = Thread(target=self._run, name="aima-job-heartbeat", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self._context.heartbeat(progress=self._context._current_progress())
            except LeaseLostError as exc:
                # 取消请求会主动阻止续租，但当前 Token 在 Lease 到期前仍可协作收敛。
                try:
                    if self._context.cancel_requested():
                        return
                except LeaseLostError:
                    pass
                log_event(
                    logger,
                    logging.WARNING,
                    "job.lease_lost",
                    "Job Lease 已失效。",
                    job_id=str(self._context._job_id),
                    error_type=type(exc).__name__,
                )
                self._context._set_heartbeat_error(exc)
                return
            except Exception as exc:
                log_exception_event(
                    logger,
                    logging.WARNING,
                    "job.heartbeat_failed",
                    "Job Heartbeat 执行失败。",
                    exc,
                    job_id=str(self._context._job_id),
                )
                self._context._set_heartbeat_error(exc)
                return


class JobWorker:
    """从 Registry Claim Job，并在事务外执行具体 Handler。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        registry: JobRegistry,
        worker_id: str,
        lease_seconds: int,
        retry_delay_seconds: int,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be nonnegative")
        self._session_factory = session_factory
        self._registry = registry
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._retry_delay_seconds = retry_delay_seconds

    def run_once(self) -> bool:
        """执行至多一个 Job；没有可认领工作时返回 False。"""
        session = self._session_factory()
        try:
            with session.begin():
                job = _repository(session).claim_next(
                    supported_job_types=self._registry.supported_types,
                    worker_id=self._worker_id,
                    lease_seconds=self._lease_seconds,
                )
        finally:
            session.close()

        if job is None:
            return False
        if job.lease_token is None:
            raise RuntimeError("claimed job is missing lease token")

        started = time.perf_counter()
        _log_job_started(job, worker_id=self._worker_id)
        try:
            payload = self._registry.validate_payload(
                job_type=job.job_type,
                payload_version=job.payload_version,
                payload=job.payload,
            )
        except ValidationError, ValueError:
            failed = self._fail_invalid_payload(job.id, job.lease_token)
            _log_job_terminal(
                failed,
                event="job.failed",
                worker_id=self._worker_id,
                error_code="invalid_payload",
                duration_ms=_elapsed_ms(started),
            )
            return True

        definition = self._registry.get(job.job_type)
        context = JobExecutionContext(
            session_factory=self._session_factory,
            job_id=job.id,
            lease_token=job.lease_token,
            lease_seconds=self._lease_seconds,
            initial_progress=job.progress,
        )
        heartbeat_loop = _HeartbeatLoop(context, lease_seconds=self._lease_seconds)
        heartbeat_loop.start()
        try:
            try:
                result = definition.handler(payload, context)
            except Exception as exc:
                log_exception_event(
                    logger,
                    logging.ERROR,
                    "job.execution_failed",
                    "Job Handler 执行出现未预期异常。",
                    exc,
                    job_id=str(job.id),
                    job_type=job.job_type,
                    worker_id=self._worker_id,
                    attempt=job.attempt,
                    duration_ms=_elapsed_ms(started),
                )
                raise
        finally:
            heartbeat_loop.stop()
        context._raise_heartbeat_error()
        persisted = self._apply_result(job_id=job.id, lease_token=job.lease_token, result=result)
        event = {
            "succeeded": "job.completed",
            "retry": "job.retry_scheduled",
            "failed": "job.failed",
            "cancelled": "job.cancelled",
        }[result.outcome]
        _log_job_terminal(
            persisted,
            event=event,
            worker_id=self._worker_id,
            error_code=result.error_code,
            duration_ms=_elapsed_ms(started),
        )
        return True

    def _fail_invalid_payload(self, job_id: UUID, lease_token: str) -> JobRecord:
        session = self._session_factory()
        try:
            with session.begin():
                failed = _repository(session).fail_permanent(
                    job_id=job_id,
                    lease_token=lease_token,
                    error_code="invalid_payload",
                )
                self._notify_terminal(session, failed)
        finally:
            session.close()
        return failed

    def _apply_result(
        self,
        *,
        job_id: UUID,
        lease_token: str,
        result: JobHandlerResult,
    ) -> JobRecord:
        session = self._session_factory()
        try:
            with session.begin():
                repository = _repository(session)
                if result.outcome == "succeeded":
                    persisted = repository.succeed(
                        job_id=job_id,
                        lease_token=lease_token,
                        result=result.result,
                    )
                elif result.outcome == "retry":
                    if result.error_code is None:
                        raise ValueError("retry result requires error_code")
                    persisted = repository.retry_transient(
                        job_id=job_id,
                        lease_token=lease_token,
                        error_code=result.error_code,
                        retry_delay_seconds=self._retry_delay_seconds,
                    )
                elif result.outcome == "failed":
                    if result.error_code is None:
                        raise ValueError("failed result requires error_code")
                    persisted = repository.fail_permanent(
                        job_id=job_id,
                        lease_token=lease_token,
                        error_code=result.error_code,
                    )
                elif result.outcome == "cancelled":
                    persisted = repository.mark_cancelled(job_id=job_id, lease_token=lease_token)
                else:
                    raise ValueError(f"unsupported Job outcome: {result.outcome}")
                if persisted.status in {"succeeded", "failed", "cancelled"}:
                    self._notify_terminal(session, persisted)
        finally:
            session.close()
        return persisted

    def _notify_terminal(self, session: Session, job: JobRecord) -> None:
        callback = self._registry.get(job.job_type).terminal_callback
        if callback is not None:
            callback(session, job)


class JobReaper:
    """只处理 Deadline/取消收敛，不抢 Claim 的普通 Lease takeover 职责。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        registry: JobRegistry,
        retry_delay_seconds: int,
    ) -> None:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be nonnegative")
        self._session_factory = session_factory
        self._registry = registry
        self._retry_delay_seconds = retry_delay_seconds

    def run_once(self) -> bool:
        session = self._session_factory()
        try:
            with session.begin():
                job = _repository(session).reap_next(
                    timeout_retry_job_types=self._registry.timeout_retry_types,
                    retry_delay_seconds=self._retry_delay_seconds,
                )
                if job is not None and job.status in {"failed", "cancelled"}:
                    callback = self._registry.get(job.job_type).terminal_callback
                    if callback is not None:
                        callback(session, job)
        finally:
            session.close()
        if job is not None:
            log_event(
                logger,
                logging.WARNING,
                "job.reaped",
                "Job Reaper 已处理超时或取消任务。",
                job_id=str(job.id),
                job_type=job.job_type,
                status=job.status,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                error_code=job.error_code,
            )
        return job is not None


def _log_job_started(job: JobRecord, *, worker_id: str) -> None:
    log_event(
        logger,
        logging.INFO,
        "job.started",
        "Job 已开始执行。",
        job_id=str(job.id),
        job_type=job.job_type,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        worker_id=worker_id,
        timeout_seconds=job.timeout_seconds,
    )


def _log_job_terminal(
    job: JobRecord,
    *,
    event: str,
    worker_id: str,
    error_code: str | None,
    duration_ms: int,
) -> None:
    if event == "job.failed":
        level = logging.ERROR
    elif event == "job.retry_scheduled":
        level = logging.WARNING
    else:
        level = logging.INFO
    log_event(
        logger,
        level,
        event,
        "Job 状态已持久化。",
        job_id=str(job.id),
        job_type=job.job_type,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        worker_id=worker_id,
        status=job.status,
        duration_ms=duration_ms,
        error_code=error_code or job.error_code,
    )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
