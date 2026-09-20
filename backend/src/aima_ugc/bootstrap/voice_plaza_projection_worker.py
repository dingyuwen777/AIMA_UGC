"""声音广场投影自动入队与分块回填执行器。"""

from __future__ import annotations

from sqlalchemy import Integer, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.voice_plaza_projection import (
    PostgresVoicePlazaProjectionRepository,
    VoicePlazaProjectionState,
)
from aima_ugc.modules.content.read_model_job import (
    VOICE_PLAZA_PROJECTION_JOB_MAX_ATTEMPTS,
    VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION,
    VOICE_PLAZA_PROJECTION_JOB_PRIORITY,
    VOICE_PLAZA_PROJECTION_JOB_TIMEOUT_SECONDS,
    VOICE_PLAZA_PROJECTION_JOB_TYPE,
    VoicePlazaProjectionJobPayload,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table

from .runtime import PlatformRuntime

_BATCH_SIZE = 500
_BATCHES_PER_JOB = 5


class PostgresVoicePlazaProjectionJobExecutor:
    """按已提交 UUID 游标回填，失败重试不会重复推进检查点。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        """绑定共享 Runtime，每个批次自行创建短事务。"""

        self._runtime = runtime

    def execute(
        self,
        *,
        payload: VoicePlazaProjectionJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """循环推进回填并在批次之间续租、检查取消。"""

        try:
            for _ in range(_BATCHES_PER_JOB):
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        state, processed = PostgresVoicePlazaProjectionRepository(
                            session
                        ).project_next_batch(
                            fence=fence,
                            batch_size=_BATCH_SIZE,
                            expected_generation=payload.generation,
                        )
                finally:
                    session.close()

                if state.generation != payload.generation:
                    return JobHandlerResult.succeeded(
                        {
                            "superseded": True,
                            "generation": payload.generation,
                            "current_generation": state.generation,
                        }
                    )
                if state.status == "ready":
                    return JobHandlerResult.succeeded(
                        {
                            "complete": True,
                            "generation": state.generation,
                            "projected_count": state.projected_count,
                            "total_content_count": state.total_content_count or 0,
                        }
                    )
                total = max(state.total_content_count or 0, 1)
                context.heartbeat(progress=min(99, int(state.projected_count * 100 / total)))
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
                if processed <= 0:
                    return JobHandlerResult.retry("voice_plaza_projection_no_progress")
            return JobHandlerResult.succeeded(
                {
                    "complete": False,
                    "generation": state.generation,
                    "projected_count": state.projected_count,
                    "total_content_count": state.total_content_count or 0,
                }
            )
        except LeaseLostError:
            raise
        except SQLAlchemyError:
            return JobHandlerResult.retry("voice_plaza_projection_database_error")


def ensure_voice_plaza_projection_backfill_job(
    runtime: PlatformRuntime,
) -> JobRecord | None:
    """Worker 启动时幂等确保未完成的投影代次存在一个持久 Job。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            projection = PostgresVoicePlazaProjectionRepository(session)
            state = projection.get_state(for_update=True)
            if state.status == "ready":
                return None
            jobs = PostgresJobRepository(session)
            generation = jobs_table.c.payload["generation"].astext.cast(Integer)
            active_id = session.scalar(
                select(jobs_table.c.id)
                .where(
                    jobs_table.c.job_type == VOICE_PLAZA_PROJECTION_JOB_TYPE,
                    generation == state.generation,
                    jobs_table.c.status.in_(("queued", "running")),
                )
                .order_by(jobs_table.c.created_at.desc(), jobs_table.c.id.desc())
                .limit(1)
            )
            if active_id is not None:
                return jobs.get(active_id)
            existing_id = session.scalar(
                select(jobs_table.c.id)
                .where(
                    jobs_table.c.job_type == VOICE_PLAZA_PROJECTION_JOB_TYPE,
                    generation == state.generation,
                )
                .limit(1)
            )
            if existing_id is not None:
                state = projection.restart_generation(state)
            return _enqueue_projection_job(session, state)
    finally:
        session.close()


def voice_plaza_projection_job_terminal_callback(session: Session, job: JobRecord) -> None:
    """当前切片成功落库时，在同一事务串接下一低优先级切片。"""

    if job.status != "succeeded":
        return
    payload = VoicePlazaProjectionJobPayload.model_validate(job.payload)
    projection = PostgresVoicePlazaProjectionRepository(session)
    state = projection.get_state(for_update=True)
    if state.generation != payload.generation or state.status == "ready":
        return
    _enqueue_projection_job(session, state)


def _enqueue_projection_job(
    session: Session,
    state: VoicePlazaProjectionState,
) -> JobRecord:
    """按代次和已提交检查点幂等创建一个有界回填切片。"""

    payload = VoicePlazaProjectionJobPayload(generation=state.generation).model_dump(mode="json")
    return PostgresJobRepository(session).enqueue(
        job_type=VOICE_PLAZA_PROJECTION_JOB_TYPE,
        payload_version=VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION,
        payload=payload,
        internal_idempotency_key=(
            f"voice-plaza-projection-backfill:{state.generation}:{state.projected_count}"
        ),
        request_id=None,
        priority=VOICE_PLAZA_PROJECTION_JOB_PRIORITY,
        max_attempts=VOICE_PLAZA_PROJECTION_JOB_MAX_ATTEMPTS,
        timeout_seconds=VOICE_PLAZA_PROJECTION_JOB_TIMEOUT_SECONDS,
    )


__all__ = [
    "PostgresVoicePlazaProjectionJobExecutor",
    "ensure_voice_plaza_projection_backfill_job",
    "voice_plaza_projection_job_terminal_callback",
]
