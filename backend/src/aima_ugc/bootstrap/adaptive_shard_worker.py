"""入库与撤回共用的持久分片调度、资源反馈与完成屏障。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from time import perf_counter
from typing import Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.replay_shards import PostgresReplayShardRepository
from aima_ugc.adapters.persistence.postgres.reversal_shards import (
    PostgresReversalShardRepository,
    ReversalKind,
)
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceConflictError
from aima_ugc.modules.ingestion.replay_shard_tables import canonical_replay_run_shards_table
from aima_ugc.modules.ingestion.replay_shards import REPLAY_SHARD_JOB_TYPE
from aima_ugc.modules.ingestion.reversal_shard_tables import reversal_shards_table
from aima_ugc.modules.ingestion.reversal_shards import REVERSAL_SHARD_JOB_TYPE
from aima_ugc.platform.capacity import (
    AdaptiveJobWindowController,
    detect_resources,
    worker_process_limit,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.storage import CanonicalArtifactIntegrityError

from .runtime import PlatformRuntime

ShardKind = Literal["import", "replay", "replay_run"]


class _ShardProcessor(Protocol):
    def process_shard(
        self,
        shard_id: UUID,
        *,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> int: ...


class AdaptiveShardCoordinator:
    """各业务表保留独立断点，父子 Job 共用调度、反馈与完成屏障。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        import_processor: _ShardProcessor,
        replay_processor: _ShardProcessor,
        replay_run_processor: _ShardProcessor,
    ) -> None:
        self._runtime = runtime
        self._processors = {
            "import": import_processor,
            "replay": replay_processor,
            "replay_run": replay_run_processor,
        }

    def execute_parent(
        self,
        *,
        kind: ShardKind,
        parent_id: UUID,
        remaining_contents: int,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
        finish: Callable[[], JobHandlerResult],
    ) -> JobHandlerResult:
        self._create(kind, parent_id, remaining_contents, fence)
        tuner = AdaptiveJobWindowController(initial_window=1)
        while True:
            if context.cancel_requested():
                self._cancel_children(kind, parent_id, parent_fence=fence)
                return JobHandlerResult.cancelled()
            units = self._units(kind, parent_id)
            if any(unit["status"] == "failed" for unit in units):
                self._cancel_children(kind, parent_id, parent_fence=fence)
                return JobHandlerResult.failed("adaptive_shard_failed")
            owned = next(
                (
                    unit
                    for unit in units
                    if unit["status"] == "running" and unit["job_id"] == fence.job_id
                ),
                None,
            )
            if owned is not None:
                self._processors[kind].process_shard(
                    cast(UUID, owned["id"]), fence=fence, context=context
                )
                continue
            active = [unit for unit in units if unit["status"] in {"queued", "running"}]
            pending = [unit for unit in units if unit["status"] == "pending"]
            if not pending:
                if all(unit["status"] == "succeeded" for unit in units):
                    child_statuses = self._child_job_statuses(units, parent_job_id=fence.job_id)
                    if any(
                        job_status in {"failed", "cancelled"} and unit_status != "succeeded"
                        for unit_status, job_status in child_statuses
                    ):
                        return JobHandlerResult.failed("adaptive_shard_failed")
                    if any(
                        job_status not in {"succeeded", "failed", "cancelled"}
                        for _, job_status in child_statuses
                    ):
                        context.heartbeat(progress=99)
                        time.sleep(0.2)
                        continue
                    completed_with_failed_job = sum(
                        job_status in {"failed", "cancelled"} for _, job_status in child_statuses
                    )
                    if completed_with_failed_job:
                        log_event(
                            self._runtime.logger,
                            logging.WARNING,
                            "capacity.adaptive_child_failed_after_commit",
                            "子 Job 终态失败，但业务分片已原子结清",
                            kind=kind,
                            parent_id=str(parent_id),
                            child_job_count=completed_with_failed_job,
                        )
                    return finish()
                raise RuntimeError("撤回分片完成屏障发现非预期状态")
            resources = detect_resources()
            headroom = self._database_headroom()
            window, reason, previous = tuner.choose(
                resources,
                remaining_units=len(pending) + len(active),
                database_headroom=headroom,
            )
            available_slots = max(0, window - len(active))
            if available_slots == 0:
                context.heartbeat(progress=self._progress(units))
                time.sleep(0.2)
                continue
            if previous != window:
                log_event(
                    self._runtime.logger,
                    logging.INFO,
                    "capacity.adaptive_job_window_selected",
                    "持久 Job 并发窗口调整",
                    kind=kind,
                    parent_id=str(parent_id),
                    previous_jobs=previous,
                    selected_jobs=window,
                    reason=reason,
                    cpu_cores=resources.cpu_cores,
                    memory_available_mib=(
                        resources.memory_available_bytes // (1024 * 1024)
                        if resources.memory_available_bytes is not None
                        else None
                    ),
                    database_headroom=headroom,
                    remaining_units=len(pending) + len(active),
                )
            before = sum(self._processed(unit, kind) for unit in units)
            wave_started = perf_counter()
            owned_id, _ = self._assign(kind, parent_id, fence, available_slots)
            if owned_id is not None:
                self._processors[kind].process_shard(owned_id, fence=fence, context=context)
            while True:
                if context.cancel_requested():
                    self._cancel_children(kind, parent_id, parent_fence=fence)
                    return JobHandlerResult.cancelled()
                current = self._units(kind, parent_id)
                if any(unit["status"] == "failed" for unit in current):
                    self._cancel_children(kind, parent_id, parent_fence=fence)
                    return JobHandlerResult.failed("adaptive_shard_failed")
                active_count = sum(unit["status"] in {"queued", "running"} for unit in current)
                pending_count = sum(unit["status"] == "pending" for unit in current)
                child_statuses = self._child_job_statuses(current, parent_job_id=fence.job_id)
                if any(
                    (job_status in {"failed", "cancelled"} and unit_status != "succeeded")
                    or (job_status == "succeeded" and unit_status != "succeeded")
                    for unit_status, job_status in child_statuses
                ):
                    self._cancel_children(kind, parent_id, parent_fence=fence)
                    return JobHandlerResult.failed("adaptive_shard_failed")
                if not active_count and all(
                    job_status in {"succeeded", "failed", "cancelled"}
                    for _, job_status in child_statuses
                ):
                    break
                if pending_count and active_count < window:
                    break
                context.heartbeat(progress=self._progress(current))
                time.sleep(0.2)
            done = sum(self._processed(unit, kind) for unit in current) - before
            duration_ms = max(1, int((perf_counter() - wave_started) * 1000))
            tuner.succeeded(window=window, contents=done, duration_ms=duration_ms)
            log_event(
                self._runtime.logger,
                logging.INFO,
                "capacity.adaptive_job_segment_completed",
                "持久分片调度区间完成",
                kind=kind,
                parent_id=str(parent_id),
                job_window=window,
                work_count=done,
                work_unit="row" if kind == "replay_run" else "content",
                duration_ms=duration_ms,
                work_per_second=round(done * 1000 / duration_ms, 1),
            )
            context.heartbeat(progress=self._progress(current))

    def execute_child(
        self,
        *,
        shard_id: UUID,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        session = self._runtime.database.new_session()
        try:
            unit = PostgresReversalShardRepository(session).get(shard_id)
            kind: ShardKind
            if unit is None:
                unit = PostgresReplayShardRepository(session).get(shard_id)
                if unit is None:
                    return JobHandlerResult.failed("adaptive_shard_not_found")
                kind = "replay_run"
            else:
                kind = cast(ReversalKind, unit["kind"])
            if unit["job_id"] != fence.job_id:
                raise LeaseLostError("撤回分片已不属于当前子 Job")
            if unit["status"] == "succeeded":
                return JobHandlerResult.succeeded(
                    {
                        "shard_id": str(shard_id),
                        "processed_count": self._processed(unit, kind),
                    }
                )
        finally:
            session.close()
        try:
            processed = self._processors[kind].process_shard(shard_id, fence=fence, context=context)
            return JobHandlerResult.succeeded(
                {"shard_id": str(shard_id), "processed_count": processed}
            )
        except LeaseLostError:
            raise
        except (
            CanonicalArtifactIntegrityError,
            LookupError,
            ValueError,
            DataError,
            IntegrityError,
            ProgrammingError,
        ):
            self._runtime.logger.exception("持久分片 Job 输入或数据错误：shard_id=%s", shard_id)
            return JobHandlerResult.failed("adaptive_shard_invalid")
        except OSError, SQLAlchemyError, ProviderPersistenceConflictError:
            self._runtime.logger.exception("持久分片 Job 暂时失败：shard_id=%s", shard_id)
            return JobHandlerResult.retry("adaptive_shard_transient_error")
        except Exception:
            self._runtime.logger.exception("持久分片 Job 未预期失败：shard_id=%s", shard_id)
            return JobHandlerResult.retry("adaptive_shard_unexpected_error")

    def _create(
        self, kind: ShardKind, parent_id: UUID, remaining_contents: int, fence: JobExecutionFence
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                if kind == "replay_run":
                    PostgresReplayShardRepository(session).create_if_absent(
                        run_id=parent_id, shard_count=remaining_contents, fence=fence
                    )
                else:
                    PostgresReversalShardRepository(session).create_if_absent(
                        kind=kind,
                        parent_id=parent_id,
                        remaining_contents=remaining_contents,
                        max_shards=worker_process_limit(detect_resources()) * 16,
                        fence=fence,
                    )
        finally:
            session.close()

    def _assign(
        self, kind: ShardKind, parent_id: UUID, fence: JobExecutionFence, window: int
    ) -> tuple[UUID | None, tuple[UUID, ...]]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                if kind == "replay_run":
                    owned = PostgresReplayShardRepository(session).assign_wave(
                        run_id=parent_id, parent_fence=fence, window=window
                    )
                    return owned, ()
                return PostgresReversalShardRepository(session).assign_wave(
                    kind=kind, parent_id=parent_id, parent_fence=fence, window=window
                )
        finally:
            session.close()

    def _units(self, kind: ShardKind, parent_id: UUID) -> tuple[RowMapping, ...]:
        session = self._runtime.database.new_session()
        try:
            if kind == "replay_run":
                return PostgresReplayShardRepository(session).list(parent_id)
            return PostgresReversalShardRepository(session).list(kind, parent_id)
        finally:
            session.close()

    def _database_headroom(self) -> int:
        session = self._runtime.database.new_session()
        try:
            maximum = int(session.execute(text("SHOW max_connections")).scalar_one())
            used = int(session.execute(text("SELECT count(*) FROM pg_stat_activity")).scalar_one())
            return max(1, maximum - used - max(10, maximum // 5))
        finally:
            session.close()

    def _child_job_statuses(
        self, units: tuple[RowMapping, ...], *, parent_job_id: UUID
    ) -> tuple[tuple[str, str], ...]:
        child_units = {
            cast(UUID, unit["job_id"]): cast(str, unit["status"])
            for unit in units
            if unit["job_id"] is not None and unit["job_id"] != parent_job_id
        }
        if not child_units:
            return ()
        session = self._runtime.database.new_session()
        try:
            return tuple(
                (child_units[cast(UUID, job_id)], cast(str, status))
                for job_id, status in session.execute(
                    select(jobs_table.c.id, jobs_table.c.status).where(
                        jobs_table.c.id.in_(tuple(child_units)),
                        jobs_table.c.job_type.in_((REVERSAL_SHARD_JOB_TYPE, REPLAY_SHARD_JOB_TYPE)),
                    )
                )
            )
        finally:
            session.close()

    def _cancel_children(
        self, kind: ShardKind, parent_id: UUID, *, parent_fence: JobExecutionFence
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                jobs = PostgresJobRepository(session)
                units = (
                    PostgresReplayShardRepository(session).list(parent_id)
                    if kind == "replay_run"
                    else PostgresReversalShardRepository(session).list(kind, parent_id)
                )
                for unit in units:
                    job_id = cast(UUID | None, unit["job_id"])
                    if (
                        job_id is not None
                        and job_id != parent_fence.job_id
                        and unit["status"] in {"queued", "running"}
                    ):
                        jobs.request_cancel(job_id)
        finally:
            session.close()

    @staticmethod
    def _processed(unit: RowMapping, kind: ShardKind) -> int:
        return int(unit["rows_seen"] if kind == "replay_run" else unit["processed_content_count"])

    @staticmethod
    def _progress(units: tuple[RowMapping, ...]) -> int:
        if not units:
            return 99
        completed = sum(unit["status"] == "succeeded" for unit in units)
        return min(99, int(completed * 100 // len(units)))


def reversal_shard_terminal_callback(session: Session, job: JobRecord) -> None:
    """子 Job 的非成功终态必须进入父完成屏障，不能被误当作空任务。"""

    if job.status == "succeeded":
        return
    shard_id = job.payload.get("shard_id")
    if shard_id is not None:
        session.execute(
            update(reversal_shards_table)
            .where(
                reversal_shards_table.c.id == UUID(str(shard_id)),
                reversal_shards_table.c.job_id == job.id,
                reversal_shards_table.c.status != "succeeded",
            )
            .values(status="failed")
        )


def replay_shard_terminal_callback(session: Session, job: JobRecord) -> None:
    if job.status == "succeeded":
        return
    shard_id = job.payload.get("shard_id")
    if shard_id is not None:
        session.execute(
            update(canonical_replay_run_shards_table)
            .where(
                canonical_replay_run_shards_table.c.id == UUID(str(shard_id)),
                canonical_replay_run_shards_table.c.job_id == job.id,
                canonical_replay_run_shards_table.c.status != "succeeded",
            )
            .values(status="failed")
        )


__all__ = [
    "AdaptiveShardCoordinator",
    "reversal_shard_terminal_callback",
    "replay_shard_terminal_callback",
]
