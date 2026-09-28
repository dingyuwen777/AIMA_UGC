"""全历史重筛取消协调，按短事务通知子 Job 后推进撤回屏障。"""

from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.ingestion.canonical_replay import CanonicalReplayCancellationJobPayload
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.logging import log_event, log_exception_event
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_CANCEL_BATCH_SIZE = 32
_LOGGER = logging.getLogger("aima_ugc")


class PostgresCanonicalReplayCancellationJobExecutor:
    """跳过被 Worker 占用的子 Job，持久重试后继续未完成的取消。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def execute(
        self,
        *,
        payload: CanonicalReplayCancellationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        started = perf_counter()
        batch_count = 0
        total_processed = 0
        log_event(
            _LOGGER,
            logging.INFO,
            "canonical_replay.cancellation_started",
            "历史重筛子任务取消协调开始。",
            job_id=str(fence.job_id),
            replay_request_id=str(payload.request_id),
            batch_size=_CANCEL_BATCH_SIZE,
        )
        try:
            while True:
                batch_started = perf_counter()
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        session.execute(text("SET LOCAL lock_timeout = '3s'"))
                        jobs = PostgresJobRepository(session)
                        jobs.lock_current_execution(fence)
                        repository = PostgresCanonicalReplayRepository(session)
                        current = repository.get_all_request(payload.request_id)
                        if current is None:
                            raise LookupError(payload.request_id)
                        repository.ensure_cancellation_requested(
                            payload.request_id,
                            actor_ref=(
                                payload.actor_ref
                                or current.reversal_requested_by
                                or current.created_by
                            ),
                            http_request_id=(
                                payload.http_request_id
                                or current.reversal_request_id
                                or str(fence.job_id)
                            ),
                            requested_at=(
                                payload.requested_at
                                or current.cancellation_requested_at
                                or beijing_now()
                            ),
                        )
                        processed, pending = repository.cancel_available_all_request_jobs(
                            payload.request_id, limit=_CANCEL_BATCH_SIZE
                        )
                        if not pending:
                            repository.ensure_reversal_job_if_ready(payload.request_id)
                finally:
                    session.close()
                batch_count += 1
                total_processed += processed
                log_event(
                    _LOGGER,
                    logging.INFO,
                    "canonical_replay.cancellation_batch_completed",
                    "历史重筛子任务取消协调批次已提交。",
                    job_id=str(fence.job_id),
                    replay_request_id=str(payload.request_id),
                    batch_number=batch_count,
                    processed_jobs=processed,
                    total_processed_jobs=total_processed,
                    pending=pending,
                    duration_ms=int((perf_counter() - batch_started) * 1000),
                )
                context.heartbeat(progress=0 if pending else 100)
                if not pending:
                    log_event(
                        _LOGGER,
                        logging.INFO,
                        "canonical_replay.cancellation_completed",
                        "历史重筛子任务取消协调完成，撤回屏障已推进。",
                        job_id=str(fence.job_id),
                        replay_request_id=str(payload.request_id),
                        batch_count=batch_count,
                        processed_jobs=total_processed,
                        duration_ms=int((perf_counter() - started) * 1000),
                    )
                    return JobHandlerResult.succeeded({"request_id": str(payload.request_id)})
                if processed == 0:
                    log_event(
                        _LOGGER,
                        logging.WARNING,
                        "canonical_replay.cancellation_row_busy",
                        "历史重筛子任务仍被运行事务占用，取消协调将重试。",
                        job_id=str(fence.job_id),
                        replay_request_id=str(payload.request_id),
                        batch_count=batch_count,
                        duration_ms=int((perf_counter() - started) * 1000),
                    )
                    return JobHandlerResult.retry("canonical_replay_cancellation_row_busy")
        except LeaseLostError:
            raise
        except SQLAlchemyError as exc:
            log_exception_event(
                _LOGGER,
                logging.WARNING,
                "canonical_replay.cancellation_database_retry",
                "历史重筛子任务取消协调遇到数据库异常，将重试。",
                error=exc,
                job_id=str(fence.job_id),
                replay_request_id=str(payload.request_id),
                batch_count=batch_count,
                processed_jobs=total_processed,
                sqlstate=getattr(getattr(exc, "orig", None), "sqlstate", None),
                duration_ms=int((perf_counter() - started) * 1000),
            )
            return JobHandlerResult.retry("canonical_replay_cancellation_transient_error")


def canonical_replay_cancellation_terminal_callback(session: Session, job: JobRecord) -> None:
    """协调 Job 最终失败时让父任务可见失败，允许重新发起取消。"""

    if job.status == "failed":
        request_id = CanonicalReplayCancellationJobPayload.model_validate(job.payload).request_id
        PostgresCanonicalReplayRepository(session).mark_cancellation_failed(request_id)
        log_event(
            _LOGGER,
            logging.ERROR,
            "canonical_replay.cancellation_failed",
            "历史重筛子任务取消协调已耗尽重试。",
            job_id=str(job.id),
            replay_request_id=str(request_id),
            error_code=job.error_code,
        )


__all__ = [
    "PostgresCanonicalReplayCancellationJobExecutor",
    "canonical_replay_cancellation_terminal_callback",
]
