"""两种撤回共用的持久 Content 工作单元调度数据入口。"""

from __future__ import annotations

from math import ceil
from typing import Literal, cast
from uuid import UUID, uuid5

from sqlalchemy import ColumnElement, func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.ingestion.canonical_replay_tables import canonical_replay_all_requests_table
from aima_ugc.modules.ingestion.reversal_shard_tables import reversal_shards_table
from aima_ugc.modules.ingestion.reversal_shards import (
    IMPORT_REVERSAL_SHARD_PRIORITY,
    REPLAY_REVERSAL_SHARD_PRIORITY,
    REVERSAL_SHARD_JOB_TYPE,
    REVERSAL_TARGET_CONTENTS_PER_SHARD,
)
from aima_ugc.modules.ingestion.revocation_tables import historical_import_revocation_requests_table
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.models import LeaseLostError
from aima_ugc.platform.time import beijing_now

ReversalKind = Literal["import", "replay"]
_UUID_SPACE = 1 << 128


def select_reversal_shard_count(remaining_contents: int, *, max_shards: int) -> int:
    """按工作量提供足够试档机会，同时避免超大请求创建无界 Job。"""

    if remaining_contents < 0 or max_shards < 1:
        raise ValueError("撤回工作量或分片资源上界无效")
    return min(ceil(remaining_contents / REVERSAL_TARGET_CONTENTS_PER_SHARD), max_shards)


class PostgresReversalShardRepository:
    """在 Job Fence 下创建、调度和结清互不重叠的 Content 范围。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def parent_column(kind: ReversalKind) -> ColumnElement[UUID | None]:
        return (
            reversal_shards_table.c.import_campaign_id
            if kind == "import"
            else reversal_shards_table.c.replay_request_id
        )

    def list(self, kind: ReversalKind, parent_id: UUID) -> tuple[RowMapping, ...]:
        return tuple(
            self._session.execute(
                select(reversal_shards_table)
                .where(self.parent_column(kind) == parent_id)
                .order_by(reversal_shards_table.c.ordinal)
            ).mappings()
        )

    def get(self, shard_id: UUID, *, for_update: bool = False) -> RowMapping | None:
        query = select(reversal_shards_table).where(reversal_shards_table.c.id == shard_id)
        if for_update:
            query = query.with_for_update()
        return self._session.execute(query).mappings().one_or_none()

    def create_if_absent(
        self,
        *,
        kind: ReversalKind,
        parent_id: UUID,
        remaining_contents: int,
        max_shards: int,
        fence: JobExecutionFence,
    ) -> tuple[RowMapping, ...]:
        """一个父 Job 一次性冻结范围；已有分片在 Lease 接管后原样继续。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        parent_job_id = self._session.scalar(
            select(
                historical_import_revocation_requests_table.c.job_id
                if kind == "import"
                else canonical_replay_all_requests_table.c.reversal_job_id
            ).where(
                historical_import_revocation_requests_table.c.campaign_id == parent_id
                if kind == "import"
                else canonical_replay_all_requests_table.c.id == parent_id
            )
        )
        if parent_job_id != fence.job_id:
            raise LeaseLostError("撤回父请求已交给另一 Job")
        existing = self.list(kind, parent_id)
        if existing:
            # 父 Job 终态失败后可创建新 Job 重试；旧子 Job 被取消/失去 Fence，
            # 新 Job 从各片已提交 checkpoint 接管，不重做已结清 Content。
            self._session.execute(
                update(reversal_shards_table)
                .where(
                    self.parent_column(kind) == parent_id,
                    reversal_shards_table.c.status != "succeeded",
                    reversal_shards_table.c.job_id.is_distinct_from(fence.job_id),
                )
                .values(status="pending", job_id=None)
            )
            return self.list(kind, parent_id)
        if remaining_contents < 1:
            return ()
        # 超大请求不能按每 2500 条无限建 Job；按有效 Worker 预算保留多轮试档。
        count = select_reversal_shard_count(remaining_contents, max_shards=max_shards)
        rows: list[dict[str, object]] = []
        for ordinal in range(count):
            lower = UUID(int=(_UUID_SPACE * ordinal) // count)
            upper = (
                UUID(int=(_UUID_SPACE * (ordinal + 1)) // count) if ordinal + 1 < count else None
            )
            rows.append(
                {
                    "id": uuid5(parent_id, f"{kind}-reversal-shard:{ordinal}"),
                    "kind": kind,
                    "import_campaign_id": parent_id if kind == "import" else None,
                    "replay_request_id": parent_id if kind == "replay" else None,
                    "ordinal": ordinal,
                    "lower_content_id": lower,
                    "upper_content_id": upper,
                    "status": "pending",
                }
            )
        self._session.execute(insert(reversal_shards_table), rows)
        return self.list(kind, parent_id)

    def assign_wave(
        self,
        *,
        kind: ReversalKind,
        parent_id: UUID,
        parent_fence: JobExecutionFence,
        window: int,
    ) -> tuple[UUID | None, tuple[UUID, ...]]:
        """父 Job 认领一片，其余交给通用 jobs；Job 和业务身份同事务提交。"""

        jobs = PostgresJobRepository(self._session)
        jobs.lock_current_execution(parent_fence)
        pending = (
            self._session.execute(
                select(reversal_shards_table.c.id)
                .where(
                    self.parent_column(kind) == parent_id,
                    reversal_shards_table.c.status == "pending",
                )
                .order_by(reversal_shards_table.c.ordinal)
                .limit(window)
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )
        if not pending:
            return None, ()
        owned = cast(UUID, pending[0])
        self._session.execute(
            update(reversal_shards_table)
            .where(reversal_shards_table.c.id == owned)
            .values(job_id=parent_fence.job_id, status="running")
        )
        children: list[UUID] = []
        for shard_id in pending[1:]:
            job = jobs.enqueue(
                job_type=REVERSAL_SHARD_JOB_TYPE,
                payload_version=REVERSAL_SHARD_JOB_TYPE,
                payload={"shard_id": str(shard_id)},
                internal_idempotency_key=f"reversal-shard:{parent_fence.job_id}:{shard_id}",
                request_id=None,
                priority=(
                    REPLAY_REVERSAL_SHARD_PRIORITY
                    if kind == "replay"
                    else IMPORT_REVERSAL_SHARD_PRIORITY
                ),
                max_attempts=10,
                timeout_seconds=86_400,
            )
            self._session.execute(
                update(reversal_shards_table)
                .where(reversal_shards_table.c.id == shard_id)
                .values(job_id=job.id, status="queued")
            )
            children.append(job.id)
        return owned, tuple(children)

    def assert_owner(self, shard_id: UUID, fence: JobExecutionFence) -> RowMapping:
        PostgresJobRepository(self._session).lock_current_execution(fence)
        row = self.get(shard_id, for_update=True)
        if (
            row is None
            or row["job_id"] != fence.job_id
            or row["status"] not in {"queued", "running"}
        ):
            raise LeaseLostError("撤回分片已不属于当前 Job")
        return row

    def advance(
        self, shard_id: UUID, *, checkpoint: UUID | None, processed: int, finished: bool
    ) -> None:
        values: dict[str, object] = {
            "status": "succeeded" if finished else "running",
            "processed_content_count": reversal_shards_table.c.processed_content_count + processed,
        }
        if checkpoint is not None:
            values["checkpoint_content_id"] = checkpoint
        if finished:
            values["completed_at"] = beijing_now()
        self._session.execute(
            update(reversal_shards_table)
            .where(reversal_shards_table.c.id == shard_id)
            .values(**values)
        )

    def status_counts(self, kind: ReversalKind, parent_id: UUID) -> dict[str, int]:
        rows = self._session.execute(
            select(reversal_shards_table.c.status, func.count())
            .where(self.parent_column(kind) == parent_id)
            .group_by(reversal_shards_table.c.status)
        ).all()
        return {cast(str, status): int(count) for status, count in rows}


__all__ = [
    "PostgresReversalShardRepository",
    "REVERSAL_SHARD_JOB_TYPE",
    "ReversalKind",
    "select_reversal_shard_count",
]
