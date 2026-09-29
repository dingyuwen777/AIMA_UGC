"""PostgreSQL 后台写批次并发槽；前台导入存在时自动收窄。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
)
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE
from aima_ugc.platform.capacity import (
    ResourceSnapshot,
    foreground_reserve_processes,
    worker_process_limit,
)
from aima_ugc.platform.jobs.tables import jobs_table

_BACKGROUND_WRITE_SLOT_PREFIX = "aima:background-write-slot:v1:"
_FOREGROUND_WRITE_JOB_TYPES = (
    IMPORT_JOB_TYPE,
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
)


@dataclass(frozen=True, slots=True)
class BackgroundWriteSlot:
    """本事务取得的后台写槽诊断，不包含业务数据。"""

    slot: int
    slot_count: int
    foreground_pressure: bool
    wait_ms: int


@dataclass(frozen=True, slots=True)
class ForegroundWritePriority:
    """前台事务取得的共享优先屏障诊断；多个导入仍可同时持有。"""

    slot_count: int
    wait_ms: int


def _background_slot_count(resources: ResourceSnapshot) -> int:
    maximum = worker_process_limit(resources)
    return max(1, maximum - foreground_reserve_processes(maximum))


def acquire_foreground_write_priority(
    session: Session,
    *,
    resources: ResourceSnapshot,
) -> ForegroundWritePriority:
    """共享锁覆盖全部后台槽；并发导入互不阻塞，后台批次在边界让路。"""

    slot_count = _background_slot_count(resources)
    started = perf_counter()
    for slot in range(slot_count):
        key = f"{_BACKGROUND_WRITE_SLOT_PREFIX}{slot}"
        session.execute(select(func.pg_advisory_xact_lock_shared(func.hashtextextended(key, 0))))
    return ForegroundWritePriority(
        slot_count=slot_count,
        wait_ms=int((perf_counter() - started) * 1000),
    )


def acquire_background_write_slot(
    session: Session,
    *,
    resources: ResourceSnapshot,
    work_id: UUID,
) -> BackgroundWriteSlot:
    """无前台导入时并行写；导入排队或运行时把后台收窄到一个事务。"""

    foreground_pressure = (
        session.scalar(
            select(jobs_table.c.id)
            .where(
                jobs_table.c.job_type.in_(_FOREGROUND_WRITE_JOB_TYPES),
                or_(
                    jobs_table.c.status == "running",
                    (
                        (jobs_table.c.status == "queued")
                        & (jobs_table.c.available_at <= func.clock_timestamp())
                    ),
                ),
            )
            .limit(1)
        )
        is not None
    )
    slot_count = 1 if foreground_pressure else _background_slot_count(resources)
    preferred = work_id.int % slot_count
    started = perf_counter()
    for offset in range(slot_count):
        slot = (preferred + offset) % slot_count
        key = f"{_BACKGROUND_WRITE_SLOT_PREFIX}{slot}"
        acquired = session.scalar(
            select(func.pg_try_advisory_xact_lock(func.hashtextextended(key, 0)))
        )
        if acquired:
            return BackgroundWriteSlot(
                slot=slot,
                slot_count=slot_count,
                foreground_pressure=foreground_pressure,
                wait_ms=int((perf_counter() - started) * 1000),
            )

    key = f"{_BACKGROUND_WRITE_SLOT_PREFIX}{preferred}"
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
    return BackgroundWriteSlot(
        slot=preferred,
        slot_count=slot_count,
        foreground_pressure=foreground_pressure,
        wait_ms=int((perf_counter() - started) * 1000),
    )
