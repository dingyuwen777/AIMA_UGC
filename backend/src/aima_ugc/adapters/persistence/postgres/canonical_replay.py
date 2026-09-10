"""Persistent Canonical Replay Run 的 PostgreSQL Owner Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid5

from sqlalchemy import insert, select, update
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
    CANONICAL_REPLAY_JOB_MAX_ATTEMPTS,
    CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
    CANONICAL_REPLAY_JOB_TIMEOUT_SECONDS,
    CANONICAL_REPLAY_JOB_TYPE,
    CanonicalReplayArtifactRecord,
    CanonicalReplayCounters,
    CanonicalReplayRunRecord,
    CanonicalReplaySourceKind,
    dump_filter_snapshot,
    load_filter_snapshot,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_run_artifacts_table,
    canonical_replay_runs_table,
    canonical_replay_seen_content_table,
)
from aima_ugc.modules.ingestion.historical_jobs import HISTORICAL_IMPORT_CHUNK_JOB_TYPE
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaign_items_table
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


class UnsupportedCanonicalReplaySource(ValueError):
    """Artifact 不是当前三种可证明 lineage 的 Persistent Canonical。"""


class PostgresCanonicalReplayRepository:
    """冻结 Replay 输入，并原子推进当前 Fence 的检查点与统计。"""

    def __init__(self, session: Session) -> None:
        self._session = session

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
        if not 1 <= len(normalized_artifact_ids) <= 100:
            raise ValueError("artifact_ids 必须包含 1—100 个 Artifact")
        if len(set(normalized_artifact_ids)) != len(normalized_artifact_ids):
            raise ValueError("artifact_ids 不能重复")
        if len(normalized_brand_ids) != len(brand_ids) or len(normalized_brand_ids) > 100:
            raise ValueError("brand_ids 必须不重复且不超过 100 个")
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch_size 必须是 1—1000")

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
                requested_brand_ids=list(normalized_brand_ids),
                artifact_count=len(normalized_artifact_ids),
                checkpoint_artifact_ordinal=0,
                checkpoint_row_number=0,
                batch_size=batch_size,
                created_by=actor,
                created_at=now,
                updated_at=now,
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
                    zip(normalized_artifact_ids, source_kinds, strict=True)
                )
            ],
        )
        created = self.get(run_id)
        if created is None:
            raise RuntimeError("Canonical Replay Run 创建后不可读")
        return created, job

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
            valid = self._session.scalar(
                select(historical_import_campaign_items_table.c.id)
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
            )
            if valid is None:
                raise UnsupportedCanonicalReplaySource(
                    "Canonical 不属于当前 Data Import Pure Canonical Chunk v2"
                )
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
    )


def _artifact_from_row(row: RowMapping) -> CanonicalReplayArtifactRecord:
    return CanonicalReplayArtifactRecord(
        run_id=cast(UUID, row["run_id"]),
        ordinal=cast(int, row["ordinal"]),
        artifact_id=cast(UUID, row["artifact_id"]),
        source_kind=cast(CanonicalReplaySourceKind, row["source_kind"]),
    )


__all__ = ["PostgresCanonicalReplayRepository", "UnsupportedCanonicalReplaySource"]
