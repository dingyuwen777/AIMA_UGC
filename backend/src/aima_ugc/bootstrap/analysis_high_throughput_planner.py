"""千万级 Analysis Run 的正式 Planner、Shard 调度与终态回调。"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis_high_throughput import (
    PostgresHighThroughputAnalysisRepository,
)
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.modules.analysis.content_analysis_job import (
    CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
    CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
    CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
    CONTENT_ANALYSIS_JOB_TYPE,
    CONTENT_ANALYSIS_PLAN_JOB_TYPE,
    ContentAnalysisJobPayload,
    ContentAnalysisPlanJobPayload,
    is_analysis_all_scope_filter_snapshot,
)
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

from .runtime import PlatformRuntime

_ANALYSIS_ALL_FREEZE_BATCH_SIZE = 10_000


class HighThroughputContentAnalysisPlanJobExecutor:
    """按连续 ordinal 有界冻结全部目标，并在同一 PostgreSQL Job Runtime 内调度 Shard。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        freeze_batch_size: int = _ANALYSIS_ALL_FREEZE_BATCH_SIZE,
    ) -> None:
        """创建 Planner；冻结批次只控制数据库事务粒度，不等于 LLM Shard 大小。"""

        if freeze_batch_size <= 0:
            raise ValueError("freeze_batch_size 必须大于 0")
        self._runtime = runtime
        self._freeze_batch_size = freeze_batch_size

    def execute_plan(
        self,
        *,
        payload: ContentAnalysisPlanJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """恢复已提交 ordinal 后继续冻结；只有完整目标校验通过才启动 LLM Shard。"""

        while True:
            progress: int | None = None
            session = self._runtime.database.new_session()
            try:
                try:
                    with session.begin():
                        jobs = PostgresJobRepository(session)
                        jobs.lock_current_execution(fence)
                        repository = PostgresHighThroughputAnalysisRepository(session)
                        run = repository.get_run(payload.run_id, for_update=True)
                        if run is None:
                            return JobHandlerResult.failed("analysis_run_not_found")
                        all_scope = is_analysis_all_scope_filter_snapshot(run["filter_snapshot"])
                        if run["cancel_requested_at"] is not None:
                            return JobHandlerResult.cancelled()

                        expected_target_count = cast(int, run["target_count"])
                        frozen_count = repository.next_frozen_target_ordinal(payload.run_id)
                        if not all_scope:
                            if frozen_count == 0:
                                frozen_count = repository.freeze_run_targets(
                                    run_id=payload.run_id,
                                    target_statement=_target_statement_from_run(session, run),
                                )
                            if frozen_count != expected_target_count:
                                raise _AnalysisTargetSelectionChanged
                            created = schedule_high_throughput_analysis_run_shards(
                                session,
                                run_id=payload.run_id,
                                max_in_flight=(
                                    self._runtime.settings.analysis_run_max_in_flight_jobs
                                ),
                                request_id=None,
                            )
                            jobs.lock_current_execution(fence)
                            return JobHandlerResult.succeeded(
                                {
                                    "run_id": str(payload.run_id),
                                    "frozen_target_count": frozen_count,
                                    "scheduled_shards": created,
                                }
                            )

                        content_repository = PostgresContentQueryRepository(
                            session,
                            analysis_identity=None,
                        )
                        batch = content_repository.list_all_analysis_targets(
                            after_content_id=repository.last_frozen_content_id(payload.run_id),
                            limit=self._freeze_batch_size,
                        )
                        if not batch:
                            current_target_count = content_repository.count_all_analysis_targets()
                            if (
                                frozen_count != expected_target_count
                                or current_target_count != expected_target_count
                            ):
                                jobs.lock_current_execution(fence)
                                return JobHandlerResult.failed("content_analysis_target_changed")
                            created = schedule_high_throughput_analysis_run_shards(
                                session,
                                run_id=payload.run_id,
                                max_in_flight=(
                                    self._runtime.settings.analysis_run_max_in_flight_jobs
                                ),
                                request_id=None,
                            )
                            jobs.lock_current_execution(fence)
                            return JobHandlerResult.succeeded(
                                {
                                    "run_id": str(payload.run_id),
                                    "frozen_target_count": frozen_count,
                                    "scheduled_shards": created,
                                }
                            )

                        next_count = frozen_count + len(batch)
                        if next_count > expected_target_count:
                            jobs.lock_current_execution(fence)
                            return JobHandlerResult.failed("content_analysis_target_changed")
                        repository.append_run_targets(
                            run_id=payload.run_id,
                            start_ordinal=frozen_count,
                            targets=batch,
                        )
                        jobs.lock_current_execution(fence)
                        progress = min(
                            99,
                            int(next_count * 100 / max(expected_target_count, 1)),
                        )
                except _AnalysisTargetSelectionChanged:
                    return JobHandlerResult.failed("content_analysis_target_changed")
            finally:
                session.close()

            if progress is not None:
                context.heartbeat(progress=progress)


class _AnalysisTargetSelectionChanged(RuntimeError):
    """Preview 后目标数量变化；抛出以回滚当前冻结事务。"""


def _target_statement_from_run(session: Session, run: RowMapping) -> object:
    """从已冻结 Run Scope 恢复兼容 selected/query 目标查询。"""

    repository = PostgresContentQueryRepository(
        session,
        analysis_identity=AnalysisConfigurationIdentity(
            prompt_version=cast(str, run["prompt_version"]),
            prompt_sha256=cast(str, run["prompt_sha256"]),
            taxonomy_sha256=cast(str, run["taxonomy_sha256"]),
            model_provider=cast(str, run["model_provider"]),
            model=cast(str, run["model"]),
        ),
    )
    if is_analysis_all_scope_filter_snapshot(run["filter_snapshot"]):
        raise ValueError("all Scope 必须走有界 Planner Target 冻结")
    if run["scope"] == "query":
        return repository.freeze_target_statement(
            filters=ContentFilterSnapshot.model_validate(run["filter_snapshot"])
        )
    snapshot = cast(dict[str, object], run["filter_snapshot"])
    content_ids = tuple(UUID(str(value)) for value in cast(list[object], snapshot["content_ids"]))
    return repository.freeze_target_statement(content_ids=content_ids)


def schedule_high_throughput_analysis_run_shards(
    session: Session,
    *,
    run_id: UUID,
    max_in_flight: int,
    request_id: str | None,
) -> int:
    """锁定 Run 后从连续 Shard 元数据推导下一批 Job，不扫描 Run Target 全集。"""

    repository = PostgresHighThroughputAnalysisRepository(session)
    run = repository.get_run(run_id, for_update=True)
    if run is None:
        return 0
    if run["cancel_requested_at"] is not None:
        return 0
    available = max(max_in_flight - repository.active_shard_count(run_id), 0)
    shard_numbers = repository.next_unscheduled_shards(run_id, limit=available)
    jobs = PostgresJobRepository(session)
    for shard_no in shard_numbers:
        analysis_request_id = uuid4()
        job = jobs.enqueue(
            job_type=CONTENT_ANALYSIS_JOB_TYPE,
            payload_version=CONTENT_ANALYSIS_JOB_PAYLOAD_VERSION,
            payload=ContentAnalysisJobPayload(
                request_id=analysis_request_id,
                run_id=run_id,
                shard_no=shard_no,
            ).model_dump(mode="json"),
            internal_idempotency_key=f"content-analysis-run:{run_id}:shard:{shard_no}",
            request_id=request_id,
            priority=0,
            max_attempts=CONTENT_ANALYSIS_JOB_MAX_ATTEMPTS,
            timeout_seconds=CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS,
        )
        repository.create_run_shard(
            run_id=run_id,
            request_id=analysis_request_id,
            job_id=job.id,
            shard_no=shard_no,
        )
    return len(shard_numbers)


def create_high_throughput_analysis_job_terminal_callback(
    runtime: PlatformRuntime,
) -> Callable[[Session, JobRecord], None]:
    """使用已完成 Job Result 聚合 Run 统计，并有界补充后续 Shard。"""

    def callback(session: Session, job: JobRecord) -> None:
        """在 Job 终态事务内刷新 Analysis 父事实并调度下一批。"""

        repository = PostgresHighThroughputAnalysisRepository(session)
        if job.job_type == CONTENT_ANALYSIS_PLAN_JOB_TYPE:
            planner_payload = ContentAnalysisPlanJobPayload.model_validate(job.payload)
            repository.complete_plan_terminal(
                run_id=planner_payload.run_id,
                job_status=job.status,
                error_code=job.error_code,
            )
            return

        shard_payload = ContentAnalysisJobPayload.model_validate(job.payload)
        run_id = repository.complete_request_terminal(
            request_id=shard_payload.request_id,
            job_status=job.status,
            error_code=job.error_code,
        )
        schedule_high_throughput_analysis_run_shards(
            session,
            run_id=run_id,
            max_in_flight=runtime.settings.analysis_run_max_in_flight_jobs,
            request_id=job.request_id,
        )
        repository.refresh_run(run_id)

    return callback


__all__ = [
    "HighThroughputContentAnalysisPlanJobExecutor",
    "create_high_throughput_analysis_job_terminal_callback",
    "schedule_high_throughput_analysis_run_shards",
]
