"""Content Owner 的显式历史修复范围、只读预检与原子检查点。"""

from collections import Counter
from dataclasses import fields
from typing import Any, cast
from uuid import UUID, uuid5

from sqlalchemy import func, insert, select, tuple_, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis_reuse import PostgresAnalysisReuseRepository
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.consistency_repair import (
    CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,
    CONTENT_CONSISTENCY_REPAIR_MAX_CONTENTS,
    ContentConsistencyRepairRun,
)
from aima_ugc.modules.content.consistency_repair_tables import (
    content_consistency_repair_runs_table as runs,
)
from aima_ugc.modules.content.consistency_repair_tables import (
    content_consistency_repair_targets_table as targets,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.vehicles.content_reclassification import (
    dump_catalog_snapshot,
    load_catalog_snapshot,
)
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_brand_review_locks_table,
    content_vehicle_evidence_table,
    content_vehicle_review_locks_table,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobRecord, LeaseLostError
from aima_ugc.platform.time import beijing_now

_NAMESPACE = UUID("2eb0de4a-9875-49a5-8cb0-6b212d029af6")
_COUNTERS = (
    "candidate_count",
    "brand_changed_count",
    "reused_count",
    "existing_reuse_count",
    "unmatched_count",
)


class PostgresContentConsistencyRepairRepository:
    """只写修复 Run/Targets；派生业务事实继续由各 Owner 维护。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方的同一 PostgreSQL 事务。"""
        self._session = session

    def resolve_targets(
        self,
        *,
        content_ids: tuple[UUID, ...],
        collection_run_id: UUID | None,
        max_contents: int,
    ) -> tuple[UUID, ...]:
        """只从显式集合或一个 Run 的成功来源账本前向找目标，超限拒绝。"""
        if not 1 <= max_contents <= CONTENT_CONSISTENCY_REPAIR_MAX_CONTENTS:
            raise ValueError("max_contents 必须是 1—10000")
        if bool(content_ids) == (collection_run_id is not None):
            raise ValueError("必须且只能指定 content_ids 或 collection_run_id")
        if content_ids:
            requested = tuple(sorted(set(content_ids)))
            if len(requested) > max_contents:
                raise ValueError("显式目标超过 max_contents，未创建修复任务")
            found = tuple(
                self._session.scalars(
                    select(contents_table.c.id)
                    .where(contents_table.c.id.in_(requested))
                    .order_by(contents_table.c.id)
                )
            )
            if found != requested:
                raise ValueError("显式目标包含不存在的 Content")
            return found
        if (
            self._session.scalar(
                select(collection_runs_table.c.id).where(
                    collection_runs_table.c.id == collection_run_id
                )
            )
            is None
        ):
            raise ValueError("找不到指定 Collection Run")
        ingestion, candidate, attempt, request, scope = (
            collection_candidate_ingestions_table,
            collection_candidates_table,
            provider_request_attempts_table,
            provider_requests_table,
            collection_scopes_table,
        )
        ids = tuple(
            self._session.scalars(
                select(ingestion.c.content_id)
                .select_from(scope)
                .join(request, request.c.scope_id == scope.c.id)
                .join(attempt, attempt.c.provider_request_id == request.c.id)
                .join(candidate, candidate.c.provider_request_attempt_id == attempt.c.id)
                .join(ingestion, ingestion.c.candidate_id == candidate.c.id)
                .where(
                    scope.c.run_id == collection_run_id,
                    ingestion.c.result.in_(("ingested", "duplicate")),
                    ingestion.c.target_type == "content",
                    ingestion.c.content_id.is_not(None),
                )
                .distinct()
                .order_by(ingestion.c.content_id)
                .limit(max_contents + 1)
            )
        )
        if len(ids) > max_contents:
            raise ValueError("Collection Run 成功目标超过 max_contents，未创建修复任务")
        return ids

    def dry_run(
        self,
        *,
        content_ids: tuple[UUID, ...],
        collection_run_id: UUID | None,
        max_contents: int,
        batch_size: int = 200,
    ) -> dict[str, object]:
        """只读评估有限目标，不创建 Job/Run/关系，也不调用模型或 Provider。"""
        _validate_batch_size(batch_size)
        ids = self.resolve_targets(
            content_ids=content_ids,
            collection_run_id=collection_run_id,
            max_contents=max_contents,
        )
        reasons: Counter[str] = Counter()
        candidates = equivalent = brand_candidates = 0
        for offset in range(0, len(ids), batch_size):
            pairs = tuple(
                (cast(UUID, row.id), cast(int, row.current_version))
                for row in self._session.execute(
                    select(contents_table.c.id, contents_table.c.current_version)
                    .where(contents_table.c.id.in_(ids[offset : offset + batch_size]))
                    .order_by(contents_table.c.id)
                )
            )
            missing = self.brand_candidate_ids(pairs)
            plans = PostgresAnalysisReuseRepository(self._session).plan_reuses(pairs)
            brand_candidates += len(missing)
            for plan in plans:
                reasons[plan.reason] += 1
                equivalent += plan.reason == "equivalent"
                candidates += plan.content_id in missing or plan.reason not in (
                    "direct",
                    "no_success",
                    "target_missing",
                )
        return {
            "target_count": len(ids),
            "candidate_count": candidates,
            "brand_candidate_count": brand_candidates,
            "equivalent_count": equivalent,
            "analysis_reasons": dict(sorted(reasons.items())),
            "catalog_version": PostgresBrandVehicleRepository(
                self._session
            ).current_catalog_version(),
        }

    def enqueue(
        self,
        *,
        content_ids: tuple[UUID, ...],
        collection_run_id: UUID | None,
        max_contents: int,
        batch_size: int,
        idempotency_key: str,
        created_by: str,
        request_id: str | None = None,
    ) -> tuple[ContentConsistencyRepairRun, JobRecord]:
        """冻结有限目标和目录，与正式 Job 原子创建；重复调用不扩大范围。"""
        _validate_batch_size(batch_size)
        key, actor = idempotency_key.strip(), created_by.strip()
        if not key or len(key) > 200 or not actor or len(actor) > 200:
            raise ValueError("idempotency_key 与 created_by 必须是 1—200 字符")
        if not 1 <= max_contents <= CONTENT_CONSISTENCY_REPAIR_MAX_CONTENTS:
            raise ValueError("max_contents 必须是 1—10000")
        if bool(content_ids) == (collection_run_id is not None):
            raise ValueError("必须且只能指定 content_ids 或 collection_run_id")
        self._session.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended(f"content-consistency:{key}", 0))
            )
        )
        run_id = uuid5(_NAMESPACE, key)
        existing = self.get(run_id)
        if existing is not None:
            if (
                existing.source_collection_run_id != collection_run_id
                or existing.max_contents != max_contents
                or existing.batch_size != batch_size
                or existing.created_by != actor
                or (content_ids and self.target_ids(run_id) != tuple(sorted(set(content_ids))))
            ):
                raise ValueError("idempotency_key 已绑定不同的修复范围或参数")
            job = PostgresJobRepository(self._session).get(existing.job_id)
            if job is None:
                raise RuntimeError("修复 Run 缺少对应 Job")
            return existing, job
        ids = self.resolve_targets(
            content_ids=content_ids, collection_run_id=collection_run_id, max_contents=max_contents
        )
        snapshot = PostgresBrandVehicleRepository(self._session).snapshot(brand_ids=None)
        if snapshot.unresolved_active_vehicle_ids:
            raise ValueError("存在未完成品牌归属的 active 车型，不能启动一致性修复")
        job = PostgresJobRepository(self._session).enqueue(
            job_type=CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,
            payload_version=CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,
            payload={"schema_version": CONTENT_CONSISTENCY_REPAIR_JOB_TYPE, "run_id": str(run_id)},
            internal_idempotency_key=f"content-consistency-repair:{key}",
            request_id=request_id,
            priority=0,
            max_attempts=10,
            timeout_seconds=86_400,
        )
        now = beijing_now()
        self._session.execute(
            insert(runs).values(
                id=run_id,
                job_id=job.id,
                catalog_snapshot=dump_catalog_snapshot(snapshot),
                source_collection_run_id=collection_run_id,
                batch_size=batch_size,
                max_contents=max_contents,
                target_count=len(ids),
                created_by=actor,
                created_at=now,
                updated_at=now,
            )
        )
        if ids:
            self._session.execute(
                insert(targets), [{"run_id": run_id, "content_id": item} for item in ids]
            )
        created = self.get(run_id)
        if created is None:
            raise RuntimeError("修复 Run 创建后不可读")
        return created, job

    def get(self, run_id: UUID, *, for_update: bool = False) -> ContentConsistencyRepairRun | None:
        """读取持久范围及进度；执行批次前锁住 Run。"""
        statement = select(runs).where(runs.c.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _run_from_row(row)

    def target_ids(self, run_id: UUID) -> tuple[UUID, ...]:
        """读取已经冻结的有限显式集合，供幂等参数复核。"""
        return tuple(
            self._session.scalars(
                select(targets.c.content_id)
                .where(targets.c.run_id == run_id)
                .order_by(targets.c.content_id)
            )
        )

    def load_next_target_ids(self, run: ContentConsistencyRepairRun) -> tuple[UUID, ...]:
        """先从 (run_id, content_id) 索引取页，不在全库 Content 上做候选过滤。"""
        statement = select(targets.c.content_id).where(targets.c.run_id == run.id)
        if run.checkpoint_content_id is not None:
            statement = statement.where(targets.c.content_id > run.checkpoint_content_id)
        return tuple(
            self._session.scalars(statement.order_by(targets.c.content_id).limit(run.batch_size))
        )

    def brand_candidate_ids(self, pairs: tuple[tuple[UUID, int], ...]) -> set[UUID]:
        """只检查页内缺少当前证据且存在旧证据或版本演进的 Content。"""
        versions = dict(pairs)
        if not versions:
            return set()
        current: set[UUID] = set()
        historical: set[UUID] = set()
        for table in (content_brand_evidence_table, content_vehicle_evidence_table):
            for row in self._session.execute(
                select(table.c.content_id, table.c.content_version)
                .where(table.c.content_id.in_(versions), table.c.is_active.is_(True))
                .distinct()
            ):
                (current if row.content_version == versions[row.content_id] else historical).add(
                    row.content_id
                )
        return {
            content_id
            for content_id, version in pairs
            if content_id not in current and (version > 1 or content_id in historical)
        }

    def manual_carry_sources(
        self, pairs: tuple[tuple[UUID, int], ...]
    ) -> tuple[tuple[tuple[UUID, int, int], ...], tuple[tuple[UUID, int, int], ...]]:
        """分别选择车型和品牌最新历史锁；unlocked 行阻止旧锁复活。"""
        versions = dict(pairs)
        if not versions:
            return (), ()
        sources = []
        for table in (content_vehicle_review_locks_table, content_brand_review_locks_table):
            latest: dict[UUID, tuple[int, bool]] = {}
            for row in self._session.execute(
                select(table.c.content_id, table.c.content_version, table.c.is_locked)
                .where(table.c.content_id.in_(versions))
                .order_by(table.c.content_id, table.c.content_version.desc())
            ):
                if row.content_version <= versions[row.content_id]:
                    latest.setdefault(row.content_id, (row.content_version, row.is_locked))
            sources.append(
                tuple(
                    (content_id, source, versions[content_id])
                    for content_id, (source, locked) in latest.items()
                    if locked and source < versions[content_id]
                )
            )
        return sources[0], sources[1]

    def evidence_state(self, pairs: tuple[tuple[UUID, int], ...]) -> dict[UUID, tuple[object, ...]]:
        """读取页内真实有效证据与人工锁，用前后差异统计实际业务变化。"""
        values: dict[UUID, list[object]] = {item[0]: [] for item in pairs}
        if not pairs:
            return {}
        for table in (
            content_vehicle_evidence_table,
            content_brand_evidence_table,
            content_vehicle_review_locks_table,
            content_brand_review_locks_table,
        ):
            statement = select(table).where(
                tuple_(table.c.content_id, table.c.content_version).in_(pairs)
            )
            if "is_active" in table.c:
                statement = statement.where(table.c.is_active.is_(True))
            for row in self._session.execute(statement):
                values[row.content_id].append((table.name, tuple(row)))
        return {item: tuple(sorted(rows, key=repr)) for item, rows in values.items()}

    def advance(
        self,
        *,
        run: ContentConsistencyRepairRun,
        checkpoint_content_id: UUID,
        processed_count: int,
        counters: dict[str, int],
        analysis_reasons: dict[str, int],
        fence: JobExecutionFence,
    ) -> ContentConsistencyRepairRun:
        """业务写入后重验 Fence，CAS 检查点并在同一事务累计真实统计。"""
        PostgresJobRepository(self._session).lock_current_execution(fence)
        if fence.job_id != run.job_id:
            raise LeaseLostError("修复 Fence 不属于此 Run")
        if processed_count <= 0 or (
            run.checkpoint_content_id is not None
            and checkpoint_content_id <= run.checkpoint_content_id
        ):
            raise ValueError("修复检查点必须向前推进")
        reasons = Counter(run.analysis_reasons)
        reasons.update(analysis_reasons)
        values: dict[str, Any] = {
            "checkpoint_content_id": checkpoint_content_id,
            "processed_count": runs.c.processed_count + processed_count,
            "analysis_reasons": dict(reasons),
            "updated_at": beijing_now(),
        }
        for name in _COUNTERS:
            values[name] = runs.c[name] + counters.get(name, 0)
        checkpoint_condition = (
            runs.c.checkpoint_content_id.is_(None)
            if run.checkpoint_content_id is None
            else runs.c.checkpoint_content_id == run.checkpoint_content_id
        )
        row = (
            self._session.execute(
                update(runs)
                .where(
                    runs.c.id == run.id,
                    runs.c.job_id == fence.job_id,
                    runs.c.processed_count == run.processed_count,
                    checkpoint_condition,
                )
                .values(**values)
                .returning(runs)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LeaseLostError("修复检查点已由其他执行推进")
        return _run_from_row(row)

    def request_cancel(self, run_id: UUID) -> JobRecord:
        """通过既有 Job Runtime 取消，不复制取消状态机。"""
        run = self.get(run_id)
        if run is None:
            raise LookupError(run_id)
        return PostgresJobRepository(self._session).request_cancel(run.job_id)


def _validate_batch_size(batch_size: int) -> None:
    """在预检与执行共用有界批次约束。"""
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size 必须是 1—1000")


def _run_from_row(row: RowMapping) -> ContentConsistencyRepairRun:
    """从机器表恢复冻结记录，不重新解释目录协议。"""
    values = {field.name: row[field.name] for field in fields(ContentConsistencyRepairRun)}
    values["catalog_snapshot"] = load_catalog_snapshot(row["catalog_snapshot"])
    return ContentConsistencyRepairRun(**values)
