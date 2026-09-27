"""全历史重筛取消协调，按短事务通知子 Job 后推进撤回屏障。"""

from __future__ import annotations

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

from .runtime import PlatformRuntime

_CANCEL_BATCH_SIZE = 32


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
        try:
            while True:
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        session.execute(text("SET LOCAL lock_timeout = '3s'"))
                        jobs = PostgresJobRepository(session)
                        jobs.lock_current_execution(fence)
                        repository = PostgresCanonicalReplayRepository(session)
                        processed, pending = repository.cancel_available_all_request_jobs(
                            payload.request_id, limit=_CANCEL_BATCH_SIZE
                        )
                        if not pending:
                            repository.ensure_reversal_job_if_ready(payload.request_id)
                finally:
                    session.close()
                context.heartbeat(progress=0 if pending else 100)
                if not pending:
                    return JobHandlerResult.succeeded({"request_id": str(payload.request_id)})
                if processed == 0:
                    return JobHandlerResult.retry("canonical_replay_cancellation_row_busy")
        except LeaseLostError:
            raise
        except SQLAlchemyError:
            return JobHandlerResult.retry("canonical_replay_cancellation_transient_error")


def canonical_replay_cancellation_terminal_callback(session: Session, job: JobRecord) -> None:
    """协调 Job 最终失败时让父任务可见失败，允许重新发起取消。"""

    if job.status == "failed":
        PostgresCanonicalReplayRepository(session).mark_cancellation_failed(
            CanonicalReplayCancellationJobPayload.model_validate(job.payload).request_id
        )


__all__ = [
    "PostgresCanonicalReplayCancellationJobExecutor",
    "canonical_replay_cancellation_terminal_callback",
]
