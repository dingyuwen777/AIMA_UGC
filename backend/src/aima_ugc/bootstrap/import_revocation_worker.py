"""数据导入撤销的有界分批、断点恢复与资源感知执行器。"""

from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.import_revocation_lifecycle import (
    PostgresImportRevocationLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.reversal_shards import PostgresReversalShardRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.ingestion.reversal_shards import REVERSAL_MIN_PARALLEL_CONTENTS
from aima_ugc.modules.ingestion.revocation_jobs import DataImportRevocationJobPayload
from aima_ugc.modules.ingestion.revocation_tables import (
    historical_import_campaign_revocations_table,
    historical_import_revocation_requests_table,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.capacity import (
    AdaptiveTierBatchController,
    detect_resources,
    select_job_window,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

if TYPE_CHECKING:
    from .adaptive_shard_worker import AdaptiveShardCoordinator


class PostgresImportRevocationJobExecutor:
    """每批事务验证 Fence，并用已提交的 UUID 断点跳过完成的 Content。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._retry_jobs: set[UUID] = set()
        self.shard_coordinator: AdaptiveShardCoordinator | None = None

    def execute(
        self,
        *,
        payload: DataImportRevocationJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        started = perf_counter()
        tuner = AdaptiveTierBatchController(improvement_margin=0.20)
        if fence.job_id in self._retry_jobs:
            tuner.database_retry()
        batch_count = 0
        slowest_ms = 0
        contribution_read_ms = 0
        content_apply_ms = 0
        batch_observations: dict[int, list[int]] = {}
        try:
            impact_count, revoked_at, sources = self._load_setup(payload.campaign_id)
            if self.shard_coordinator is not None and self._can_shard(
                payload.campaign_id,
                allow_new=(
                    impact_count >= REVERSAL_MIN_PARALLEL_CONTENTS
                    and select_job_window(detect_resources()) >= 2
                ),
            ):

                def finish() -> JobHandlerResult:
                    _, total, completed, _, _ = self._apply_batch(
                        campaign_id=payload.campaign_id,
                        fence=fence,
                        limit=1,
                        revoked_at=revoked_at,
                        sources=sources,
                        finish_only=True,
                    )
                    if not completed:
                        raise RuntimeError("撤销分片完成屏障未能结清父请求")
                    return JobHandlerResult.succeeded(
                        {"campaign_id": str(payload.campaign_id), "recomputed_content_count": total}
                    )

                return self.shard_coordinator.execute_parent(
                    kind="import",
                    parent_id=payload.campaign_id,
                    remaining_contents=impact_count,
                    fence=fence,
                    context=context,
                    finish=finish,
                )
            while True:
                resources = detect_resources()
                batch_size, reason, previous = tuner.choose(resources)
                if previous != batch_size:
                    log_event(
                        self._runtime.logger,
                        logging.INFO,
                        "capacity.data_import_revocation_batch_selected",
                        "数据导入撤销批量调整",
                        campaign_id=str(payload.campaign_id),
                        previous_contents=previous,
                        selected_contents=batch_size,
                        reason=reason,
                        available_memory_mib=(
                            resources.memory_available_bytes // (1024 * 1024)
                            if resources.memory_available_bytes is not None
                            else None
                        ),
                    )
                batch_started = perf_counter()
                processed, total, completed, read_ms, apply_ms = self._apply_batch(
                    campaign_id=payload.campaign_id,
                    fence=fence,
                    limit=batch_size,
                    revoked_at=revoked_at,
                    sources=sources,
                )
                batch_ms = int((perf_counter() - batch_started) * 1000)
                contribution_read_ms += read_ms
                content_apply_ms += apply_ms
                if completed:
                    self._retry_jobs.discard(fence.job_id)
                    context.heartbeat(progress=100)
                    log_event(
                        self._runtime.logger,
                        logging.INFO,
                        "data_import.revocation_completed",
                        "数据导入撤销完成",
                        campaign_id=str(payload.campaign_id),
                        recomputed_content_count=total,
                        batch_count=batch_count,
                        slowest_batch_ms=slowest_ms,
                        contribution_read_ms=contribution_read_ms,
                        content_apply_ms=content_apply_ms,
                        batch_observations=[
                            {
                                "batch_size": size,
                                "batch_count": values[0],
                                "content_count": values[1],
                                "duration_ms": values[2],
                            }
                            for size, values in sorted(batch_observations.items())
                        ],
                        duration_ms=int((perf_counter() - started) * 1000),
                    )
                    return JobHandlerResult.succeeded(
                        {"campaign_id": str(payload.campaign_id), "recomputed_content_count": total}
                    )
                batch_count += 1
                slowest_ms = max(slowest_ms, batch_ms)
                observation = batch_observations.setdefault(batch_size, [0, 0, 0])
                observation[0] += 1
                observation[1] += processed
                observation[2] += batch_ms
                tuner.succeeded(size=batch_size, rows=processed, duration_ms=batch_ms)
                context.heartbeat(progress=min(99, int(total * 100 / max(1, impact_count))))
        except LeaseLostError:
            raise
        except LookupError, ValueError:
            return JobHandlerResult.failed("data_import_revocation_invalid")
        except SQLAlchemyError:
            self._retry_jobs.add(fence.job_id)
            return JobHandlerResult.retry("data_import_revocation_transient_error")

    def _can_shard(self, campaign_id: UUID, *, allow_new: bool) -> bool:
        session = self._runtime.database.new_session()
        try:
            existing = PostgresReversalShardRepository(session).list("import", campaign_id)
            if existing:
                return True
            if not allow_new:
                return False
            request = (
                session.execute(
                    select(historical_import_revocation_requests_table).where(
                        historical_import_revocation_requests_table.c.campaign_id == campaign_id
                    )
                )
                .mappings()
                .one()
            )
            return (
                request["checkpoint_content_id"] is None
                and request["recomputed_content_count"] == 0
            )
        finally:
            session.close()

    def process_shard(
        self,
        shard_id: UUID,
        *,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> int:
        session = self._runtime.database.new_session()
        try:
            shard = PostgresReversalShardRepository(session).get(shard_id)
            if shard is None or shard["kind"] != "import":
                raise LookupError("普通导入撤销工作单元不存在")
            campaign_id = cast(UUID, shard["import_campaign_id"])
        finally:
            session.close()
        _, revoked_at, sources = self._load_setup(campaign_id)
        tuner = AdaptiveTierBatchController(improvement_margin=0.20)
        total = 0
        while True:
            if context.cancel_requested():
                raise LeaseLostError("撤销分片已取消")
            size, _, _ = tuner.choose(detect_resources())
            started = perf_counter()
            processed, _, finished, _, _ = self._apply_batch(
                campaign_id=campaign_id,
                fence=fence,
                limit=size,
                revoked_at=revoked_at,
                sources=sources,
                shard_id=shard_id,
            )
            total += processed
            if finished:
                context.heartbeat(progress=100)
                return total
            tuner.succeeded(
                size=size,
                rows=processed,
                duration_ms=max(1, int((perf_counter() - started) * 1000)),
            )
            context.heartbeat(progress=50)

    def _load_setup(self, campaign_id: UUID) -> tuple[int, datetime, dict[str, tuple[UUID, UUID]]]:
        """只在 Job 开始时读取不可变影响、时间和平台来源。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                fact = (
                    session.execute(
                        select(historical_import_campaign_revocations_table).where(
                            historical_import_campaign_revocations_table.c.campaign_id
                            == campaign_id
                        )
                    )
                    .mappings()
                    .one()
                )
                artifact_id = session.scalar(
                    select(historical_import_revocation_requests_table.c.raw_artifact_id).where(
                        historical_import_revocation_requests_table.c.campaign_id == campaign_id
                    )
                )
                platforms = PostgresImportRevocationLifecycleRepository(
                    session
                ).campaign_contribution_platforms(campaign_id)
                if platforms and artifact_id is None:
                    raise ValueError("撤销来源缺少 Artifact")
                return (
                    int(fact["affected_content_count"]),
                    cast(datetime, fact["revoked_at"]),
                    {
                        platform: (
                            uuid5(campaign_id, f"data-import-revoke-attempt:{platform}"),
                            cast(UUID, artifact_id),
                        )
                        for platform in platforms
                    },
                )
        finally:
            session.close()

    def _apply_batch(
        self,
        *,
        campaign_id: UUID,
        fence: JobExecutionFence,
        limit: int,
        revoked_at: datetime,
        sources: dict[str, tuple[UUID, UUID]],
        shard_id: UUID | None = None,
        finish_only: bool = False,
    ) -> tuple[int, int, bool, int, int]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                jobs = PostgresJobRepository(session)
                jobs.lock_current_execution(fence)
                shards = PostgresReversalShardRepository(session)
                shard = shards.assert_owner(shard_id, fence) if shard_id is not None else None
                if shard is not None and shard["import_campaign_id"] != campaign_id:
                    raise LeaseLostError("普通导入撤销工作单元父请求不匹配")
                request_query = select(historical_import_revocation_requests_table).where(
                    historical_import_revocation_requests_table.c.campaign_id == campaign_id
                )
                if shard is None:
                    request_query = request_query.with_for_update()
                request = session.execute(request_query).mappings().one_or_none()
                if request is None or (shard is None and request["job_id"] != fence.job_id):
                    raise LeaseLostError("数据导入撤销请求不属于当前 Job")
                if request["status"] == "succeeded":
                    return 0, int(request["recomputed_content_count"]), True, 0, 0
                if request["status"] not in {"queued", "running"}:
                    raise LeaseLostError("数据导入撤销请求已结束")
                lifecycle = PostgresImportRevocationLifecycleRepository(session)
                read_started = perf_counter()
                contributions, last_content_id = (
                    ((), None)
                    if finish_only
                    else lifecycle.next_campaign_contribution_batch(
                        campaign_id,
                        after_content_id=cast(
                            UUID | None,
                            shard["checkpoint_content_id"]
                            if shard is not None
                            else request["checkpoint_content_id"],
                        ),
                        content_limit=limit,
                        lower_content_id=cast(UUID, shard["lower_content_id"])
                        if shard is not None
                        else None,
                        upper_content_id=cast(UUID | None, shard["upper_content_id"])
                        if shard is not None
                        else None,
                    )
                )
                read_ms = int((perf_counter() - read_started) * 1000)
                if not contributions:
                    if shard is not None:
                        shards.advance(
                            cast(UUID, shard_id), checkpoint=None, processed=0, finished=True
                        )
                        jobs.lock_current_execution(fence)
                        return 0, int(request["recomputed_content_count"]), True, read_ms, 0
                    now = beijing_now()
                    session.execute(
                        update(historical_import_revocation_requests_table)
                        .where(
                            historical_import_revocation_requests_table.c.campaign_id == campaign_id
                        )
                        .values(status="succeeded", completed_at=now)
                    )
                    session.execute(
                        update(historical_import_campaigns_table)
                        .where(
                            historical_import_campaigns_table.c.id == campaign_id,
                            historical_import_campaigns_table.c.status == "revoking",
                        )
                        .values(status="revoked")
                    )
                    fact = (
                        session.execute(
                            select(historical_import_campaign_revocations_table).where(
                                historical_import_campaign_revocations_table.c.campaign_id
                                == campaign_id
                            )
                        )
                        .mappings()
                        .one()
                    )
                    PostgresAuditRepository(session).append(
                        AuditEvent(
                            id=uuid4(),
                            actor_kind="principal",
                            actor_ref=cast(str, fact["actor_ref"]),
                            event_type="data_import_campaign_revoked",
                            object_type="data_import_campaign",
                            object_id=str(campaign_id),
                            request_id=cast(str | None, fact["request_id"]),
                            safe_detail={
                                "affected_content_count": fact["affected_content_count"],
                                "hidden_content_count": fact["hidden_content_count"],
                                "retained_shared_content_count": fact[
                                    "retained_shared_content_count"
                                ],
                                "recomputed_content_count": request["recomputed_content_count"],
                            },
                            created_at=now,
                        )
                    )
                    jobs.lock_current_execution(fence)
                    return 0, int(request["recomputed_content_count"]), True, read_ms, 0
                if last_content_id is None:
                    raise ValueError("撤销批次缺少断点")
                apply_started = perf_counter()
                processed = lifecycle.apply_campaign_contribution_batch(
                    campaign_id,
                    contributions=contributions,
                    revoked_at=revoked_at,
                    lifecycle_sources=sources,
                )
                apply_ms = int((perf_counter() - apply_started) * 1000)
                total = int(request["recomputed_content_count"]) + processed
                if shard is not None:
                    shards.advance(
                        cast(UUID, shard_id),
                        checkpoint=last_content_id,
                        processed=processed,
                        finished=False,
                    )
                    updated_request = cast(
                        CursorResult[object],
                        session.execute(
                            update(historical_import_revocation_requests_table)
                            .where(
                                historical_import_revocation_requests_table.c.campaign_id
                                == campaign_id,
                                historical_import_revocation_requests_table.c.status.in_(
                                    ("queued", "running")
                                ),
                            )
                            .values(
                                status="running",
                                recomputed_content_count=(
                                    historical_import_revocation_requests_table.c.recomputed_content_count
                                    + processed
                                ),
                            )
                        ),
                    )
                    if updated_request.rowcount != 1:
                        raise LeaseLostError("普通导入撤销父请求状态已改变")
                else:
                    session.execute(
                        update(historical_import_revocation_requests_table)
                        .where(
                            historical_import_revocation_requests_table.c.campaign_id == campaign_id
                        )
                        .values(
                            status="running",
                            checkpoint_content_id=last_content_id,
                            recomputed_content_count=total,
                        )
                    )
                jobs.lock_current_execution(fence)
                return processed, total, False, read_ms, apply_ms
        finally:
            session.close()


def data_import_revocation_terminal_callback(session: Session, job: JobRecord) -> None:
    """非成功终态保留已提交断点，并把失败暴露给查询和重试入口。"""

    if job.status == "succeeded":
        return
    campaign_id = job.payload.get("campaign_id")
    if campaign_id is not None:
        shards = PostgresReversalShardRepository(session).list("import", UUID(str(campaign_id)))
        jobs = PostgresJobRepository(session)
        for shard in shards:
            child_id = cast(UUID | None, shard["job_id"])
            if (
                child_id is not None
                and child_id != job.id
                and shard["status"] in {"queued", "running"}
            ):
                jobs.request_cancel(child_id)
        session.execute(
            update(historical_import_revocation_requests_table)
            .where(
                historical_import_revocation_requests_table.c.campaign_id == UUID(str(campaign_id)),
                historical_import_revocation_requests_table.c.job_id == job.id,
                historical_import_revocation_requests_table.c.status != "succeeded",
            )
            .values(status="failed", error_code=job.error_code)
        )


__all__ = [
    "PostgresImportRevocationJobExecutor",
    "data_import_revocation_terminal_callback",
]
