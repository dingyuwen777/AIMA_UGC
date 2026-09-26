"""Persistent Canonical Replay Run 的 PostgreSQL Owner Repository。"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, insert, literal, select, union_all, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_ARTIFACTS_PER_RUN,
    CANONICAL_REPLAY_FAST_BATCH_SIZE,
    CANONICAL_REPLAY_JOB_MAX_ATTEMPTS,
    CANONICAL_REPLAY_PLAN_JOB_PAYLOAD_VERSION,
    CANONICAL_REPLAY_PLAN_JOB_TYPE,
    CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
    CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS,
    CANONICAL_REPLAY_JOB_TYPE,
    CANONICAL_REPLAY_REVERSAL_JOB_PAYLOAD_VERSION,
    CANONICAL_REPLAY_REVERSAL_JOB_TYPE,
    CanonicalReplayAllRequestRecord,
    CanonicalReplayArtifactRecord,
    CanonicalReplayCounters,
    CanonicalReplayLifecycleStatus,
    CanonicalReplayRunRecord,
    CanonicalReplaySourceKind,
    dump_filter_snapshot,
    load_filter_snapshot,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_all_requests_table,
    canonical_replay_run_artifacts_table,
    canonical_replay_runs_table,
    canonical_replay_seen_content_table,
    canonical_replay_validation_proofs_table,
)
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_IMPORT_CHUNK_JOB_TYPE
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.jobs import JobExecutionFence, JobRecord
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.canonical import CANONICAL_CONTENT_ARTIFACT_KIND
from aima_ugc.platform.storage.models import ArtifactRecord
from aima_ugc.platform.storage.tables import artifacts_table, canonical_artifact_links_table
from aima_ugc.platform.time import beijing_now

from .artifact_metadata import PostgresArtifactMetadataRepository
from .brand_vehicle import PostgresBrandVehicleRepository
from .jobs import PostgresJobRepository

_RUN_NAMESPACE = UUID("6112f610-4803-4590-a121-9f225e729e95")
_ALL_REQUEST_NAMESPACE = UUID("51f57b7c-40e0-41bb-8fb7-0d8bf723333d")
_PENDING_SELECTION_DIGEST = hashlib.sha256(b"canonical-replay-plan-pending-v1").hexdigest()


class UnsupportedCanonicalReplaySource(ValueError):
    """Artifact 不是当前三种可证明 lineage 的 Persistent Canonical。"""


class RevokedCanonicalReplaySource(UnsupportedCanonicalReplaySource):
    """冻结输入的 Data Import 来源已进入撤销状态，可跳过继续其他来源。"""


class PostgresCanonicalReplayRepository:
    """冻结 Replay 输入，并原子推进当前 Fence 的检查点与统计。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_validation_proof(self, artifact_id: UUID) -> RowMapping | None:
        """读取已持久化证明；调用方还须复核实际字节及当前来源关系。"""

        return (
            self._session.execute(
                select(canonical_replay_validation_proofs_table).where(
                    canonical_replay_validation_proofs_table.c.artifact_id == artifact_id
                )
            )
            .mappings()
            .one_or_none()
        )

    def save_validation_proof(
        self,
        *,
        artifact: ArtifactRecord,
        validation_version: str,
        source_kind: CanonicalReplaySourceKind,
        source_expectations: list[dict[str, str]],
    ) -> None:
        """仅在完整预检及来源验证成功后保存可再生证明。"""

        if artifact.sha256 is None or artifact.byte_size is None:
            raise ValueError("Canonical Artifact 缺少完整性元数据")
        values = {
            "artifact_id": artifact.id,
            "sha256": artifact.sha256,
            "byte_size": artifact.byte_size,
            "validation_version": validation_version,
            "source_kind": source_kind,
            "source_expectations": source_expectations,
            "validated_at": beijing_now(),
        }
        self._session.execute(
            pg_insert(canonical_replay_validation_proofs_table)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[canonical_replay_validation_proofs_table.c.artifact_id],
                set_={key: value for key, value in values.items() if key != "artifact_id"},
            )
        )

    def enqueue(
        self,
        *,
        idempotency_key: str,
        artifact_ids: tuple[UUID, ...],
        brand_ids: tuple[UUID, ...],
        batch_size: int,
        created_by: str,
        request_id: str | None,
    ) -> tuple[CanonicalReplayRunRecord, JobRecord]:
        """校验当前输入、冻结目录，并与 Job 在同一事务创建 Run。"""

        key = idempotency_key.strip()
        actor = created_by.strip()
        normalized_artifact_ids = tuple(artifact_ids)
        normalized_brand_ids = tuple(sorted(set(brand_ids), key=str))
        if not key or len(key) > 200:
            raise ValueError("idempotency_key 必须是 1—200 字符")
        if not actor or len(actor) > 200:
            raise ValueError("created_by 必须是 1—200 字符")
        if not 1 <= len(normalized_artifact_ids) <= CANONICAL_REPLAY_ARTIFACTS_PER_RUN:
            raise ValueError("artifact_ids 必须包含 1—100 个 Artifact")
        if len(set(normalized_artifact_ids)) != len(normalized_artifact_ids):
            raise ValueError("artifact_ids 不能重复")
        if len(normalized_brand_ids) != len(brand_ids) or len(normalized_brand_ids) > 100:
            raise ValueError("brand_ids 必须不重复且不超过 100 个")
        if not 1 <= batch_size <= CANONICAL_REPLAY_FAST_BATCH_SIZE:
            raise ValueError("batch_size 必须是 1—1000")

        self._lock_idempotency_key(key)
        run_id = uuid5(_RUN_NAMESPACE, key)
        existing = self.get(run_id)
        if existing is not None:
            existing_artifacts = tuple(item.artifact_id for item in self.list_artifacts(run_id))
            requested_identity = (
                normalized_artifact_ids,
                normalized_brand_ids,
                batch_size,
                actor,
            )
            existing_identity = (
                existing_artifacts,
                existing.requested_brand_ids,
                existing.batch_size,
                existing.created_by,
            )
            if requested_identity != existing_identity:
                raise RuntimeError("idempotency_key 已绑定不同 Replay 输入或参数")
            job = PostgresJobRepository(self._session).get(existing.job_id)
            if job is None:
                raise RuntimeError("Canonical Replay Run 缺少对应 Job")
            return existing, job

        source_kinds = tuple(self._classify_artifact(item) for item in normalized_artifact_ids)
        catalog = PostgresBrandVehicleRepository(self._session).snapshot(
            brand_ids=normalized_brand_ids or None
        )
        if catalog.unresolved_active_vehicle_ids:
            raise RuntimeError("存在未完成品牌归属的 active 车型，不能启动 Replay")
        snapshot = BrandVehicleFilterSnapshot(catalog=catalog)
        return self._create_run(
            key=key,
            artifact_ids=normalized_artifact_ids,
            source_kinds=source_kinds,
            snapshot=snapshot,
            brand_ids=normalized_brand_ids,
            batch_size=batch_size,
            created_by=actor,
            request_id=request_id,
        )

    def enqueue_all(
        self,
        *,
        idempotency_key: str,
        created_by: str,
        request_id: str | None,
        filter_snapshot: BrandVehicleFilterSnapshot,
    ) -> tuple[CanonicalReplayAllRequestRecord, JobRecord | None]:
        """只受理父请求并排队 Planner；不在 HTTP 事务扫描历史 Artifact。"""

        key = idempotency_key.strip()
        actor = created_by.strip()
        if not key or len(key) > 120:
            raise ValueError("idempotency_key 必须是 1—120 字符")
        if not actor or len(actor) > 200:
            raise ValueError("created_by 必须是 1—200 字符")
        if filter_snapshot.catalog.unresolved_active_vehicle_ids:
            raise RuntimeError("存在未完成品牌归属的 active 车型，不能启动 Replay")

        self._lock_all_idempotency_key(key)
        all_request_id = uuid5(_ALL_REQUEST_NAMESPACE, key)
        existing = self._get_all_request(all_request_id)
        jobs = PostgresJobRepository(self._session)
        if existing is not None:
            if existing.client_idempotency_key != key or existing.created_by != actor:
                raise RuntimeError("idempotency_key 已绑定不同的全量 Replay 创建者")
            return existing, jobs.get_by_identity(
                job_type=CANONICAL_REPLAY_PLAN_JOB_TYPE,
                internal_idempotency_key=f"canonical-replay-plan:{all_request_id}",
            )

        accepted_before = cast(datetime, self._session.scalar(select(func.clock_timestamp())))
        self._session.execute(
            insert(canonical_replay_all_requests_table).values(
                id=all_request_id,
                client_idempotency_key=key,
                selection_digest=_PENDING_SELECTION_DIGEST,
                artifact_count=0,
                run_count=0,
                artifacts_per_run=CANONICAL_REPLAY_ARTIFACTS_PER_RUN,
                batch_size=CANONICAL_REPLAY_FAST_BATCH_SIZE,
                created_by=actor,
                created_at=accepted_before,
                reversible=False,
                lifecycle_status="active",
            )
        )
        planner = jobs.enqueue(
            job_type=CANONICAL_REPLAY_PLAN_JOB_TYPE,
            payload_version=CANONICAL_REPLAY_PLAN_JOB_PAYLOAD_VERSION,
            payload={
                "schema_version": CANONICAL_REPLAY_PLAN_JOB_PAYLOAD_VERSION,
                "request_id": str(all_request_id),
                "accepted_before": accepted_before.isoformat(),
                "filter_snapshot": dump_filter_snapshot(filter_snapshot),
            },
            internal_idempotency_key=f"canonical-replay-plan:{all_request_id}",
            request_id=request_id,
            priority=0,
            max_attempts=CANONICAL_REPLAY_JOB_MAX_ATTEMPTS,
            timeout_seconds=CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS,
        )
        created = self._get_all_request(all_request_id)
        if created is None:
            raise RuntimeError("全量 Replay 请求创建后不可读")
        return created, planner

    @staticmethod
    def planning_status(record: CanonicalReplayAllRequestRecord) -> str:
        """由持久 selection digest 判断父请求是否仍处于后台规划阶段。"""

        return "queued" if record.selection_digest == _PENDING_SELECTION_DIGEST else "planned"

    def list_replayable_artifacts(
        self,
        *,
        accepted_before: datetime,
    ) -> tuple[tuple[UUID, CanonicalReplaySourceKind], ...]:
        """枚举受理时间边界内的可证明 Canonical；新 Artifact 不进入既有请求。"""

        return self._list_replayable_artifacts(accepted_before=accepted_before)

    def complete_all_plan(
        self,
        *,
        request_id: UUID,
        accepted_before: datetime,
        candidates: tuple[tuple[UUID, CanonicalReplaySourceKind], ...],
        snapshot: BrandVehicleFilterSnapshot,
        http_request_id: str | None,
    ) -> CanonicalReplayAllRequestRecord:
        """在后台原子提交 selection 摘要及所有子 Run；取消先到达时不再派生工作。"""

        record = self.get_all_request(request_id, for_update=True)
        if record is None:
            raise LookupError(request_id)
        if record.selection_digest != _PENDING_SELECTION_DIGEST:
            return record
        if record.lifecycle_status != "active":
            return record
        if record.created_at != accepted_before:
            raise RuntimeError("Replay Planner 受理时间边界发生漂移")

        selection_digest = _selection_digest(candidates)
        artifact_count = len(candidates)
        run_count = (
            artifact_count + CANONICAL_REPLAY_ARTIFACTS_PER_RUN - 1
        ) // CANONICAL_REPLAY_ARTIFACTS_PER_RUN
        for ordinal in range(run_count):
            start = ordinal * CANONICAL_REPLAY_ARTIFACTS_PER_RUN
            selected = candidates[start : start + CANONICAL_REPLAY_ARTIFACTS_PER_RUN]
            child_key = f"canonical-replay-all:{request_id}:{ordinal}"
            if self.get(uuid5(_RUN_NAMESPACE, child_key)) is not None:
                raise RuntimeError("全量 Replay 子 Run 幂等身份冲突")
            self._create_run(
                key=child_key,
                artifact_ids=tuple(item[0] for item in selected),
                source_kinds=tuple(item[1] for item in selected),
                snapshot=snapshot,
                brand_ids=(),
                batch_size=CANONICAL_REPLAY_FAST_BATCH_SIZE,
                created_by=record.created_by,
                request_id=http_request_id,
                all_request_id=request_id,
                all_request_ordinal=ordinal,
            )
        self._session.execute(
            update(canonical_replay_all_requests_table)
            .where(
                canonical_replay_all_requests_table.c.id == request_id,
                canonical_replay_all_requests_table.c.selection_digest
                == _PENDING_SELECTION_DIGEST,
            )
            .values(
                selection_digest=selection_digest,
                artifact_count=artifact_count,
                run_count=run_count,
                reversible=True,
            )
        )
        planned = self._get_all_request(request_id)
        if planned is None:
            raise RuntimeError("全量 Replay 规划提交后父请求不可读")
        return planned

    def _create_run(
        self,
        *,
        key: str,
        artifact_ids: tuple[UUID, ...],
        source_kinds: tuple[CanonicalReplaySourceKind, ...],
        snapshot: BrandVehicleFilterSnapshot,
        brand_ids: tuple[UUID, ...],
        batch_size: int,
        created_by: str,
        request_id: str | None,
        all_request_id: UUID | None = None,
        all_request_ordinal: int | None = None,
    ) -> tuple[CanonicalReplayRunRecord, JobRecord]:
        """把已校验并冻结的一个有界输入组与 Job 同事务落库。"""

        if len(artifact_ids) != len(source_kinds):
            raise ValueError("Canonical Replay Artifact 与来源分类数量不一致")
        run_id = uuid5(_RUN_NAMESPACE, key)
        job = PostgresJobRepository(self._session).enqueue(
            job_type=CANONICAL_REPLAY_JOB_TYPE,
            payload_version=CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
            payload={
                "schema_version": CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
                "run_id": str(run_id),
            },
            internal_idempotency_key=f"canonical-replay:{key}",
            request_id=request_id,
            priority=0,
            max_attempts=CANONICAL_REPLAY_JOB_MAX_ATTEMPTS,
            timeout_seconds=CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS,
        )
        now = beijing_now()
        self._session.execute(
            insert(canonical_replay_runs_table).values(
                id=run_id,
                job_id=job.id,
                client_idempotency_key=key,
                filter_snapshot=dump_filter_snapshot(snapshot),
                requested_brand_ids=list(brand_ids),
                artifact_count=len(artifact_ids),
                checkpoint_artifact_ordinal=0,
                checkpoint_row_number=0,
                batch_size=batch_size,
                created_by=created_by,
                created_at=now,
                updated_at=now,
                all_request_id=all_request_id,
                all_request_ordinal=all_request_ordinal,
            )
        )
        self._session.execute(
            insert(canonical_replay_run_artifacts_table),
            [
                {
                    "run_id": run_id,
                    "ordinal": ordinal,
                    "artifact_id": artifact_id,
                    "source_kind": source_kind,
                }
                for ordinal, (artifact_id, source_kind) in enumerate(
                    zip(artifact_ids, source_kinds, strict=True)
                )
            ],
        )
        created = self.get(run_id)
        if created is None:
            raise RuntimeError("Canonical Replay Run 创建后不可读")
        return created, job

    def _get_all_request(self, request_id: UUID) -> CanonicalReplayAllRequestRecord | None:
        row = (
            self._session.execute(
                select(canonical_replay_all_requests_table).where(
                    canonical_replay_all_requests_table.c.id == request_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _all_request_from_row(row)

    def get_all_request(
        self,
        request_id: UUID,
        *,
        for_update: bool = False,
    ) -> CanonicalReplayAllRequestRecord | None:
        """读取父请求；状态转换时由调用方显式要求行锁。"""

        statement = select(canonical_replay_all_requests_table).where(
            canonical_replay_all_requests_table.c.id == request_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _all_request_from_row(row)

    def _list_replayable_artifacts(
        self,
        *,
        accepted_before: datetime,
    ) -> tuple[tuple[UUID, CanonicalReplaySourceKind], ...]:
        """用确定性查询枚举受理时间边界内三类可证明来源的 linked Canonical。"""

        common_filters = (
            artifacts_table.c.kind == CANONICAL_CONTENT_ARTIFACT_KIND,
            artifacts_table.c.storage_status == "linked",
            artifacts_table.c.created_at <= accepted_before,
        )
        excel = (
            select(
                artifacts_table.c.id.label("artifact_id"),
                artifacts_table.c.created_at.label("created_at"),
                literal("excel_import_v2").label("source_kind"),
            )
            .select_from(
                artifacts_table.join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.artifact_id == artifacts_table.c.id,
                )
                .join(
                    processing_import_batches_table,
                    processing_import_batches_table.c.id
                    == canonical_artifact_links_table.c.processing_import_batch_id,
                )
                .join(
                    jobs_table,
                    jobs_table.c.id == processing_import_batches_table.c.job_id,
                )
            )
            .where(
                *common_filters,
                processing_import_batches_table.c.historical_campaign_item_id.is_(None),
                jobs_table.c.job_type == IMPORT_JOB_TYPE,
            )
        )
        historical = (
            select(
                artifacts_table.c.id.label("artifact_id"),
                artifacts_table.c.created_at.label("created_at"),
                literal("data_import_canonical_chunk_v2").label("source_kind"),
            )
            .select_from(
                artifacts_table.join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.artifact_id == artifacts_table.c.id,
                )
                .join(
                    historical_import_campaign_items_table,
                    historical_import_campaign_items_table.c.id
                    == canonical_artifact_links_table.c.historical_import_campaign_item_id,
                )
                .join(
                    historical_import_campaigns_table,
                    historical_import_campaigns_table.c.id
                    == historical_import_campaign_items_table.c.campaign_id,
                )
                .join(
                    jobs_table,
                    jobs_table.c.id == historical_import_campaign_items_table.c.job_id,
                )
            )
            .where(
                *common_filters,
                historical_import_campaign_items_table.c.item_kind == "chunk",
                historical_import_campaign_items_table.c.artifact_id == artifacts_table.c.id,
                historical_import_campaigns_table.c.status.notin_(("revoking", "revoked")),
                jobs_table.c.job_type == HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
            )
        )
        tikhub = (
            select(
                artifacts_table.c.id.label("artifact_id"),
                artifacts_table.c.created_at.label("created_at"),
                literal("tikhub_search_attempt_v1").label("source_kind"),
            )
            .select_from(
                artifacts_table.join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.artifact_id == artifacts_table.c.id,
                )
                .join(
                    provider_request_attempts_table,
                    provider_request_attempts_table.c.id
                    == canonical_artifact_links_table.c.provider_attempt_id,
                )
                .join(
                    provider_requests_table,
                    provider_requests_table.c.id
                    == provider_request_attempts_table.c.provider_request_id,
                )
                .join(
                    collection_scopes_table,
                    collection_scopes_table.c.id == provider_requests_table.c.scope_id,
                )
                .join(
                    collection_runs_table,
                    collection_runs_table.c.id == collection_scopes_table.c.run_id,
                )
                .join(jobs_table, jobs_table.c.id == collection_runs_table.c.job_id)
            )
            .where(
                *common_filters,
                provider_request_attempts_table.c.dispatch_status == "completed",
                provider_request_attempts_table.c.raw_artifact_id.is_not(None),
                provider_requests_table.c.provider == "tikhub",
                collection_scopes_table.c.operation_group == "content_discovery",
                jobs_table.c.job_type == "collection.run.v1",
            )
        )
        candidates = union_all(excel, historical, tikhub).subquery()
        rows = self._session.execute(
            select(candidates.c.artifact_id, candidates.c.source_kind).order_by(
                candidates.c.created_at,
                candidates.c.artifact_id,
            )
        )
        return tuple(
            (
                cast(UUID, row.artifact_id),
                cast(CanonicalReplaySourceKind, row.source_kind),
            )
            for row in rows
        )

    def get(
        self,
        run_id: UUID,
        *,
        for_update: bool = False,
    ) -> CanonicalReplayRunRecord | None:
        statement = select(canonical_replay_runs_table).where(
            canonical_replay_runs_table.c.id == run_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.execute(statement).mappings().one_or_none()
        return None if row is None else _run_from_row(row)

    def get_job(self, run_id: UUID) -> JobRecord | None:
        run = self.get(run_id)
        return None if run is None else PostgresJobRepository(self._session).get(run.job_id)

    def list_artifacts(self, run_id: UUID) -> tuple[CanonicalReplayArtifactRecord, ...]:
        rows = self._session.execute(
            select(canonical_replay_run_artifacts_table)
            .where(canonical_replay_run_artifacts_table.c.run_id == run_id)
            .order_by(canonical_replay_run_artifacts_table.c.ordinal)
        ).mappings()
        return tuple(_artifact_from_row(row) for row in rows)

    def load_artifact(self, artifact_id: UUID) -> ArtifactRecord | None:
        return PostgresArtifactMetadataRepository(self._session).get(artifact_id)

    def classify_artifact(self, artifact_id: UUID) -> CanonicalReplaySourceKind:
        """重新验证一个冻结输入仍属于当前支持的唯一来源结构。"""

        return self._classify_artifact(artifact_id)

    def request_cancel(self, run_id: UUID) -> JobRecord:
        run = self.get(run_id)
        if run is None:
            raise LookupError(run_id)
        return PostgresJobRepository(self._session).request_cancel(run.job_id)

    def request_all_reversal(
        self,
        request_id: UUID,
        *,
        cancel_active: bool,
        actor_ref: str,
        http_request_id: str,
    ) -> CanonicalReplayAllRequestRecord:
        """幂等请求整次撤回；运行中请求先协作取消全部子 Job。"""

        record = self.get_all_request(request_id, for_update=True)
        if record is None:
            raise LookupError(request_id)
        if not record.reversible:
            raise RuntimeError("该历史重筛创建时没有精确贡献账本，禁止撤回")
        if record.lifecycle_status == "reverted":
            return record

        jobs = self._list_all_request_jobs(request_id)
        active = tuple(job for job in jobs if job.status in {"queued", "running"})
        if active and not cancel_active:
            raise RuntimeError("历史重筛仍在运行，请使用取消并撤回")
        now = beijing_now()
        if cancel_active:
            job_repository = PostgresJobRepository(self._session)
            for job in active:
                job_repository.request_cancel(job.id)
            self._session.execute(
                update(canonical_replay_all_requests_table)
                .where(canonical_replay_all_requests_table.c.id == request_id)
                .values(
                    lifecycle_status="cancelling",
                    cancellation_requested_at=func.coalesce(
                        canonical_replay_all_requests_table.c.cancellation_requested_at,
                        now,
                    ),
                    reversal_requested_at=func.coalesce(
                        canonical_replay_all_requests_table.c.reversal_requested_at,
                        now,
                    ),
                    reversal_requested_by=func.coalesce(
                        canonical_replay_all_requests_table.c.reversal_requested_by,
                        actor_ref,
                    ),
                    reversal_request_id=func.coalesce(
                        canonical_replay_all_requests_table.c.reversal_request_id,
                        http_request_id,
                    ),
                )
            )
        else:
            self._session.execute(
                update(canonical_replay_all_requests_table)
                .where(canonical_replay_all_requests_table.c.id == request_id)
                .values(
                    reversal_requested_at=func.coalesce(
                        canonical_replay_all_requests_table.c.reversal_requested_at,
                        now,
                    ),
                    reversal_requested_by=func.coalesce(
                        canonical_replay_all_requests_table.c.reversal_requested_by,
                        actor_ref,
                    ),
                    reversal_request_id=func.coalesce(
                        canonical_replay_all_requests_table.c.reversal_request_id,
                        http_request_id,
                    ),
                )
            )
        self.ensure_reversal_job_if_ready(request_id)
        refreshed = self.get_all_request(request_id)
        if refreshed is None:
            raise RuntimeError("历史重筛撤回请求更新后不可读")
        return refreshed

    def ensure_reversal_job_if_ready(
        self,
        request_id: UUID,
    ) -> CanonicalReplayAllRequestRecord:
        """最后一个子 Job 终态后，在同一事务排队唯一撤回 Job。"""

        record = self.get_all_request(request_id, for_update=True)
        if record is None:
            raise LookupError(request_id)
        if record.lifecycle_status in {"reverted", "reverting"}:
            return record
        if record.reversal_requested_at is None:
            return record
        if any(
            job.status in {"queued", "running"} for job in self._list_all_request_jobs(request_id)
        ):
            return record
        job = PostgresJobRepository(self._session).enqueue(
            job_type=CANONICAL_REPLAY_REVERSAL_JOB_TYPE,
            payload_version=CANONICAL_REPLAY_REVERSAL_JOB_PAYLOAD_VERSION,
            payload={
                "schema_version": CANONICAL_REPLAY_REVERSAL_JOB_PAYLOAD_VERSION,
                "request_id": str(request_id),
            },
            internal_idempotency_key=(
                f"canonical-replay-reversal:{request_id}:{uuid4()}"
                if record.lifecycle_status == "revert_failed"
                else f"canonical-replay-reversal:{request_id}"
            ),
            request_id=record.reversal_request_id,
            priority=0,
            max_attempts=CANONICAL_REPLAY_JOB_MAX_ATTEMPTS,
            timeout_seconds=CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS,
        )
        self._session.execute(
            update(canonical_replay_all_requests_table)
            .where(canonical_replay_all_requests_table.c.id == request_id)
            .values(lifecycle_status="reverting", reversal_job_id=job.id)
        )
        refreshed = self.get_all_request(request_id)
        if refreshed is None:
            raise RuntimeError("历史重筛撤回 Job 创建后父请求不可读")
        return refreshed

    def mark_reversal_failed(self, request_id: UUID) -> None:
        """只有未成功结束的父请求可被撤回 Job 终态回调标记失败。"""

        self._session.execute(
            update(canonical_replay_all_requests_table)
            .where(
                canonical_replay_all_requests_table.c.id == request_id,
                canonical_replay_all_requests_table.c.lifecycle_status == "reverting",
            )
            .values(lifecycle_status="revert_failed")
        )

    def _list_all_request_jobs(self, request_id: UUID) -> tuple[JobRecord, ...]:
        """返回 Planner 与全部子 Run Job，供取消/撤回完成屏障统一判断。"""

        repository = PostgresJobRepository(self._session)
        planner = repository.get_by_identity(
            job_type=CANONICAL_REPLAY_PLAN_JOB_TYPE,
            internal_idempotency_key=f"canonical-replay-plan:{request_id}",
        )
        job_ids = self._session.scalars(
            select(jobs_table.c.id)
            .select_from(
                canonical_replay_runs_table.join(
                    jobs_table,
                    jobs_table.c.id == canonical_replay_runs_table.c.job_id,
                )
            )
            .where(canonical_replay_runs_table.c.all_request_id == request_id)
            .order_by(canonical_replay_runs_table.c.all_request_ordinal)
        )
        run_jobs = tuple(repository.get(cast(UUID, job_id)) for job_id in job_ids)
        if any(job is None for job in run_jobs):
            raise RuntimeError("全量 Replay 子 Run 缺少 Job")
        normalized = cast(tuple[JobRecord, ...], run_jobs)
        return ((planner,) if planner is not None else ()) + normalized

    def claim_content_identity(
        self,
        *,
        run_id: UUID,
        platform: str,
        external_content_id: str,
    ) -> bool:
        """持久声明本 Run 首次遇到的 Content identity，支持跨批次恢复去重。"""

        claimed = self._session.execute(
            pg_insert(canonical_replay_seen_content_table)
            .values(
                run_id=run_id,
                platform=platform,
                external_content_id=external_content_id,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    canonical_replay_seen_content_table.c.run_id,
                    canonical_replay_seen_content_table.c.platform,
                    canonical_replay_seen_content_table.c.external_content_id,
                ]
            )
            .returning(canonical_replay_seen_content_table.c.run_id)
        ).scalar_one_or_none()
        return claimed is not None

    def claim_content_identities(
        self,
        *,
        run_id: UUID,
        identities: Iterable[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        """一次声明当前事务中的匹配 identity，并返回本 Run 新取得的声明。"""

        distinct = tuple(dict.fromkeys(identities))
        if not distinct:
            return set()
        rows = self._session.execute(
            pg_insert(canonical_replay_seen_content_table)
            .values(
                [
                    {
                        "run_id": run_id,
                        "platform": platform,
                        "external_content_id": external_content_id,
                    }
                    for platform, external_content_id in distinct
                ]
            )
            .on_conflict_do_nothing(
                index_elements=[
                    canonical_replay_seen_content_table.c.run_id,
                    canonical_replay_seen_content_table.c.platform,
                    canonical_replay_seen_content_table.c.external_content_id,
                ]
            )
            .returning(
                canonical_replay_seen_content_table.c.platform,
                canonical_replay_seen_content_table.c.external_content_id,
            )
        )
        return {(row.platform, row.external_content_id) for row in rows}

    def advance(
        self,
        *,
        run_id: UUID,
        expected_artifact_ordinal: int,
        expected_row_number: int,
        next_artifact_ordinal: int,
        next_row_number: int,
        counters: CanonicalReplayCounters,
        fence: JobExecutionFence,
    ) -> CanonicalReplayRunRecord:
        """在当前 Fence 与预期 checkpoint 下原子累计一个已写业务批次。"""

        PostgresJobRepository(self._session).lock_current_execution(fence)
        row = (
            self._session.execute(
                update(canonical_replay_runs_table)
                .where(
                    canonical_replay_runs_table.c.id == run_id,
                    canonical_replay_runs_table.c.checkpoint_artifact_ordinal
                    == expected_artifact_ordinal,
                    canonical_replay_runs_table.c.checkpoint_row_number == expected_row_number,
                )
                .values(
                    checkpoint_artifact_ordinal=next_artifact_ordinal,
                    checkpoint_row_number=next_row_number,
                    rows_seen=canonical_replay_runs_table.c.rows_seen + counters.rows_seen,
                    rows_matched=(
                        canonical_replay_runs_table.c.rows_matched + counters.rows_matched
                    ),
                    rows_filtered_out=(
                        canonical_replay_runs_table.c.rows_filtered_out + counters.rows_filtered_out
                    ),
                    duplicates_removed=(
                        canonical_replay_runs_table.c.duplicates_removed
                        + counters.duplicates_removed
                    ),
                    rows_ingested=(
                        canonical_replay_runs_table.c.rows_ingested + counters.rows_ingested
                    ),
                    existing_convergence=(
                        canonical_replay_runs_table.c.existing_convergence
                        + counters.existing_convergence
                    ),
                    updated_at=beijing_now(),
                )
                .returning(canonical_replay_runs_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RuntimeError("Canonical Replay checkpoint 已被其他执行推进")
        return _run_from_row(row)

    def _classify_artifact(self, artifact_id: UUID) -> CanonicalReplaySourceKind:
        artifact = (
            self._session.execute(
                select(artifacts_table, canonical_artifact_links_table)
                .join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.artifact_id == artifacts_table.c.id,
                )
                .where(artifacts_table.c.id == artifact_id)
            )
            .mappings()
            .one_or_none()
        )
        if (
            artifact is None
            or artifact["kind"] != CANONICAL_CONTENT_ARTIFACT_KIND
            or artifact["storage_status"] != "linked"
        ):
            raise UnsupportedCanonicalReplaySource("Replay 只接受 linked Canonical Artifact")

        batch_id = cast(UUID | None, artifact["processing_import_batch_id"])
        historical_item_id = cast(UUID | None, artifact["historical_import_campaign_item_id"])
        scope_id = cast(UUID | None, artifact["collection_scope_id"])
        provider_attempt_id = cast(UUID | None, artifact["provider_attempt_id"])
        if scope_id is not None:
            raise UnsupportedCanonicalReplaySource(
                "Scope-only Canonical lineage 已淘汰，拒绝 Replay"
            )
        if batch_id is not None:
            job_type = self._session.scalar(
                select(processing_import_batches_table.c.id)
                .join(
                    jobs_table,
                    processing_import_batches_table.c.job_id == jobs_table.c.id,
                )
                .where(
                    processing_import_batches_table.c.id == batch_id,
                    processing_import_batches_table.c.historical_campaign_item_id.is_(None),
                    jobs_table.c.job_type == IMPORT_JOB_TYPE,
                )
            )
            if job_type is None:
                raise UnsupportedCanonicalReplaySource("Canonical 不属于当前 Excel Import v2")
            return "excel_import_v2"
        if historical_item_id is not None:
            source = self._session.execute(
                select(
                    historical_import_campaign_items_table.c.id,
                    historical_import_campaigns_table.c.status,
                )
                .join(
                    historical_import_campaigns_table,
                    historical_import_campaigns_table.c.id
                    == historical_import_campaign_items_table.c.campaign_id,
                )
                .join(
                    jobs_table,
                    historical_import_campaign_items_table.c.job_id == jobs_table.c.id,
                )
                .where(
                    historical_import_campaign_items_table.c.id == historical_item_id,
                    historical_import_campaign_items_table.c.item_kind == "chunk",
                    historical_import_campaign_items_table.c.artifact_id == artifact_id,
                    jobs_table.c.job_type == HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
                )
            ).one_or_none()
            if source is None:
                raise UnsupportedCanonicalReplaySource("Canonical 不属于可重筛的 Data Import Chunk")
            if source.status in ("revoking", "revoked"):
                raise RevokedCanonicalReplaySource("Data Import 来源正在撤销或已撤销")
            return "data_import_canonical_chunk_v2"
        if provider_attempt_id is not None:
            valid = self._session.scalar(
                select(provider_request_attempts_table.c.id)
                .join(
                    provider_requests_table,
                    provider_request_attempts_table.c.provider_request_id
                    == provider_requests_table.c.id,
                )
                .join(
                    collection_scopes_table,
                    provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                )
                .join(
                    collection_runs_table,
                    collection_scopes_table.c.run_id == collection_runs_table.c.id,
                )
                .join(
                    jobs_table,
                    collection_runs_table.c.job_id == jobs_table.c.id,
                )
                .where(
                    provider_request_attempts_table.c.id == provider_attempt_id,
                    provider_request_attempts_table.c.dispatch_status == "completed",
                    provider_request_attempts_table.c.raw_artifact_id.is_not(None),
                    provider_requests_table.c.provider == "tikhub",
                    collection_scopes_table.c.operation_group == "content_discovery",
                    jobs_table.c.job_type == "collection.run.v1",
                )
            )
            if valid is None:
                raise UnsupportedCanonicalReplaySource(
                    "Canonical 不属于当前 TikHub Discovery Search Attempt"
                )
            return "tikhub_search_attempt_v1"
        raise UnsupportedCanonicalReplaySource("Canonical lineage 无法唯一分类")

    def _lock_idempotency_key(self, key: str) -> None:
        """串行化同一客户端幂等键，保证并发创建也返回同一 Run/Job。"""

        lock_key = f"canonical-replay:{key}"
        self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )

    def _lock_all_idempotency_key(self, key: str) -> None:
        """串行化同一全量请求，使输入选择、父记录和全部子 Run 原子提交。"""

        lock_key = f"canonical-replay-all:{key}"
        self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )


def _all_request_from_row(row: RowMapping) -> CanonicalReplayAllRequestRecord:
    return CanonicalReplayAllRequestRecord(
        id=cast(UUID, row["id"]),
        client_idempotency_key=cast(str, row["client_idempotency_key"]),
        selection_digest=cast(str, row["selection_digest"]),
        artifact_count=cast(int, row["artifact_count"]),
        run_count=cast(int, row["run_count"]),
        artifacts_per_run=cast(int, row["artifacts_per_run"]),
        batch_size=cast(int, row["batch_size"]),
        created_by=cast(str, row["created_by"]),
        created_at=cast(datetime, row["created_at"]),
        reversible=cast(bool, row["reversible"]),
        lifecycle_status=cast(CanonicalReplayLifecycleStatus, row["lifecycle_status"]),
        reversal_job_id=cast(UUID | None, row["reversal_job_id"]),
        cancellation_requested_at=cast(datetime | None, row["cancellation_requested_at"]),
        reversal_requested_at=cast(datetime | None, row["reversal_requested_at"]),
        reversed_at=cast(datetime | None, row["reversed_at"]),
        reversal_requested_by=cast(str | None, row["reversal_requested_by"]),
        reversal_request_id=cast(str | None, row["reversal_request_id"]),
        reverted_content_count=cast(int, row["reverted_content_count"]),
        hidden_content_count=cast(int, row["hidden_content_count"]),
        retained_content_count=cast(int, row["retained_content_count"]),
        skipped_content_count=cast(int, row["skipped_content_count"]),
        restored_evidence_count=cast(int, row["restored_evidence_count"]),
        skipped_evidence_count=cast(int, row["skipped_evidence_count"]),
    )


def _selection_digest(
    candidates: tuple[tuple[UUID, CanonicalReplaySourceKind], ...],
) -> str:
    """对稳定有序的 Artifact/来源清单生成幂等输入摘要。"""

    digest = hashlib.sha256()
    for artifact_id, source_kind in candidates:
        digest.update(artifact_id.bytes)
        digest.update(b"\x00")
        digest.update(source_kind.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _run_from_row(row: RowMapping) -> CanonicalReplayRunRecord:
    return CanonicalReplayRunRecord(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        client_idempotency_key=cast(str, row["client_idempotency_key"]),
        filter_snapshot=load_filter_snapshot(row["filter_snapshot"]),
        requested_brand_ids=tuple(cast(list[UUID], row["requested_brand_ids"])),
        artifact_count=cast(int, row["artifact_count"]),
        checkpoint_artifact_ordinal=cast(int, row["checkpoint_artifact_ordinal"]),
        checkpoint_row_number=cast(int, row["checkpoint_row_number"]),
        batch_size=cast(int, row["batch_size"]),
        rows_seen=cast(int, row["rows_seen"]),
        rows_matched=cast(int, row["rows_matched"]),
        rows_filtered_out=cast(int, row["rows_filtered_out"]),
        duplicates_removed=cast(int, row["duplicates_removed"]),
        rows_ingested=cast(int, row["rows_ingested"]),
        existing_convergence=cast(int, row["existing_convergence"]),
        created_by=cast(str, row["created_by"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
        all_request_id=cast(UUID | None, row["all_request_id"]),
        all_request_ordinal=cast(int | None, row["all_request_ordinal"]),
    )


def _artifact_from_row(row: RowMapping) -> CanonicalReplayArtifactRecord:
    return CanonicalReplayArtifactRecord(
        run_id=cast(UUID, row["run_id"]),
        ordinal=cast(int, row["ordinal"]),
        artifact_id=cast(UUID, row["artifact_id"]),
        source_kind=cast(CanonicalReplaySourceKind, row["source_kind"]),
    )


__all__ = [
    "PostgresCanonicalReplayRepository",
    "RevokedCanonicalReplaySource",
    "UnsupportedCanonicalReplaySource",
]
