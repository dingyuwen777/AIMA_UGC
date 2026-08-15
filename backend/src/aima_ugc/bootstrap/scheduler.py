"""Scheduler 进程装配与 PostgreSQL 持久化调度 tick。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.collection.collection_run_job import (
    COLLECTION_RUN_JOB_TYPE,
    COLLECTION_RUN_PAYLOAD_VERSION,
    CollectionRunJobPayload,
)
from aima_ugc.modules.collection.execution import CollectionExecutionService
from aima_ugc.modules.collection.planning import CollectionPlanningService, CollectionPlanRecord
from aima_ugc.modules.collection.scheduler import resolve_scheduler_plan
from aima_ugc.platform.config import PlatformSettings

from .runtime import PlatformRuntime, create_platform_runtime


@dataclass(frozen=True, slots=True)
class SchedulerTickResult:
    """一次 Scheduler 预扫与短事务处理结果。"""

    scanned: int
    initialized: int
    enqueued: int
    skipped: int


def create_scheduler_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Scheduler 所需的共享 Platform runtime。"""
    return create_platform_runtime("scheduler", settings=settings)


def run_scheduler_once(
    runtime: PlatformRuntime,
    *,
    now: datetime | None = None,
    scan_limit: int = 100,
) -> SchedulerTickResult:
    """执行一次 Scheduler tick；每个 Plan 使用独立短事务和行锁。"""
    observed_at = datetime.now(UTC) if now is None else now
    if observed_at.utcoffset() is None:
        raise ValueError("Scheduler now 必须包含时区")

    scan_session = runtime.database.new_session()
    try:
        with scan_session.begin():
            plan_ids = PostgresCollectionPlanningRepository(scan_session).list_schedulable_plan_ids(
                now=observed_at, limit=scan_limit
            )
    finally:
        scan_session.close()

    initialized = 0
    enqueued = 0
    skipped = 0
    for plan_id in plan_ids:
        session = runtime.database.new_session()
        try:
            with session.begin():
                planning_repository = PostgresCollectionPlanningRepository(session)
                plan = planning_repository.get_plan_for_update(plan_id)
                if plan is None:
                    continue

                decision = resolve_scheduler_plan(plan, now=observed_at)
                if not plan.enabled or plan.schedule_expr is None:
                    continue
                if decision.initialized:
                    if decision.next_run_at is None:  # pragma: no cover - 领域结果不允许
                        raise RuntimeError("initialized Scheduler decision 缺少 next_run_at")
                    planning_repository.update_schedule_cursor(
                        plan_id=plan.id,
                        schedule_version=plan.schedule_version,
                        next_run_at=decision.next_run_at,
                        last_scheduled_at=plan.last_scheduled_at,
                    )
                    initialized += 1
                    continue

                if decision.enqueue_for is None:
                    continue
                if decision.next_run_at is None:  # pragma: no cover - 领域结果不允许
                    raise RuntimeError("due Scheduler decision 缺少 next_run_at")

                planning_service = CollectionPlanningService(planning_repository)
                for skipped_slot in decision.skipped:
                    planning_service.record_skipped_occurrence(
                        plan_id=plan.id,
                        schedule_version=plan.schedule_version,
                        scheduled_for=skipped_slot.scheduled_for,
                        skip_reason=skipped_slot.reason,
                    )

                job = PostgresJobRepository(session).enqueue(
                    job_type=COLLECTION_RUN_JOB_TYPE,
                    payload_version=COLLECTION_RUN_PAYLOAD_VERSION,
                    payload=CollectionRunJobPayload().model_dump(mode="json"),
                    internal_idempotency_key=_scheduled_job_idempotency_key(
                        plan, decision.enqueue_for
                    ),
                    request_id=None,
                    priority=10,
                    max_attempts=2,
                    timeout_seconds=300,
                )
                occurrence = planning_service.record_enqueued_occurrence(
                    plan_id=plan.id,
                    schedule_version=plan.schedule_version,
                    scheduled_for=decision.enqueue_for,
                    job_id=job.id,
                )
                CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                    job_id=job.id,
                    trigger_type="scheduled",
                    config_snapshot=_scheduled_run_snapshot(plan, decision.enqueue_for),
                    scopes=(),
                    occurrence_id=occurrence.id,
                )
                planning_repository.update_schedule_cursor(
                    plan_id=plan.id,
                    schedule_version=plan.schedule_version,
                    next_run_at=decision.next_run_at,
                    last_scheduled_at=decision.last_scheduled_at,
                )
                enqueued += 1
                skipped += len(decision.skipped)
        finally:
            session.close()

    return SchedulerTickResult(
        scanned=len(plan_ids),
        initialized=initialized,
        enqueued=enqueued,
        skipped=skipped,
    )


def _scheduled_job_idempotency_key(plan: CollectionPlanRecord, scheduled_for: datetime) -> str:
    return f"scheduled:{plan.id}:{plan.schedule_version}:{scheduled_for.isoformat()}"


def _scheduled_run_snapshot(
    plan: CollectionPlanRecord, scheduled_for: datetime
) -> dict[str, object]:
    """冻结调度时可安全持久化的 Plan 业务事实，不复制 Provider Secret。"""
    return {
        "schema_version": "collection-run-config.v1",
        "plan_id": str(plan.id),
        "plan_name": plan.name,
        "schedule_version": plan.schedule_version,
        "scheduled_for": scheduled_for.isoformat(),
        "timezone": plan.timezone,
        "detail_policy": plan.detail_policy,
        "comment_policy": plan.comment_policy,
        "request_budget": plan.request_budget,
        "platforms": [
            {
                "platform": item.platform,
                "provider_config_id": str(item.provider_config_id),
                "config": dict(item.config),
            }
            for item in plan.platforms
        ],
        "keyword_pack_ids": [str(item) for item in plan.keyword_pack_ids],
    }
