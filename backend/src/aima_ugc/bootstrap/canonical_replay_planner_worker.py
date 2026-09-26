"""全历史 Canonical Replay 的后台输入规划执行器。"""

from __future__ import annotations

from uuid import UUID

from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.ingestion.canonical_replay import (
    CanonicalReplayPlanJobPayload,
    load_filter_snapshot,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

from .runtime import PlatformRuntime


class PostgresCanonicalReplayPlanJobExecutor:
    """把历史枚举和子 Run 创建移出 HTTP，同时保持受理时范围与目录冻结。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def execute(
        self,
        *,
        payload: CanonicalReplayPlanJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """扫描受理边界内 Artifact，再用短提交阶段原子生成全部子 Run。"""

        snapshot = load_filter_snapshot(payload.filter_snapshot)
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                record = repository.get_all_request(payload.request_id)
                if record is None:
                    return JobHandlerResult.failed("canonical_replay_plan_not_found")
                if repository.planning_status(record) == "planned":
                    return JobHandlerResult.succeeded(
                        {
                            "request_id": str(record.id),
                            "artifact_count": record.artifact_count,
                            "run_count": record.run_count,
                        }
                    )
                if record.lifecycle_status != "active":
                    return JobHandlerResult.cancelled()
                candidates = repository.list_replayable_artifacts(
                    accepted_before=payload.accepted_before
                )
        finally:
            session.close()

        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        context.heartbeat(progress=50)

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                planned = PostgresCanonicalReplayRepository(session).complete_all_plan(
                    request_id=payload.request_id,
                    accepted_before=payload.accepted_before,
                    candidates=candidates,
                    snapshot=snapshot,
                    http_request_id=None,
                )
        finally:
            session.close()
        if planned.lifecycle_status != "active":
            return JobHandlerResult.cancelled()
        return JobHandlerResult.succeeded(
            {
                "request_id": str(planned.id),
                "artifact_count": planned.artifact_count,
                "run_count": planned.run_count,
            }
        )


def canonical_replay_plan_terminal_callback(session, job: JobRecord) -> None:  # type: ignore[no-untyped-def]
    """Planner 终态后让已请求的取消/撤回继续通过父完成屏障收敛。"""

    request_id = job.payload.get("request_id")
    if request_id is not None:
        PostgresCanonicalReplayRepository(session).ensure_reversal_job_if_ready(
            UUID(str(request_id))
        )


__all__ = [
    "PostgresCanonicalReplayPlanJobExecutor",
    "canonical_replay_plan_terminal_callback",
]
