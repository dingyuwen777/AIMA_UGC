"""Scheduler 进程装配与 PostgreSQL 持久化调度 tick。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.scheduled_keywords import (
    MissingScheduledKeywordPackError,
    PostgresScheduledKeywordSnapshotReader,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.contracts.collection import ProviderPlatformCapabilityV1
from aima_ugc.modules.collection.collection_run_job import (
    COLLECTION_RUN_JOB_TYPE,
    COLLECTION_RUN_PAYLOAD_VERSION,
    CollectionRunJobPayload,
)
from aima_ugc.modules.collection.execution import CollectionExecutionService
from aima_ugc.modules.collection.planning import CollectionPlanningService, CollectionPlanRecord
from aima_ugc.modules.collection.scheduled_scopes import (
    ScheduledKeywordPackSnapshot,
    build_scheduled_scope_snapshot,
)
from aima_ugc.modules.collection.scheduler import (
    ScheduleExpressionError,
    SchedulerBacklogLimitError,
    resolve_scheduler_plan,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.logging import log_event

from .runtime import PlatformRuntime, create_platform_runtime

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SchedulerTickResult:
    """一次 Scheduler 预扫与短事务处理结果。"""

    scanned: int
    initialized: int
    enqueued: int
    skipped: int
    failed: int = 0


def create_scheduler_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Scheduler 所需的共享 Platform runtime。"""
    return create_platform_runtime("scheduler", settings=settings)


def run_scheduler_once(
    runtime: PlatformRuntime,
    *,
    now: datetime | None = None,
    scan_limit: int = 100,
) -> SchedulerTickResult:
    """执行一次 Scheduler tick；坏 Plan 只回滚自己的短事务，不终止其他 Plan。"""
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
    failed = 0
    for plan_id in plan_ids:
        session = runtime.database.new_session()
        try:
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

                    provider_snapshots = _resolve_provider_snapshots(session, plan)
                    keyword_catalog = PostgresScheduledKeywordSnapshotReader(session).read(
                        plan.keyword_pack_ids
                    )
                    scope_snapshot = build_scheduled_scope_snapshot(
                        plan_platforms=tuple(item.platform for item in plan.platforms),
                        entries=keyword_catalog.entries,
                        keyword_packs=keyword_catalog.keyword_packs,
                    )
                    _require_scope_for_every_platform(plan, scope_snapshot.scopes)

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
                        timeout_seconds=_scheduled_job_timeout_seconds(
                            decision.enqueue_for,
                            decision.next_run_at,
                        ),
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
                        config_snapshot=_scheduled_run_snapshot(
                            plan,
                            decision.enqueue_for,
                            provider_snapshots=provider_snapshots,
                            keyword_packs=scope_snapshot.keyword_packs,
                            keyword_scope_count=len(scope_snapshot.scopes),
                        ),
                        scopes=scope_snapshot.scopes,
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
            except (
                MissingScheduledKeywordPackError,
                ScheduleExpressionError,
                SchedulerBacklogLimitError,
                ValueError,
            ) as exc:
                session.rollback()
                failed += 1
                log_event(
                    logger,
                    logging.ERROR,
                    "scheduler.plan.rejected",
                    "Scheduler 已对非法 Plan fail closed，并继续处理其他 Plan。",
                    plan_id=str(plan_id),
                    error_type=type(exc).__name__,
                )
        finally:
            session.close()

    return SchedulerTickResult(
        scanned=len(plan_ids),
        initialized=initialized,
        enqueued=enqueued,
        skipped=skipped,
        failed=failed,
    )


def _resolve_provider_snapshots(session, plan: CollectionPlanRecord) -> tuple[dict[str, object], ...]:
    """在 Run 创建事务内验证路由并冻结非 Secret Provider 执行配置。"""
    provider_repository = PostgresProviderConfigRepository(session)
    registry = build_default_provider_registry()
    snapshots: list[dict[str, object]] = []
    for item in plan.platforms:
        provider_config = provider_repository.get(item.provider_config_id)
        if provider_config is None:
            raise ValueError(f"Plan 引用 Provider Config 不存在: {item.provider_config_id}")
        route = registry.resolve(config=provider_config, platform=item.platform)
        _validate_search_config(route.capability, item.config)
        snapshots.append(_provider_snapshot(provider_config, item.platform, item.config))
    return tuple(snapshots)


def _provider_snapshot(
    provider_config: ProviderConfig,
    platform: str,
    config: dict[str, object],
) -> dict[str, object]:
    return {
        "platform": platform,
        "provider_config_id": str(provider_config.id),
        "provider": provider_config.provider,
        "base_url": provider_config.base_url,
        # 只冻结 Secret 引用身份；Secret 文件内容仍可在同一 ref 下合规轮换。
        "secret_ref": provider_config.secret_ref,
        "config": dict(config),
    }


def _validate_search_config(
    capability: ProviderPlatformCapabilityV1,
    config: dict[str, object],
) -> None:
    search = capability.operation("keyword_search")
    if search is None:
        raise ValueError(f"Provider/Platform 缺少 keyword_search: {capability.platform}")
    allowed_keys = {"sort_mode", "published_within", "duration", "content_type"}
    unknown = set(config) - allowed_keys
    if unknown:
        raise ValueError(f"Plan 平台配置包含未声明字段: {', '.join(sorted(unknown))}")

    _validate_config_choice(config, "sort_mode", search.supported_sort_modes)
    _validate_config_choice(config, "published_within", search.supported_time_filters)
    _validate_config_choice(config, "duration", search.supported_duration_filters)
    _validate_config_choice(config, "content_type", search.supported_content_types)


def _validate_config_choice(
    config: dict[str, object],
    key: str,
    supported: tuple[str, ...],
) -> None:
    if key not in config:
        return
    raw = config[key]
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"Plan 平台配置 {key} 必须是非空字符串")
    value = raw.strip()
    if not supported or value not in supported:
        raise ValueError(f"Plan 平台配置 {key}={value} 不受当前 Capability 支持")


def _require_scope_for_every_platform(plan: CollectionPlanRecord, scopes) -> None:  # type: ignore[no-untyped-def]
    expected = {item.platform for item in plan.platforms}
    actual = {scope.platform for scope in scopes}
    missing = expected - actual
    if missing:
        raise ValueError(f"Plan 目标平台没有可用关键词: {', '.join(sorted(missing))}")
    if not scopes:
        raise ValueError("Plan 无可执行 Collection Scope")


def _scheduled_job_timeout_seconds(scheduled_for: datetime, next_run_at: datetime) -> int:
    """Scheduled Run 的不可续期 Deadline 与下一逻辑 slot 对齐，不使用固定 300 秒魔数。"""
    seconds = int((next_run_at - scheduled_for).total_seconds())
    if seconds < 1:
        raise ValueError("Scheduler 下一逻辑 slot 必须晚于当前 scheduled_for")
    return seconds


def _scheduled_job_idempotency_key(plan: CollectionPlanRecord, scheduled_for: datetime) -> str:
    return f"scheduled:{plan.id}:{plan.schedule_version}:{scheduled_for.isoformat()}"


def _scheduled_run_snapshot(
    plan: CollectionPlanRecord,
    scheduled_for: datetime,
    *,
    provider_snapshots: tuple[dict[str, object], ...],
    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...],
    keyword_scope_count: int,
) -> dict[str, object]:
    """冻结调度时可安全持久化的 Plan/Provider/词包执行事实，不复制 Secret 值。"""
    return {
        "schema_version": "collection-run-config.v1",
        "plan_id": str(plan.id),
        "plan_name": plan.name,
        "schedule_version": plan.schedule_version,
        "scheduled_for": scheduled_for.isoformat(),
        "timezone": plan.timezone,
        "detail_policy": plan.detail_policy,
        "comment_policy": plan.comment_policy,
        "decision_policy": plan.decision_policy.model_dump(mode="json"),
        "platforms": list(provider_snapshots),
        "keyword_pack_ids": [str(item) for item in plan.keyword_pack_ids],
        "keyword_packs": [
            {
                "id": str(item.pack_id),
                "version": item.version,
                "enabled": item.enabled,
            }
            for item in keyword_packs
        ],
        "keyword_scope_count": keyword_scope_count,
    }
