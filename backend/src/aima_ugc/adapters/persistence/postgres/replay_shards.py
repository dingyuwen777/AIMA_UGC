"""Replay Run 内的持久身份分片与原 Run 计数原子汇总。"""

from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID, uuid5

from sqlalchemy import insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.ingestion.canonical_replay import (
    CanonicalReplayCounters,
    CanonicalReplayRunRecord,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import canonical_replay_runs_table
from aima_ugc.modules.ingestion.replay_shard_tables import canonical_replay_run_shards_table
from aima_ugc.modules.ingestion.replay_shards import (
    REPLAY_SHARD_JOB_PRIORITY,
    REPLAY_SHARD_JOB_TYPE,
)
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.models import LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now


class PostgresReplayShardRepository:
    """保留原 Run 身份，独立推进每片的输入行断点。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, run_id: UUID) -> tuple[RowMapping, ...]:
        return tuple(
            self._session.execute(
                select(canonical_replay_run_shards_table)
                .where(canonical_replay_run_shards_table.c.run_id == run_id)
                .order_by(canonical_replay_run_shards_table.c.ordinal)
            ).mappings()
        )

    def get(self, shard_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        query = select(canonical_replay_run_shards_table).where(
            canonical_replay_run_shards_table.c.id == shard_id
        )
        if for_update:
            query = query.with_for_update()
        return self._session.execute(query).mappings().one_or_none()

    def create_if_absent(
        self, *, run_id: UUID, shard_count: int, fence: JobExecutionFence
    ) -> tuple[RowMapping, ...]:
        PostgresJobRepository(self._session).lock_current_execution(fence)
        current = self.list(run_id)
        if current:
            return current
        if shard_count < 2:
            raise ValueError("Replay 分片数至少为二")
        self._session.execute(
            insert(canonical_replay_run_shards_table),
            [
                {
                    "id": uuid5(run_id, f"canonical-replay-shard:{ordinal}"),
                    "run_id": run_id,
                    "ordinal": ordinal,
                    "shard_count": shard_count,
                    "status": "pending",
                }
                for ordinal in range(shard_count)
            ],
        )
        return self.list(run_id)

    def assign_wave(
        self, *, run_id: UUID, parent_fence: JobExecutionFence, window: int
    ) -> UUID | None:
        jobs = PostgresJobRepository(self._session)
        jobs.lock_current_execution(parent_fence)
        pending = tuple(
            self._session.scalars(
                select(canonical_replay_run_shards_table.c.id)
                .where(
                    canonical_replay_run_shards_table.c.run_id == run_id,
                    canonical_replay_run_shards_table.c.status == "pending",
                )
                .order_by(canonical_replay_run_shards_table.c.ordinal)
                .limit(window)
                .with_for_update(skip_locked=True)
            )
        )
        if not pending:
            return None
        parent_unit = cast(UUID, pending[0])
        self._session.execute(
            update(canonical_replay_run_shards_table)
            .where(canonical_replay_run_shards_table.c.id == parent_unit)
            .values(status="running", job_id=parent_fence.job_id)
        )
        for shard_id in pending[1:]:
            job = jobs.enqueue(
                job_type=REPLAY_SHARD_JOB_TYPE,
                payload_version=REPLAY_SHARD_JOB_TYPE,
                payload={"shard_id": str(shard_id)},
                internal_idempotency_key=f"canonical-replay-shard:{shard_id}",
                request_id=None,
                priority=REPLAY_SHARD_JOB_PRIORITY,
                max_attempts=10,
                timeout_seconds=86_400,
            )
            self._session.execute(
                update(canonical_replay_run_shards_table)
                .where(canonical_replay_run_shards_table.c.id == shard_id)
                .values(status="queued", job_id=job.id)
            )
        return parent_unit

    def assert_owner(self, shard_id: UUID, fence: JobExecutionFence) -> RowMapping:
        PostgresJobRepository(self._session).validate_current_execution(fence)
        shard = self.get(shard_id, for_update=True)
        if (
            shard is None
            or shard["job_id"] != fence.job_id
            or shard["status"] not in {"queued", "running"}
        ):
            raise LeaseLostError("Replay 分片已不属于当前 Job")
        return shard

    def advance(
        self,
        *,
        shard_id: UUID,
        run_id: UUID,
        expected_artifact_ordinal: int,
        expected_row_number: int,
        next_artifact_ordinal: int,
        next_row_number: int,
        counters: CanonicalReplayCounters,
        fence: JobExecutionFence,
        finished: bool,
    ) -> CanonicalReplayRunRecord:
        """业务写、片断点与父 Run 计数在同一事务提交。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        shard = self.get(shard_id, for_update=True)
        if (
            shard is None
            or shard["run_id"] != run_id
            or shard["job_id"] != fence.job_id
            or shard["checkpoint_artifact_ordinal"] != expected_artifact_ordinal
            or shard["checkpoint_row_number"] != expected_row_number
        ):
            raise LeaseLostError("Replay 分片断点已改变")
        parent = PostgresCanonicalReplayRepository(self._session).get(run_id)
        if parent is None:
            raise LeaseLostError("Replay 父 Run 已不存在")
        parent_job = self._session.execute(
            select(jobs_table.c.status, jobs_table.c.cancel_requested_at)
            .where(jobs_table.c.id == parent.job_id)
            .with_for_update(read=True)
        ).one_or_none()
        if (
            parent_job is None
            or parent_job.status != "running"
            or parent_job.cancel_requested_at is not None
        ):
            raise LeaseLostError("Replay 父 Job 已停止或取消")
        shard_table = canonical_replay_run_shards_table
        row = self._session.execute(
            update(shard_table)
            .where(
                shard_table.c.id == shard_id,
                shard_table.c.checkpoint_artifact_ordinal == expected_artifact_ordinal,
                shard_table.c.checkpoint_row_number == expected_row_number,
            )
            .values(
                checkpoint_artifact_ordinal=next_artifact_ordinal,
                checkpoint_row_number=next_row_number,
                status="succeeded" if finished else "running",
                completed_at=beijing_now() if finished else None,
                rows_seen=shard_table.c.rows_seen + counters.rows_seen,
                rows_matched=shard_table.c.rows_matched + counters.rows_matched,
                rows_filtered_out=shard_table.c.rows_filtered_out + counters.rows_filtered_out,
                duplicates_removed=shard_table.c.duplicates_removed + counters.duplicates_removed,
                rows_ingested=shard_table.c.rows_ingested + counters.rows_ingested,
                existing_convergence=shard_table.c.existing_convergence
                + counters.existing_convergence,
            )
            .returning(shard_table.c.id)
        ).one_or_none()
        if row is None:
            raise LeaseLostError("Replay 分片断点提交失败")
        run_table = canonical_replay_runs_table
        parent_row = self._session.execute(
            update(run_table)
            .where(run_table.c.id == run_id, run_table.c.job_id == parent.job_id)
            .values(
                rows_seen=run_table.c.rows_seen + counters.rows_seen,
                rows_matched=run_table.c.rows_matched + counters.rows_matched,
                rows_filtered_out=run_table.c.rows_filtered_out + counters.rows_filtered_out,
                duplicates_removed=run_table.c.duplicates_removed + counters.duplicates_removed,
                rows_ingested=run_table.c.rows_ingested + counters.rows_ingested,
                existing_convergence=run_table.c.existing_convergence
                + counters.existing_convergence,
                updated_at=beijing_now(),
            )
            .returning(run_table.c.id)
        ).one_or_none()
        if parent_row is None:
            raise LeaseLostError("Replay 父 Run 计数提交失败")
        updated = PostgresCanonicalReplayRepository(self._session).get(run_id)
        if updated is None:
            raise LeaseLostError("Replay 父 Run 丢失")
        return replace(
            updated,
            checkpoint_artifact_ordinal=next_artifact_ordinal,
            checkpoint_row_number=next_row_number,
        )


__all__ = ["PostgresReplayShardRepository"]
