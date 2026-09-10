"""旧 Content 品牌车型重分类 Run 的 PostgreSQL Owner Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid5

from sqlalchemy import Text, func, insert, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.vehicles.content_reclassification import (
    CONTENT_RECLASSIFICATION_JOB_MAX_ATTEMPTS,
    CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION,
    CONTENT_RECLASSIFICATION_JOB_TIMEOUT_SECONDS,
    CONTENT_RECLASSIFICATION_JOB_TYPE,
    ContentReclassificationCandidate,
    ContentReclassificationRunRecord,
    ReclassificationBatchCounters,
    dump_catalog_snapshot,
    load_catalog_snapshot,
)
from aima_ugc.modules.vehicles.tables import (
    content_reclassification_runs_table,
    content_vehicle_evidence_table,
    content_vehicle_review_locks_table,
    vehicle_models_table,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobRecord
from aima_ugc.platform.time import beijing_now

_RUN_NAMESPACE = UUID("696d8f6c-d184-4aae-93ed-81ce6f1d3f8b")


class PostgresContentReclassificationRepository:
    """持久化冻结范围、Keyset 检查点、对账统计与对应 Job。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方持有的事务 Session。"""

        self._session = session

    def enqueue(
        self,
        *,
        idempotency_key: str,
        shard_index: int,
        shard_count: int,
        start_after_content_id: UUID | None,
        end_at_content_id: UUID | None,
        batch_size: int,
        max_contents: int,
        created_by: str,
        request_id: str | None,
    ) -> tuple[ContentReclassificationRunRecord, JobRecord]:
        """冻结全量 active 目录并与幂等 Job 在同一事务创建 Run。"""

        key = idempotency_key.strip()
        if not key or len(key) > 200:
            raise ValueError("idempotency_key 必须是 1—200 字符")
        actor = created_by.strip()
        if not actor or len(actor) > 200:
            raise ValueError("created_by 必须是 1—200 字符")
        if shard_count <= 0 or shard_index < 0 or shard_index >= shard_count:
            raise ValueError("shard_index 必须落在 shard_count 范围内")
        if batch_size <= 0 or batch_size > 1000:
            raise ValueError("batch_size 必须是 1—1000")
        if max_contents <= 0:
            raise ValueError("max_contents 必须大于 0")
        if (
            start_after_content_id is not None
            and end_at_content_id is not None
            and start_after_content_id >= end_at_content_id
        ):
            raise ValueError("start_after_content_id 必须小于 end_at_content_id")

        run_id = uuid5(_RUN_NAMESPACE, key)
        existing = self.get(run_id)
        if existing is not None:
            requested_identity = (
                shard_index,
                shard_count,
                start_after_content_id,
                end_at_content_id,
                batch_size,
                max_contents,
                actor,
            )
            existing_identity = (
                existing.shard_index,
                existing.shard_count,
                existing.start_after_content_id,
                existing.end_at_content_id,
                existing.batch_size,
                existing.max_contents,
                existing.created_by,
            )
            if requested_identity != existing_identity:
                raise RuntimeError("idempotency_key 已绑定不同的重分类范围或参数")
            job = PostgresJobRepository(self._session).get(existing.job_id)
            if job is None:
                raise RuntimeError("重分类 Run 缺少对应 Job")
            return existing, job

        snapshot = PostgresBrandVehicleRepository(self._session).snapshot(brand_ids=None)
        if snapshot.unresolved_active_vehicle_ids:
            raise RuntimeError("存在未完成品牌归属的 active 车型，不能启动重分类")
        job = PostgresJobRepository(self._session).enqueue(
            job_type=CONTENT_RECLASSIFICATION_JOB_TYPE,
            payload_version=CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION,
            payload={
                "schema_version": CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION,
                "run_id": str(run_id),
            },
            internal_idempotency_key=f"content-reclassification:{key}",
            request_id=request_id,
            priority=0,
            max_attempts=CONTENT_RECLASSIFICATION_JOB_MAX_ATTEMPTS,
            timeout_seconds=CONTENT_RECLASSIFICATION_JOB_TIMEOUT_SECONDS,
        )
        now = beijing_now()
        self._session.execute(
            insert(content_reclassification_runs_table).values(
                id=run_id,
                job_id=job.id,
                catalog_snapshot=dump_catalog_snapshot(snapshot),
                shard_index=shard_index,
                shard_count=shard_count,
                start_after_content_id=start_after_content_id,
                end_at_content_id=end_at_content_id,
                checkpoint_content_id=None,
                batch_size=batch_size,
                max_contents=max_contents,
                created_by=actor,
                created_at=now,
                updated_at=now,
            )
        )
        created = self.get(run_id)
        if created is None:
            raise RuntimeError("重分类 Run 创建后不可读")
        return created, job

    def get(
        self,
        run_id: UUID,
        *,
        for_update: bool = False,
    ) -> ContentReclassificationRunRecord | None:
        """读取一个 Run；批次推进时可显式加行锁。"""

        statement = select(content_reclassification_runs_table).where(
            content_reclassification_runs_table.c.id == run_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _run_from_row(row)

    def get_job(self, run_id: UUID) -> JobRecord | None:
        """读取 Run 对应 Job 状态。"""

        run = self.get(run_id)
        return None if run is None else PostgresJobRepository(self._session).get(run.job_id)

    def request_cancel(self, run_id: UUID) -> JobRecord:
        """通过 Platform Job Runtime 请求取消，保留统一竞态语义。"""

        run = self.get(run_id)
        if run is None:
            raise LookupError(run_id)
        return PostgresJobRepository(self._session).request_cancel(run.job_id)

    def load_next_batch(
        self,
        run: ContentReclassificationRunRecord,
    ) -> tuple[ContentReclassificationCandidate, ...]:
        """按 UUID Keyset 与稳定 Hash Shard 读取一个有界 Current Content 批次。"""

        remaining = run.max_contents - run.processed_count
        if remaining <= 0:
            return ()
        cursor = run.checkpoint_content_id or run.start_after_content_id
        conditions = []
        if cursor is not None:
            conditions.append(contents_table.c.id > cursor)
        if run.end_at_content_id is not None:
            conditions.append(contents_table.c.id <= run.end_at_content_id)
        shard_hash = func.hashtextextended(sql_cast(contents_table.c.id, Text), 0)
        shard = func.mod(func.mod(shard_hash, run.shard_count) + run.shard_count, run.shard_count)
        conditions.append(shard == run.shard_index)
        rows = tuple(
            self._session.execute(
                select(
                    contents_table.c.id,
                    contents_table.c.current_version,
                    contents_table.c.title,
                    contents_table.c.text,
                )
                .where(*conditions)
                .order_by(contents_table.c.id)
                .limit(min(run.batch_size, remaining))
            ).mappings()
        )
        if not rows:
            return ()

        content_ids = tuple(cast(UUID, row["id"]) for row in rows)
        versions = {cast(UUID, row["id"]): cast(int, row["current_version"]) for row in rows}
        evidence_rows = self._session.execute(
            select(
                content_vehicle_evidence_table.c.content_id,
                content_vehicle_evidence_table.c.content_version,
                func.coalesce(
                    vehicle_models_table.c.merged_into_id,
                    content_vehicle_evidence_table.c.vehicle_model_id,
                ).label("effective_vehicle_model_id"),
                content_vehicle_evidence_table.c.source,
            )
            .join(
                vehicle_models_table,
                vehicle_models_table.c.id == content_vehicle_evidence_table.c.vehicle_model_id,
            )
            .where(
                content_vehicle_evidence_table.c.content_id.in_(content_ids),
                content_vehicle_evidence_table.c.is_active.is_(True),
                # alias_match 会由本次冻结目录重新计算，不能反向把旧目录命中
                # 当作第一层既有车型事实继续传播。
                content_vehicle_evidence_table.c.source != "alias_match",
            )
        )
        existing: dict[UUID, set[UUID]] = {item: set() for item in content_ids}
        manual: dict[UUID, set[UUID]] = {item: set() for item in content_ids}
        for row in evidence_rows:
            content_id = cast(UUID, row.content_id)
            if cast(int, row.content_version) != versions.get(content_id):
                continue
            vehicle_id = cast(UUID, row.effective_vehicle_model_id)
            existing[content_id].add(vehicle_id)
            if cast(str, row.source) == "manual_review":
                manual[content_id].add(vehicle_id)
        locked_pairs = set(
            self._session.execute(
                select(
                    content_vehicle_review_locks_table.c.content_id,
                    content_vehicle_review_locks_table.c.content_version,
                ).where(
                    content_vehicle_review_locks_table.c.content_id.in_(content_ids),
                    content_vehicle_review_locks_table.c.is_locked.is_(True),
                )
            )
        )
        return tuple(
            ContentReclassificationCandidate(
                content_id=cast(UUID, row["id"]),
                content_version=cast(int, row["current_version"]),
                title=cast(str | None, row["title"]),
                text=cast(str | None, row["text"]),
                existing_vehicle_ids=tuple(sorted(existing[cast(UUID, row["id"])], key=str)),
                manual_vehicle_ids=(
                    tuple(sorted(manual[cast(UUID, row["id"])], key=str))
                    if (row["id"], row["current_version"]) in locked_pairs
                    else None
                ),
            )
            for row in rows
        )

    def advance(
        self,
        *,
        run_id: UUID,
        checkpoint_content_id: UUID,
        counters: ReclassificationBatchCounters,
        fence: JobExecutionFence,
    ) -> ContentReclassificationRunRecord:
        """验证当前 Fence 后原子提交检查点和对账增量。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        row = (
            self._session.execute(
                update(content_reclassification_runs_table)
                .where(content_reclassification_runs_table.c.id == run_id)
                .values(
                    checkpoint_content_id=checkpoint_content_id,
                    processed_count=(
                        content_reclassification_runs_table.c.processed_count
                        + counters.processed_count
                    ),
                    matched_count=(
                        content_reclassification_runs_table.c.matched_count + counters.matched_count
                    ),
                    unmatched_count=(
                        content_reclassification_runs_table.c.unmatched_count
                        + counters.unmatched_count
                    ),
                    brand_evidence_count=(
                        content_reclassification_runs_table.c.brand_evidence_count
                        + counters.brand_evidence_count
                    ),
                    vehicle_evidence_count=(
                        content_reclassification_runs_table.c.vehicle_evidence_count
                        + counters.vehicle_evidence_count
                    ),
                    conflict_count=(
                        content_reclassification_runs_table.c.conflict_count
                        + counters.conflict_count
                    ),
                    brand_locked_count=(
                        content_reclassification_runs_table.c.brand_locked_count
                        + counters.brand_locked_count
                    ),
                    vehicle_locked_count=(
                        content_reclassification_runs_table.c.vehicle_locked_count
                        + counters.vehicle_locked_count
                    ),
                    updated_at=beijing_now(),
                )
                .returning(content_reclassification_runs_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError(run_id)
        return _run_from_row(row)


def _run_from_row(row: RowMapping) -> ContentReclassificationRunRecord:
    """把 SQLAlchemy RowMapping 转成不可变领域记录。"""

    return ContentReclassificationRunRecord(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        catalog_snapshot=load_catalog_snapshot(row["catalog_snapshot"]),
        shard_index=cast(int, row["shard_index"]),
        shard_count=cast(int, row["shard_count"]),
        start_after_content_id=cast(UUID | None, row["start_after_content_id"]),
        end_at_content_id=cast(UUID | None, row["end_at_content_id"]),
        checkpoint_content_id=cast(UUID | None, row["checkpoint_content_id"]),
        batch_size=cast(int, row["batch_size"]),
        max_contents=cast(int, row["max_contents"]),
        processed_count=cast(int, row["processed_count"]),
        matched_count=cast(int, row["matched_count"]),
        unmatched_count=cast(int, row["unmatched_count"]),
        brand_evidence_count=cast(int, row["brand_evidence_count"]),
        vehicle_evidence_count=cast(int, row["vehicle_evidence_count"]),
        conflict_count=cast(int, row["conflict_count"]),
        brand_locked_count=cast(int, row["brand_locked_count"]),
        vehicle_locked_count=cast(int, row["vehicle_locked_count"]),
        created_by=cast(str, row["created_by"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


__all__ = ["PostgresContentReclassificationRepository"]
