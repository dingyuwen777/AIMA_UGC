"""后台写槽在前台导入压力下的 PostgreSQL 集成回归。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.workload_slots import (
    acquire_background_write_slot,
    acquire_foreground_write_priority,
)
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_IMPORT_CHUNK_JOB_TYPE
from aima_ugc.platform.capacity import ResourceSnapshot
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import func, select


def test_background_write_slots_contract_when_foreground_import_is_ready() -> None:
    runtime = DatabaseRuntime(load_settings())
    resources = ResourceSnapshot(
        cpu_cores=12.0,
        memory_limit_bytes=12 * 1024**3,
        memory_available_bytes=11 * 1024**3,
        source="cgroup_v2",
    )
    try:
        without_pressure = runtime.new_session()
        try:
            with without_pressure.begin():
                selected = acquire_background_write_slot(
                    without_pressure,
                    resources=resources,
                    work_id=uuid4(),
                )
                assert selected.foreground_pressure is False
                assert selected.slot_count == 6
        finally:
            without_pressure.close()

        with_pressure = runtime.new_session()
        try:
            transaction = with_pressure.begin()
            PostgresJobRepository(with_pressure).enqueue(
                job_type=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                payload_version=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                payload={"schema_version": HISTORICAL_IMPORT_CHUNK_JOB_TYPE},
                internal_idempotency_key=f"workload-slot-test:{uuid4()}",
                request_id="workload-slot-test",
                priority=0,
                max_attempts=1,
                timeout_seconds=60,
            )
            selected = acquire_background_write_slot(
                with_pressure,
                resources=resources,
                work_id=uuid4(),
            )
            assert selected.foreground_pressure is True
            assert selected.slot_count == 1
            transaction.rollback()
        finally:
            with_pressure.rollback()
            with_pressure.close()
    finally:
        runtime.dispose()


def test_foreground_priority_allows_other_foreground_and_blocks_background() -> None:
    runtime = DatabaseRuntime(load_settings())
    resources = ResourceSnapshot(
        cpu_cores=12.0,
        memory_limit_bytes=12 * 1024**3,
        memory_available_bytes=11 * 1024**3,
        source="cgroup_v2",
    )
    first = runtime.new_session()
    second = runtime.new_session()
    probe = runtime.new_session()
    try:
        first.begin()
        selected = acquire_foreground_write_priority(first, resources=resources)
        assert selected.slot_count == 6

        second.begin()
        concurrent = acquire_foreground_write_priority(second, resources=resources)
        assert concurrent.slot_count == 6

        probe.begin()
        acquired = probe.scalar(
            select(
                func.pg_try_advisory_xact_lock(
                    func.hashtextextended("aima:background-write-slot:v1:0", 0)
                )
            )
        )
        assert acquired is False
    finally:
        probe.rollback()
        second.rollback()
        first.rollback()
        probe.close()
        second.close()
        first.close()
        runtime.dispose()
