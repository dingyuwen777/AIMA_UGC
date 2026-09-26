"""Persistent Canonical Replay 的正式 PostgreSQL Job 执行器。"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Generator
from dataclasses import dataclass, replace
from itertools import islice
from time import perf_counter
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
    RevokedCanonicalReplaySource,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
    PostgresCompleteNewContentBatchItem,
)
from aima_ugc.adapters.persistence.postgres.content_contributions import (
    build_content_contribution_delta,
    capture_content_contribution_snapshots_batch,
)
from aima_ugc.adapters.persistence.postgres.import_lineage import (
    ensure_campaign_import_lineage,
    ensure_single_import_lineage,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.replay_shards import PostgresReplayShardRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.adapters.persistence.postgres.voice_plaza_projection import (
    defer_voice_plaza_projection,
    flush_deferred_voice_plaza_projection,
)
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.collection.tables import (
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.ingestion.brand_vehicle_filter import resolve_canonical_brand_vehicle
from aima_ugc.modules.ingestion.canonical_replay import (
    CanonicalReplayArtifactRecord,
    CanonicalReplayCounters,
    CanonicalReplayJobPayload,
    CanonicalReplayRunRecord,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_content_changes_table,
)
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
from aima_ugc.modules.ingestion.replay_shards import select_replay_shard_count
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandVehicleResolution,
    BrandVehicleResolver,
)
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.capacity import (
    AdaptiveBatchController,
    detect_resources,
    worker_process_limit,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.storage import (
    ArtifactRecord,
    CanonicalArtifactIntegrityError,
    CanonicalArtifactReader,
)
from aima_ugc.platform.storage.tables import artifacts_table, canonical_artifact_links_table
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

if TYPE_CHECKING:
    from .adaptive_shard_worker import AdaptiveShardCoordinator

_PREFLIGHT_BATCH_SIZE = 500
_SHARD_SAMPLE_ROWS_PER_ARTIFACT = 64
_PROVEN_SAMPLE_ROWS_LIMIT = 256
_LEDGER_INSERT_ROWS = 1000
_MAX_PROOF_SOURCE_EXPECTATIONS = 1000

# 结构变动由 Schema 摘要检测；非 Schema 可见的来源/Validator 语义改变时须提升此版本。
_VALIDATION_VERSION = (
    "replay-source-v1:"
    + hashlib.sha256(
        json.dumps(CanonicalContentV1.model_json_schema(), sort_keys=True).encode("utf-8")
    ).hexdigest()
)


@dataclass(frozen=True, slots=True)
class _ImportLineageContext:
    batch_id: UUID
    raw_artifact: ArtifactRecord
    operation: str


class PostgresCanonicalReplayJobExecutor:
    """先预检完整输入集，再按有界批次和当前 Fence 幂等 Replay。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self.shard_coordinator: AdaptiveShardCoordinator | None = None

    def execute(
        self,
        *,
        payload: CanonicalReplayJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """接管先重新预检全部输入；随后从已提交 checkpoint 继续。"""

        batch_tuner: AdaptiveBatchController | None = None
        phase = "load_execution"
        artifact_ordinal: int | None = None
        skipped_revoked_artifacts = 0
        batch_metrics: dict[str, int] = {
            "batch_count": 0,
            "artifact_read_ms": 0,
            "batch_elapsed_ms": 0,
            "resolution_ms": 0,
            "content_batch_ms": 0,
            "evidence_batch_ms": 0,
            "fallback_ms": 0,
            "fallback_snapshot_ms": 0,
            "fallback_content_ms": 0,
            "fallback_evidence_ms": 0,
            "fallback_ledger_ms": 0,
            "scalar_fallback_count": 0,
            "ledger_checkpoint_ms": 0,
            "transaction_ms": 0,
            "fast_created_count": 0,
            "fallback_count": 0,
        }
        try:
            run, selected = self._load_execution(payload.run_id, fence)
            if run.batch_size > 1:
                batch_tuner = AdaptiveBatchController(
                    lower=max(1, run.batch_size // 2),
                    upper=run.batch_size,
                    improvement_margin=0.20,
                )
            if run.checkpoint_artifact_ordinal >= run.artifact_count:
                return JobHandlerResult.succeeded(_result(run))

            # 预检资格仅属于本次 Attempt；接管必须重新证明输入全集。
            reader = CanonicalArtifactReader(store=self._runtime.artifact_store)
            preflight_started = perf_counter()
            phase = "preflight"
            preflight_ok, sampled_rows, matched_rows = self._preflight_all(
                selected, run=run, reader=reader, fence=fence, context=context
            )
            if not preflight_ok:
                return JobHandlerResult.cancelled()
            log_event(
                self._runtime.logger,
                logging.INFO,
                "canonical_replay.preflight_completed",
                "Canonical Replay 全输入预检完成",
                run_id=str(run.id),
                artifact_count=run.artifact_count,
                duration_ms=int((perf_counter() - preflight_started) * 1000),
            )

            shard_count = self._shard_count(run, selected, sampled_rows, matched_rows)
            if self.shard_coordinator is not None and shard_count >= 2:

                def finish() -> JobHandlerResult:
                    completed = self._finish_sharded_run(run.id, fence=fence)
                    log_event(
                        self._runtime.logger,
                        logging.INFO,
                        "canonical_replay.ingestion_completed",
                        "Canonical Replay 分片入库完成",
                        run_id=str(run.id),
                        shard_count=shard_count,
                        rows_seen=completed.rows_seen,
                        rows_ingested=completed.rows_ingested,
                        existing_convergence=completed.existing_convergence,
                    )
                    return JobHandlerResult.succeeded(_result(completed))

                return self.shard_coordinator.execute_parent(
                    kind="replay_run",
                    parent_id=run.id,
                    remaining_contents=shard_count,
                    fence=fence,
                    context=context,
                    finish=finish,
                )

            ingestion_started = perf_counter()
            phase = "ingestion"
            while run.checkpoint_artifact_ordinal < run.artifact_count:
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
                current = selected[run.checkpoint_artifact_ordinal]
                artifact_ordinal = current.ordinal
                try:
                    artifact = self._load_artifact(current, fence=fence)
                except RevokedCanonicalReplaySource:
                    run = self._advance_empty_artifact(run, current, fence=fence)
                    skipped_revoked_artifacts += 1
                    context.heartbeat(progress=_progress(run))
                    continue
                iterator = cast(
                    Generator[CanonicalContentV1],
                    reader.read_preflighted(artifact),
                )
                try:
                    for _ in islice(iterator, run.checkpoint_row_number):
                        pass
                    while True:
                        if context.cancel_requested():
                            return JobHandlerResult.cancelled()
                        resources = detect_resources()
                        if batch_tuner is None:
                            proposed_size, reason, previous = (
                                run.batch_size,
                                "frozen_single_row",
                                None,
                            )
                        else:
                            proposed_size, reason, previous = batch_tuner.choose(resources)
                        effective_size = proposed_size
                        if previous != proposed_size:
                            log_event(
                                self._runtime.logger,
                                logging.INFO,
                                "capacity.replay_batch_selected",
                                "历史重筛批量调整",
                                run_id=str(run.id),
                                previous_rows=(
                                    min(run.batch_size, previous) if previous is not None else None
                                ),
                                selected_rows=effective_size,
                                frozen_max_rows=run.batch_size,
                                reason=reason,
                            )
                        artifact_read_started = perf_counter()
                        batch = tuple(islice(iterator, effective_size))
                        batch_metrics["artifact_read_ms"] += int(
                            (perf_counter() - artifact_read_started) * 1000
                        )
                        if not batch:
                            run = self._advance_empty_artifact(run, current, fence=fence)
                            break
                        batch_started = perf_counter()
                        try:
                            run = self._ingest_batch(
                                run,
                                current,
                                artifact,
                                batch,
                                fence=fence,
                                batch_metrics=batch_metrics,
                            )
                        except RevokedCanonicalReplaySource:
                            run = self._advance_empty_artifact(run, current, fence=fence)
                            skipped_revoked_artifacts += 1
                            break
                        if batch_tuner is not None:
                            batch_tuner.succeeded(
                                size=proposed_size,
                                rows=len(batch),
                                duration_ms=int((perf_counter() - batch_started) * 1000),
                            )
                        context.heartbeat(progress=_progress(run))
                finally:
                    iterator.close()
                context.heartbeat(progress=_progress(run))
            log_event(
                self._runtime.logger,
                logging.INFO,
                "canonical_replay.ingestion_completed",
                "Canonical Replay 入库完成",
                run_id=str(run.id),
                duration_ms=int((perf_counter() - ingestion_started) * 1000),
                rows_seen=run.rows_seen,
                rows_matched=run.rows_matched,
                rows_ingested=run.rows_ingested,
                existing_convergence=run.existing_convergence,
                skipped_revoked_artifacts=skipped_revoked_artifacts,
                **batch_metrics,
            )
            return JobHandlerResult.succeeded(_result(run))
        except LeaseLostError:
            raise
        except CanonicalArtifactIntegrityError:
            return JobHandlerResult.failed("canonical_replay_artifact_invalid")
        except (LookupError, ValueError) as exc:
            log_event(
                self._runtime.logger,
                logging.ERROR,
                "canonical_replay.input_invalid",
                "Canonical Replay 输入已失效",
                job_id=str(fence.job_id),
                run_id=str(payload.run_id),
                phase=phase,
                artifact_ordinal=artifact_ordinal,
                error_class=type(exc).__name__,
            )
            return JobHandlerResult.failed("canonical_replay_input_invalid")
        except (DataError, IntegrityError, ProgrammingError) as exc:
            # 约束/SQL 结构错误重试不会自愈；只记录错误类别和 SQLSTATE，不泄露行内容。
            log_event(
                self._runtime.logger,
                logging.ERROR,
                "canonical_replay.persistence_invalid",
                "Canonical Replay 遇到不可重试的数据库错误",
                job_id=str(fence.job_id),
                error_class=type(exc).__name__,
                sqlstate=getattr(exc.orig, "sqlstate", None),
            )
            return JobHandlerResult.failed("canonical_replay_persistence_invalid")
        except OSError, SQLAlchemyError:
            if batch_tuner is not None:
                batch_tuner.database_retry()
            return JobHandlerResult.retry("canonical_replay_transient_error")

    def _load_execution(
        self,
        run_id: UUID,
        fence: JobExecutionFence,
        *,
        shard_id: UUID | None = None,
    ) -> tuple[CanonicalReplayRunRecord, tuple[CanonicalReplayArtifactRecord, ...]]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                run = repository.get(run_id)
                if run is None or (shard_id is None and run.job_id != fence.job_id):
                    raise LookupError("Canonical Replay Run 不属于当前 Job")
                if shard_id is not None:
                    shard = PostgresReplayShardRepository(session).get(shard_id)
                    if (
                        shard is None
                        or shard["run_id"] != run_id
                        or shard["job_id"] != fence.job_id
                    ):
                        raise LeaseLostError("Canonical Replay 分片不属于当前 Job")
                selected = repository.list_artifacts(run_id)
                if len(selected) != run.artifact_count or tuple(
                    item.ordinal for item in selected
                ) != tuple(range(run.artifact_count)):
                    raise ValueError("Canonical Replay 输入顺序不完整")
                return run, selected
        finally:
            session.close()

    def _shard_count(
        self,
        run: CanonicalReplayRunRecord,
        selected: tuple[CanonicalReplayArtifactRecord, ...],
        sampled_rows: int,
        matched_rows: int,
    ) -> int:
        session = self._runtime.database.new_session()
        try:
            existing = PostgresReplayShardRepository(session).list(run.id)
            if existing:
                return len(existing)
            if run.checkpoint_artifact_ordinal or run.checkpoint_row_number:
                return 1
            bytes_total = session.scalar(
                select(func.sum(artifacts_table.c.byte_size)).where(
                    artifacts_table.c.id.in_(tuple(item.artifact_id for item in selected))
                )
            )
            # 每片都会按原序重读输入；过多工作单元会让解析开销盖过并行收益。
            # 两片在单路起步后没有双路试档机会；直接串行可少读一次输入。
            # 更大的输入保留后续工作单元，供同一次运行中逐级试档。
            count = select_replay_shard_count(
                compressed_bytes=int(bytes_total or 0),
                available_workers=worker_process_limit(detect_resources()),
                sampled_rows=sampled_rows,
                matched_rows=matched_rows,
            )
            log_event(
                self._runtime.logger,
                logging.INFO,
                "capacity.replay_shard_plan_selected",
                "Replay 按预检样本和资源选择分片数",
                run_id=str(run.id),
                compressed_bytes=int(bytes_total or 0),
                sampled_rows=sampled_rows,
                matched_rows=matched_rows,
                selected_shards=count,
            )
            return count
        finally:
            session.close()

    def _finish_sharded_run(
        self, run_id: UUID, *, fence: JobExecutionFence
    ) -> CanonicalReplayRunRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                shards = PostgresReplayShardRepository(session).list(run_id)
                if not shards or any(item["status"] != "succeeded" for item in shards):
                    raise RuntimeError("Replay 子工作单元尚未全部完成")
                repository = PostgresCanonicalReplayRepository(session)
                run = repository.get(run_id)
                if run is None or run.job_id != fence.job_id:
                    raise LeaseLostError("Replay 父 Run 不属于当前 Job")
                for field in (
                    "rows_seen",
                    "rows_matched",
                    "rows_filtered_out",
                    "duplicates_removed",
                    "rows_ingested",
                    "existing_convergence",
                ):
                    if sum(int(item[field]) for item in shards) != getattr(run, field):
                        raise RuntimeError(f"Replay 分片与父 Run 的 {field} 计数不一致")
                return repository.advance(
                    run_id=run.id,
                    expected_artifact_ordinal=run.checkpoint_artifact_ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=run.artifact_count,
                    next_row_number=0,
                    counters=_zero_counters(),
                    fence=fence,
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
        """一个身份分片重读冻结输入，但只提交自己负责的内容，保持原始顺序。"""

        session = self._runtime.database.new_session()
        try:
            shard = PostgresReplayShardRepository(session).get(shard_id)
            if shard is None:
                raise LookupError("Replay 分片不存在")
            run_id = cast(UUID, shard["run_id"])
        finally:
            session.close()
        run, selected = self._load_execution(run_id, fence, shard_id=shard_id)
        run = replace(
            run,
            checkpoint_artifact_ordinal=int(shard["checkpoint_artifact_ordinal"]),
            checkpoint_row_number=int(shard["checkpoint_row_number"]),
        )
        ordinal = int(shard["ordinal"])
        shard_count = int(shard["shard_count"])
        reader = CanonicalArtifactReader(store=self._runtime.artifact_store)
        metrics = {
            "batch_count": 0,
            "artifact_read_ms": 0,
            "batch_elapsed_ms": 0,
            "resolution_ms": 0,
            "content_batch_ms": 0,
            "evidence_batch_ms": 0,
            "fallback_ms": 0,
            "fallback_snapshot_ms": 0,
            "fallback_content_ms": 0,
            "fallback_evidence_ms": 0,
            "fallback_ledger_ms": 0,
            "scalar_fallback_count": 0,
            "ledger_checkpoint_ms": 0,
            "transaction_ms": 0,
            "fast_created_count": 0,
            "fallback_count": 0,
        }
        while run.checkpoint_artifact_ordinal < run.artifact_count:
            if context.cancel_requested():
                raise LeaseLostError("Replay 分片已取消")
            current = selected[run.checkpoint_artifact_ordinal]
            try:
                artifact = self._load_artifact(current, fence=fence)
            except RevokedCanonicalReplaySource:
                run = self._advance_empty_artifact(run, current, fence=fence, shard_id=shard_id)
                continue
            # 子 Worker 持有独立 Reader；先逐字节核验冻结 Artifact，再复用父 Attempt
            # 已完成的来源/Contract 全量预检，不能把跨进程资格当成本地 Reader 状态。
            reader.verify_bytes_for_preflight(artifact)
            iterator = cast(Generator[CanonicalContentV1], reader.read_preflighted(artifact))
            try:
                for _ in islice(iterator, run.checkpoint_row_number):
                    pass
                while True:
                    if context.cancel_requested():
                        raise LeaseLostError("Replay 分片已取消")
                    raw_batch = tuple(islice(iterator, run.batch_size))
                    if not raw_batch:
                        run = self._advance_empty_artifact(
                            run, current, fence=fence, shard_id=shard_id
                        )
                        break
                    owned = tuple(
                        content
                        for content in raw_batch
                        if _identity_shard(content, shard_count) == ordinal
                    )
                    if owned:
                        try:
                            run = self._ingest_batch(
                                run,
                                current,
                                artifact,
                                owned,
                                fence=fence,
                                batch_metrics=metrics,
                                shard_id=shard_id,
                                raw_row_count=len(raw_batch),
                            )
                        except RevokedCanonicalReplaySource:
                            run = self._advance_empty_artifact(
                                run, current, fence=fence, shard_id=shard_id
                            )
                            break
                    else:
                        run = self._advance_filtered_batch(
                            run, current, len(raw_batch), fence=fence, shard_id=shard_id
                        )
                    context.heartbeat(progress=_progress(run))
            finally:
                iterator.close()
        session = self._runtime.database.new_session()
        try:
            completed = PostgresReplayShardRepository(session).get(shard_id)
            if completed is None or completed["status"] != "succeeded":
                raise RuntimeError("Replay 分片断点未到终点")
            return int(completed["rows_seen"])
        finally:
            session.close()

    def _load_artifact(
        self,
        selected: CanonicalReplayArtifactRecord,
        *,
        fence: JobExecutionFence,
    ) -> ArtifactRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                if repository.classify_artifact(selected.artifact_id) != selected.source_kind:
                    raise ValueError("Canonical Replay 输入来源类型发生漂移")
                artifact = repository.load_artifact(selected.artifact_id)
                if artifact is None:
                    raise LookupError("Canonical Replay Artifact 不存在")
                return artifact
        finally:
            session.close()

    def _preflight_all(
        self,
        selected: tuple[CanonicalReplayArtifactRecord, ...],
        *,
        run: CanonicalReplayRunRecord,
        reader: CanonicalArtifactReader,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> tuple[bool, int, int]:
        """在首个 Content 写入前验证全部字节、Contract 与逐行来源。"""

        resolver = BrandVehicleResolver(run.filter_snapshot.catalog)
        sampled_rows = 0
        matched_rows = 0
        for item in selected:
            try:
                artifact = self._load_artifact(item, fence=fence)
                proof = self._check_parent_and_load_validation_proof(item, artifact, fence=fence)
            except RevokedCanonicalReplaySource:
                continue
            if proof is not None:
                reader.verify_bytes_for_preflight(artifact)
                self._validate_source_rows(item, (), fence=fence, source_expectations=proof)
                if sampled_rows < _PROVEN_SAMPLE_ROWS_LIMIT:
                    iterator = cast(
                        Generator[CanonicalContentV1], reader.read_preflighted(artifact)
                    )
                    try:
                        sample = tuple(
                            islice(
                                iterator,
                                min(
                                    _SHARD_SAMPLE_ROWS_PER_ARTIFACT,
                                    _PROVEN_SAMPLE_ROWS_LIMIT - sampled_rows,
                                ),
                            )
                        )
                    finally:
                        iterator.close()
                    for content in sample:
                        sampled_rows += 1
                        matched_rows += int(
                            resolve_canonical_brand_vehicle(
                                run.filter_snapshot, content, resolver=resolver
                            ).matched
                        )
                if context.cancel_requested():
                    return False, sampled_rows, matched_rows
                continue
            expectations: dict[UUID, tuple[UUID, UUID, str, str]] = {}
            cacheable = True
            sampled_from_artifact = 0
            iterator = cast(
                Generator[CanonicalContentV1],
                reader.read_for_preflight(artifact),
            )
            try:
                while True:
                    batch = tuple(islice(iterator, _PREFLIGHT_BATCH_SIZE))
                    if not batch:
                        break
                    batch_expectations = self._validate_source_rows(item, batch, fence=fence)
                    sample = batch[
                        : max(0, _SHARD_SAMPLE_ROWS_PER_ARTIFACT - sampled_from_artifact)
                    ]
                    for content in sample:
                        sampled_rows += 1
                        matched_rows += int(
                            resolve_canonical_brand_vehicle(
                                run.filter_snapshot, content, resolver=resolver
                            ).matched
                        )
                    sampled_from_artifact += len(sample)
                    if cacheable:
                        for attempt_id, lineage in batch_expectations.items():
                            previous = expectations.setdefault(attempt_id, lineage)
                            if previous != lineage:
                                raise ValueError("同一 Canonical 文件的 Attempt 跨批来源不一致")
                        if len(expectations) > _MAX_PROOF_SOURCE_EXPECTATIONS:
                            expectations.clear()
                            cacheable = False
                    if context.cancel_requested():
                        return False, sampled_rows, matched_rows
            finally:
                iterator.close()
            if cacheable:
                self._save_validation_proof(item, artifact, expectations, fence=fence)
        return True, sampled_rows, matched_rows

    def _check_parent_and_load_validation_proof(
        self,
        selected: CanonicalReplayArtifactRecord,
        artifact: ArtifactRecord,
        *,
        fence: JobExecutionFence,
    ) -> dict[UUID, tuple[UUID, UUID, str, str]] | None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                if selected.source_kind != "tikhub_search_attempt_v1":
                    self._load_import_lineage_context(session, selected, artifact)
                proof = PostgresCanonicalReplayRepository(session).get_validation_proof(artifact.id)
                if (
                    proof is None
                    or proof["sha256"] != artifact.sha256
                    or proof["byte_size"] != artifact.byte_size
                    or proof["validation_version"] != _VALIDATION_VERSION
                    or proof["source_kind"] != selected.source_kind
                ):
                    return None
                raw = proof["source_expectations"]
                if not isinstance(raw, list) or len(raw) > _MAX_PROOF_SOURCE_EXPECTATIONS:
                    return None
                try:
                    return {
                        UUID(item["attempt_id"]): (
                            UUID(item["request_id"]),
                            UUID(item["raw_id"]),
                            item["platform"],
                            item["operation"],
                        )
                        for item in raw
                    }
                except KeyError, TypeError, ValueError:
                    return None
        finally:
            session.close()

    def _save_validation_proof(
        self,
        selected: CanonicalReplayArtifactRecord,
        artifact: ArtifactRecord,
        expectations: dict[UUID, tuple[UUID, UUID, str, str]],
        *,
        fence: JobExecutionFence,
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                PostgresCanonicalReplayRepository(session).save_validation_proof(
                    artifact=artifact,
                    validation_version=_VALIDATION_VERSION,
                    source_kind=selected.source_kind,
                    source_expectations=[
                        {
                            "attempt_id": str(attempt_id),
                            "request_id": str(value[0]),
                            "raw_id": str(value[1]),
                            "platform": value[2],
                            "operation": value[3],
                        }
                        for attempt_id, value in sorted(expectations.items())
                    ],
                )
        finally:
            session.close()

    def _validate_source_rows(
        self,
        selected: CanonicalReplayArtifactRecord,
        contents: tuple[CanonicalContentV1, ...],
        *,
        fence: JobExecutionFence,
        source_expectations: dict[UUID, tuple[UUID, UUID, str, str]] | None = None,
    ) -> dict[UUID, tuple[UUID, UUID, str, str]]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                if selected.source_kind in {
                    "excel_import_v2",
                    "data_import_canonical_chunk_v2",
                }:
                    for content in contents:
                        source = content.source
                        if (
                            source.provider_name != "imports"
                            or source.operation != "excel_import"
                            or source.provider_request_id is not None
                            or source.provider_attempt_id is not None
                            or source.raw_artifact_id is not None
                        ):
                            raise ValueError("Import Canonical Source 不符合当前持久格式")
                    return {}

                parent = session.execute(
                    select(collection_scopes_table.c.run_id)
                    .select_from(
                        canonical_artifact_links_table.join(
                            provider_request_attempts_table,
                            canonical_artifact_links_table.c.provider_attempt_id
                            == provider_request_attempts_table.c.id,
                        )
                        .join(
                            provider_requests_table,
                            provider_request_attempts_table.c.provider_request_id
                            == provider_requests_table.c.id,
                        )
                        .join(
                            collection_scopes_table,
                            provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                        )
                    )
                    .where(canonical_artifact_links_table.c.artifact_id == selected.artifact_id)
                    .add_columns(collection_scopes_table.c.id)
                ).one_or_none()
                if parent is None:
                    raise ValueError("TikHub Canonical 缺少父级 Collection Scope/Run")
                parent_run_id = cast(UUID, parent.run_id)
                parent_scope_id = cast(UUID, parent.id)
                expected = dict(source_expectations or {})
                if source_expectations is None:
                    for content in contents:
                        source = content.source
                        if (
                            source.provider_name != "tikhub"
                            or source.operation is None
                            or source.provider_request_id is None
                            or source.provider_attempt_id is None
                            or source.raw_artifact_id is None
                        ):
                            raise ValueError("TikHub Canonical Source 缺少 Request/Attempt/Raw")
                        try:
                            request_id = UUID(source.provider_request_id)
                            attempt_id = UUID(source.provider_attempt_id)
                        except ValueError as exc:
                            raise ValueError("TikHub Canonical Request/Attempt 不是 UUID") from exc
                        lineage = (
                            request_id,
                            source.raw_artifact_id,
                            content.platform,
                            source.operation,
                        )
                        previous = expected.setdefault(attempt_id, lineage)
                        if previous != lineage:
                            raise ValueError("同一 TikHub Attempt 的行级来源不一致")
                attempt_ids = set(expected)
                rows = session.execute(
                    select(
                        provider_request_attempts_table.c.id,
                        provider_request_attempts_table.c.provider_request_id,
                        provider_request_attempts_table.c.raw_artifact_id,
                        provider_requests_table.c.scope_id,
                        collection_scopes_table.c.platform,
                        provider_requests_table.c.operation,
                        collection_scopes_table.c.run_id,
                    )
                    .join(
                        provider_requests_table,
                        provider_request_attempts_table.c.provider_request_id
                        == provider_requests_table.c.id,
                    )
                    .join(
                        collection_scopes_table,
                        provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                    )
                    .where(
                        provider_request_attempts_table.c.id.in_(attempt_ids),
                        provider_request_attempts_table.c.dispatch_status == "completed",
                        provider_request_attempts_table.c.raw_artifact_id.is_not(None),
                        provider_requests_table.c.provider == "tikhub",
                    )
                )
                actual = {
                    cast(UUID, row.id): (
                        cast(UUID, row.provider_request_id),
                        cast(UUID, row.raw_artifact_id),
                        cast(UUID, row.scope_id),
                        cast(UUID, row.run_id),
                        cast(str, row.platform),
                        cast(str, row.operation),
                    )
                    for row in rows
                }
                if set(actual) != attempt_ids or any(
                    actual[item]
                    != (
                        expected[item][0],
                        expected[item][1],
                        parent_scope_id,
                        parent_run_id,
                        expected[item][2],
                        expected[item][3],
                    )
                    for item in attempt_ids
                ):
                    raise ValueError(
                        "TikHub Canonical 行级来源不属于父级 Scope 或与 Request/Attempt/Raw 不一致"
                    )
                return expected
        finally:
            session.close()

    def _advance_empty_artifact(
        self,
        run: CanonicalReplayRunRecord,
        selected: CanonicalReplayArtifactRecord,
        *,
        fence: JobExecutionFence,
        shard_id: UUID | None = None,
    ) -> CanonicalReplayRunRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                if shard_id is not None:
                    return PostgresReplayShardRepository(session).advance(
                        shard_id=shard_id,
                        run_id=run.id,
                        expected_artifact_ordinal=selected.ordinal,
                        expected_row_number=run.checkpoint_row_number,
                        next_artifact_ordinal=selected.ordinal + 1,
                        next_row_number=0,
                        counters=_zero_counters(),
                        fence=fence,
                        finished=selected.ordinal + 1 == run.artifact_count,
                    )
                return PostgresCanonicalReplayRepository(session).advance(
                    run_id=run.id,
                    expected_artifact_ordinal=selected.ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=selected.ordinal + 1,
                    next_row_number=0,
                    counters=_zero_counters(),
                    fence=fence,
                )
        finally:
            session.close()

    def _advance_filtered_batch(
        self,
        run: CanonicalReplayRunRecord,
        selected: CanonicalReplayArtifactRecord,
        raw_row_count: int,
        *,
        fence: JobExecutionFence,
        shard_id: UUID,
    ) -> CanonicalReplayRunRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return PostgresReplayShardRepository(session).advance(
                    shard_id=shard_id,
                    run_id=run.id,
                    expected_artifact_ordinal=selected.ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=selected.ordinal,
                    next_row_number=run.checkpoint_row_number + raw_row_count,
                    counters=_zero_counters(),
                    fence=fence,
                    finished=False,
                )
        finally:
            session.close()

    def _ingest_batch(
        self,
        run: CanonicalReplayRunRecord,
        selected: CanonicalReplayArtifactRecord,
        artifact: ArtifactRecord,
        contents: tuple[CanonicalContentV1, ...],
        *,
        fence: JobExecutionFence,
        batch_metrics: dict[str, int],
        shard_id: UUID | None = None,
        raw_row_count: int | None = None,
    ) -> CanonicalReplayRunRecord:
        batch_started = perf_counter()
        resolution_started = perf_counter()
        resolver = BrandVehicleResolver(run.filter_snapshot.catalog)
        resolved = tuple(
            (
                content,
                resolve_canonical_brand_vehicle(
                    run.filter_snapshot,
                    content,
                    resolver=resolver,
                ),
            )
            for content in contents
        )
        resolution_ms = int((perf_counter() - resolution_started) * 1000)
        session = self._runtime.database.new_session()
        advanced: CanonicalReplayRunRecord | None = None
        fast_created_count = 0
        fallback_count = 0
        stable_author_count = 0
        batched_remainder_count = 0
        scalar_fallback_count = 0
        content_batch_ms = 0
        evidence_batch_ms = 0
        fallback_ms = 0
        fallback_snapshot_ms = 0
        fallback_content_ms = 0
        fallback_evidence_ms = 0
        fallback_ledger_ms = 0
        ledger_checkpoint_ms = 0
        projection_refresh_ms = 0
        projection_content_count = 0
        transaction_started = perf_counter()
        try:
            with session.begin():
                # 这里只做无锁资格检查；提交前由 repository.advance 获取 Job 行锁并
                # 再次验证 Fence。取消/接管可在长批次中写入状态，旧事务随后整体回滚。
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                shard = (
                    PostgresReplayShardRepository(session).assert_owner(shard_id, fence)
                    if shard_id is not None
                    else None
                )
                current = repository.get(run.id, for_update=shard is None)
                if (
                    current is None
                    or (
                        shard is None
                        and (
                            current.job_id != fence.job_id
                            or current.checkpoint_artifact_ordinal != selected.ordinal
                            or current.checkpoint_row_number != run.checkpoint_row_number
                        )
                    )
                    or (
                        shard is not None
                        and (
                            shard["run_id"] != run.id
                            or shard["checkpoint_artifact_ordinal"] != selected.ordinal
                            or shard["checkpoint_row_number"] != run.checkpoint_row_number
                        )
                    )
                ):
                    raise LeaseLostError("Canonical Replay checkpoint 已不属于当前执行")
                lineage = self._load_import_lineage_context(session, selected, artifact)
                content_repository = PostgresCompleteContentRepository(
                    session,
                    replay_visibility_owner_id=current.all_request_id,
                )
                content_owner = ContentIngestionService(content_repository)
                vehicle_repository = PostgresVehicleCatalogRepository(session)
                brand_repository = PostgresBrandVehicleRepository(session)
                matched = 0
                duplicates = 0
                inserted = 0
                existing = 0
                lineage_by_platform: dict[str, tuple[UUID, UUID]] = {}
                ledger_rows: list[dict[str, object]] = []
                pending: list[tuple[CanonicalContentV1, BrandVehicleResolution]] = []
                claimed_identities = repository.claim_content_identities(
                    run_id=run.id,
                    identities=(
                        (content.platform, content.external_content_id)
                        for content, resolution in resolved
                        if resolution.matched
                    ),
                )
                for content, resolution in resolved:
                    if not resolution.matched:
                        continue
                    matched += 1
                    identity = (content.platform, content.external_content_id)
                    if identity not in claimed_identities:
                        duplicates += 1
                        continue
                    claimed_identities.remove(identity)
                    observation = self._content_with_lineage(
                        session,
                        content,
                        selected=selected,
                        lineage=lineage,
                        lineage_by_platform=lineage_by_platform,
                    )
                    pending.append((observation, resolution))

                defer_voice_plaza_projection(session)
                content_batch_started = perf_counter()
                fast_observations = tuple(
                    observation
                    for observation, _resolution in pending
                    if observation.author is None or observation.author.external_account_id is None
                )
                batch_created: tuple[PostgresCompleteNewContentBatchItem, ...] = (
                    content_owner.ingest_new_contents_batch(fast_observations)
                )
                content_batch_ms = int((perf_counter() - content_batch_started) * 1000)
                fast_created_count = len(batch_created)
                inserted += fast_created_count
                created_by_identity = {
                    (
                        item.observation.platform,
                        item.observation.external_content_id,
                    ): item
                    for item in batch_created
                }
                resolution_by_identity = {
                    (observation.platform, observation.external_content_id): resolution
                    for observation, resolution in pending
                }

                evidence_batch_started = perf_counter()
                evidence_created_at = beijing_now()
                vehicle_entries: list[tuple[UUID, int, tuple[ContentVehicleEvidence, ...]]] = []
                brand_entries = []
                for identity, item in created_by_identity.items():
                    resolution = resolution_by_identity[identity]
                    vehicle_entries.append(
                        (
                            item.result.target_id,
                            item.result.version_no,
                            tuple(
                                ContentVehicleEvidence(
                                    id=uuid4(),
                                    content_id=item.result.target_id,
                                    content_version=item.result.version_no,
                                    vehicle_model_id=evidence.entity_id,
                                    source="alias_match",
                                    matched_text=evidence.matched_text,
                                    source_field=evidence.source_field,
                                    catalog_version=resolution.catalog_version,
                                    confidence=1.0,
                                    is_manual_locked=False,
                                    is_active=True,
                                    created_at=evidence_created_at,
                                )
                                for evidence in resolution.vehicle_evidence
                            ),
                        )
                    )
                    brand_entries.append(
                        (
                            item.result.target_id,
                            item.result.version_no,
                            resolution.brand_evidence,
                        )
                    )
                vehicle_after_by_pair = (
                    vehicle_repository.append_initial_automatic_alias_evidence_batch(
                        entries=tuple(vehicle_entries)
                    )
                )
                brand_after_by_pair = (
                    brand_repository.append_initial_automatic_brand_evidence_batch(
                        entries=tuple(brand_entries),
                        catalog_snapshot=run.filter_snapshot.catalog,
                    )
                )
                evidence_batch_ms = int((perf_counter() - evidence_batch_started) * 1000)

                ledger_created_at = beijing_now()
                for item in batch_created:
                    observation = item.observation
                    attempt_id = observation.source.provider_attempt_id
                    raw_id = observation.source.raw_artifact_id
                    if attempt_id is None or raw_id is None:
                        raise ValueError("Replay 贡献账本要求 Attempt 与 Raw 来源")
                    if current.all_request_id is not None:
                        pair = (item.result.target_id, item.result.version_no)
                        ledger_rows.append(
                            {
                                "id": uuid4(),
                                "all_request_id": current.all_request_id,
                                "run_id": current.id,
                                "content_id": item.result.target_id,
                                "provider_attempt_id": UUID(attempt_id),
                                "raw_artifact_id": raw_id,
                                "version_before": None,
                                "version_after": item.result.version_no,
                                "delta": build_content_contribution_delta(
                                    observation,
                                    None,
                                    item.contribution_after,
                                ),
                                "visibility_owner_before": None,
                                "vehicle_evidence_before": [],
                                "vehicle_evidence_after": vehicle_after_by_pair[pair],
                                "brand_evidence_before": [],
                                "brand_evidence_after": brand_after_by_pair[pair],
                                "created_at": ledger_created_at,
                            }
                        )
                        if len(ledger_rows) >= _LEDGER_INSERT_ROWS:
                            self._flush_ledger_rows(session, ledger_rows)

                fallback_started = perf_counter()
                fallback_pending = tuple(
                    (observation, resolution)
                    for observation, resolution in pending
                    if (observation.platform, observation.external_content_id)
                    not in created_by_identity
                )
                fallback_count = len(fallback_pending)
                fallback_observations = tuple(item[0] for item in fallback_pending)
                stable_author_count = sum(
                    1
                    for observation in fallback_observations
                    if observation.author is not None
                    and observation.author.external_account_id is not None
                )
                fallback_snapshot_started = perf_counter()
                before_snapshots = capture_content_contribution_snapshots_batch(
                    session,
                    tuple((observation, None) for observation in fallback_observations),
                )
                before_pairs = tuple(
                    (before.content_id, before.version_no)
                    for before in before_snapshots
                    if before.content_id is not None and before.version_no is not None
                )
                owner_before_by_content = (
                    {
                        cast(UUID, row.id): cast(UUID | None, row.replay_visibility_owner_id)
                        for row in session.execute(
                            select(
                                contents_table.c.id,
                                contents_table.c.replay_visibility_owner_id,
                            ).where(
                                contents_table.c.id.in_(tuple(item[0] for item in before_pairs))
                            )
                        )
                    }
                    if before_pairs
                    else {}
                )
                vehicle_before_by_pair = vehicle_repository.snapshot_automatic_evidence_batch(
                    pairs=before_pairs
                )
                brand_before_by_pair = brand_repository.snapshot_automatic_brand_evidence_batch(
                    pairs=before_pairs
                )
                fallback_snapshot_ms = int((perf_counter() - fallback_snapshot_started) * 1000)
                fallback_content_started = perf_counter()
                fallback_items = content_repository.ingest_contents_with_before_snapshots_batch(
                    tuple(zip(fallback_observations, before_snapshots, strict=True))
                )
                fallback_content_ms = int((perf_counter() - fallback_content_started) * 1000)
                scalar_fallback_count = sum(
                    1 for item in fallback_items if item.used_scalar_fallback
                )
                batched_remainder_count = fallback_count - scalar_fallback_count
                fallback_evidence_started = perf_counter()
                fallback_vehicle_entries = []
                fallback_brand_entries = []
                evidence_created_at = beijing_now()
                for fallback_item, (_, resolution) in zip(
                    fallback_items,
                    fallback_pending,
                    strict=True,
                ):
                    result = fallback_item.result
                    fallback_vehicle_entries.append(
                        (
                            result.target_id,
                            result.version_no,
                            tuple(
                                ContentVehicleEvidence(
                                    id=uuid4(),
                                    content_id=result.target_id,
                                    content_version=result.version_no,
                                    vehicle_model_id=evidence.entity_id,
                                    source="alias_match",
                                    matched_text=evidence.matched_text,
                                    source_field=evidence.source_field,
                                    catalog_version=resolution.catalog_version,
                                    confidence=1.0,
                                    is_manual_locked=False,
                                    is_active=True,
                                    created_at=evidence_created_at,
                                )
                                for evidence in resolution.vehicle_evidence
                            ),
                        )
                    )
                    fallback_brand_entries.append(
                        (result.target_id, result.version_no, resolution.brand_evidence)
                    )
                selected_scope = run.filter_snapshot.catalog.filter_scope == "selected"
                if selected_scope:
                    vehicle_repository.append_automatic_alias_evidence_batch(
                        tuple(
                            item for _, _, evidence in fallback_vehicle_entries for item in evidence
                        )
                    )
                else:
                    vehicle_repository.replace_automatic_alias_evidence_batch(
                        entries=tuple(fallback_vehicle_entries)
                    )
                brand_repository.replace_automatic_brand_evidence_batch(
                    entries=tuple(fallback_brand_entries),
                    catalog_snapshot=run.filter_snapshot.catalog,
                    preserve_unconfirmed=selected_scope,
                )
                after_pairs = tuple(
                    (item.result.target_id, item.result.version_no) for item in fallback_items
                )
                vehicle_after_by_pair = vehicle_repository.snapshot_automatic_evidence_batch(
                    pairs=after_pairs
                )
                brand_after_by_pair = brand_repository.snapshot_automatic_brand_evidence_batch(
                    pairs=after_pairs
                )
                fallback_evidence_ms = int((perf_counter() - fallback_evidence_started) * 1000)
                fallback_ledger_started = perf_counter()
                for fallback_item in fallback_items:
                    observation = fallback_item.observation
                    before = fallback_item.before
                    result = fallback_item.result
                    if result.version_created and result.version_no == 1:
                        inserted += 1
                    else:
                        existing += 1
                    if current.all_request_id is None:
                        continue
                    attempt_id = observation.source.provider_attempt_id
                    raw_id = observation.source.raw_artifact_id
                    if attempt_id is None or raw_id is None:
                        raise ValueError("Replay 贡献账本要求 Attempt 与 Raw 来源")
                    before_pair = (
                        (before.content_id, before.version_no)
                        if before.content_id is not None and before.version_no is not None
                        else None
                    )
                    after_pair = (result.target_id, result.version_no)
                    ledger_rows.append(
                        {
                            "id": uuid4(),
                            "all_request_id": current.all_request_id,
                            "run_id": current.id,
                            "content_id": result.target_id,
                            "provider_attempt_id": UUID(attempt_id),
                            "raw_artifact_id": raw_id,
                            "version_before": before.version_no,
                            "version_after": result.version_no,
                            "delta": build_content_contribution_delta(
                                observation,
                                before,
                                fallback_item.contribution_after,
                            ),
                            "visibility_owner_before": (
                                owner_before_by_content.get(before.content_id)
                                if before.content_id is not None
                                else None
                            ),
                            "vehicle_evidence_before": (
                                vehicle_before_by_pair[before_pair]
                                if before_pair is not None
                                else []
                            ),
                            "vehicle_evidence_after": vehicle_after_by_pair[after_pair],
                            "brand_evidence_before": (
                                brand_before_by_pair[before_pair] if before_pair is not None else []
                            ),
                            "brand_evidence_after": brand_after_by_pair[after_pair],
                            "created_at": beijing_now(),
                        }
                    )
                    if len(ledger_rows) >= _LEDGER_INSERT_ROWS:
                        self._flush_ledger_rows(session, ledger_rows)
                fallback_ledger_ms = int((perf_counter() - fallback_ledger_started) * 1000)
                fallback_ms = int((perf_counter() - fallback_started) * 1000)
                ledger_checkpoint_started = perf_counter()
                self._flush_ledger_rows(session, ledger_rows)
                counters = CanonicalReplayCounters(
                    rows_seen=len(contents),
                    rows_matched=matched,
                    rows_filtered_out=len(contents) - matched,
                    duplicates_removed=duplicates,
                    rows_ingested=inserted,
                    existing_convergence=existing,
                )
                next_row = run.checkpoint_row_number + (
                    raw_row_count if raw_row_count is not None else len(contents)
                )
                if shard_id is None:
                    advanced = repository.advance(
                        run_id=run.id,
                        expected_artifact_ordinal=selected.ordinal,
                        expected_row_number=run.checkpoint_row_number,
                        next_artifact_ordinal=selected.ordinal,
                        next_row_number=next_row,
                        counters=counters,
                        fence=fence,
                    )
                else:
                    advanced = PostgresReplayShardRepository(session).advance(
                        shard_id=shard_id,
                        run_id=run.id,
                        expected_artifact_ordinal=selected.ordinal,
                        expected_row_number=run.checkpoint_row_number,
                        next_artifact_ordinal=selected.ordinal,
                        next_row_number=next_row,
                        counters=counters,
                        fence=fence,
                        finished=False,
                    )
                ledger_checkpoint_ms = int((perf_counter() - ledger_checkpoint_started) * 1000)
                projection_started = perf_counter()
                projection_content_count = flush_deferred_voice_plaza_projection(
                    session,
                    tuple(item.result.target_id for item in batch_created)
                    + tuple(item.result.target_id for item in fallback_items),
                )
                projection_refresh_ms = int((perf_counter() - projection_started) * 1000)
        finally:
            session.close()
        if advanced is None:
            raise RuntimeError("Canonical Replay 批次提交后缺少 checkpoint")
        log_event(
            self._runtime.logger,
            logging.DEBUG,
            "canonical_replay.batch_completed",
            "Canonical Replay 批次已原子提交",
            run_id=str(run.id),
            artifact_ordinal=selected.ordinal,
            row_start=run.checkpoint_row_number,
            row_count=len(contents),
            raw_row_count=raw_row_count if raw_row_count is not None else len(contents),
            matched_count=matched,
            fast_created_count=fast_created_count,
            fallback_count=fallback_count,
            stable_author_count=stable_author_count,
            batched_remainder_count=batched_remainder_count,
            scalar_fallback_count=scalar_fallback_count,
            resolution_ms=resolution_ms,
            content_batch_ms=content_batch_ms,
            evidence_batch_ms=evidence_batch_ms,
            fallback_ms=fallback_ms,
            fallback_snapshot_ms=fallback_snapshot_ms,
            fallback_content_ms=fallback_content_ms,
            fallback_evidence_ms=fallback_evidence_ms,
            fallback_ledger_ms=fallback_ledger_ms,
            ledger_checkpoint_ms=ledger_checkpoint_ms,
            projection_content_count=projection_content_count,
            projection_refresh_ms=projection_refresh_ms,
            transaction_ms=int((perf_counter() - transaction_started) * 1000),
            duration_ms=int((perf_counter() - batch_started) * 1000),
        )
        batch_metrics["batch_count"] += 1
        batch_metrics["batch_elapsed_ms"] += int((perf_counter() - batch_started) * 1000)
        batch_metrics["resolution_ms"] += resolution_ms
        batch_metrics["content_batch_ms"] += content_batch_ms
        batch_metrics["evidence_batch_ms"] += evidence_batch_ms
        batch_metrics["fallback_ms"] += fallback_ms
        batch_metrics["fallback_snapshot_ms"] += fallback_snapshot_ms
        batch_metrics["fallback_content_ms"] += fallback_content_ms
        batch_metrics["fallback_evidence_ms"] += fallback_evidence_ms
        batch_metrics["fallback_ledger_ms"] += fallback_ledger_ms
        batch_metrics["scalar_fallback_count"] += scalar_fallback_count
        batch_metrics["ledger_checkpoint_ms"] += ledger_checkpoint_ms
        batch_metrics["transaction_ms"] += int((perf_counter() - transaction_started) * 1000)
        batch_metrics["fast_created_count"] += fast_created_count
        batch_metrics["fallback_count"] += fallback_count
        return advanced

    @staticmethod
    def _flush_ledger_rows(session: Session, rows: list[dict[str, object]]) -> None:
        """账本 SQL 合批但保持有界内存，所有片段仍属于同一 checkpoint 事务。"""

        if rows:
            session.execute(insert(canonical_replay_content_changes_table), rows)
            rows.clear()

    def _load_import_lineage_context(
        self,
        session: Session,
        selected: CanonicalReplayArtifactRecord,
        artifact: ArtifactRecord,
    ) -> _ImportLineageContext | None:
        if selected.source_kind == "tikhub_search_attempt_v1":
            return None
        if selected.source_kind == "excel_import_v2":
            row = session.execute(
                select(
                    processing_import_batches_table.c.id,
                    processing_import_batches_table.c.input_artifact_id,
                )
                .join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.processing_import_batch_id
                    == processing_import_batches_table.c.id,
                )
                .where(canonical_artifact_links_table.c.artifact_id == artifact.id)
            ).one_or_none()
            if row is None:
                raise ValueError("Excel Canonical 缺少 Import Batch")
            raw = PostgresArtifactMetadataRepository(session).get(cast(UUID, row.input_artifact_id))
            if raw is None or raw.storage_status != "linked":
                raise ValueError("Excel Input Artifact 不可用")
            return _ImportLineageContext(cast(UUID, row.id), raw, "excel_import")

        chunk = session.execute(
            select(
                historical_import_campaign_items_table.c.parent_item_id,
                jobs_table.c.payload,
                historical_import_campaigns_table.c.status,
            )
            .select_from(
                canonical_artifact_links_table.join(
                    historical_import_campaign_items_table,
                    canonical_artifact_links_table.c.historical_import_campaign_item_id
                    == historical_import_campaign_items_table.c.id,
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
            .where(canonical_artifact_links_table.c.artifact_id == artifact.id)
            .with_for_update(read=True, of=historical_import_campaigns_table)
        ).one_or_none()
        if chunk is None or chunk.parent_item_id is None:
            raise ValueError("Data Import Canonical 缺少 Chunk Job")
        if chunk.status in ("revoking", "revoked"):
            raise RevokedCanonicalReplaySource("Data Import 来源正在撤销或已撤销")
        payload = cast(dict[str, object], chunk.payload)
        try:
            batch_id = UUID(str(payload["batch_id"]))
        except (KeyError, ValueError) as exc:
            raise ValueError("Data Import Chunk Job 缺少有效 batch_id") from exc
        row = session.execute(
            select(
                processing_import_batches_table.c.id,
                processing_import_batches_table.c.historical_policy_version,
            ).where(
                processing_import_batches_table.c.id == batch_id,
                processing_import_batches_table.c.historical_campaign_item_id
                == chunk.parent_item_id,
            )
        ).one_or_none()
        if row is None:
            raise ValueError("Data Import Canonical 缺少当前 Processing Batch")
        policy = cast(str | None, row.historical_policy_version)
        if policy == "historical-fill-only.v1":
            operation = "historical_excel_import"
        elif policy == "standard-observation.v1":
            operation = "excel_import"
        else:
            raise ValueError("Data Import Canonical 的写入策略已淘汰")
        return _ImportLineageContext(cast(UUID, row.id), artifact, operation)

    @staticmethod
    def _content_with_lineage(
        session: Session,
        content: CanonicalContentV1,
        *,
        selected: CanonicalReplayArtifactRecord,
        lineage: _ImportLineageContext | None,
        lineage_by_platform: dict[str, tuple[UUID, UUID]],
    ) -> CanonicalContentV1:
        if selected.source_kind == "tikhub_search_attempt_v1":
            return content
        if lineage is None:
            raise ValueError("Import Replay 缺少 lineage context")
        identifiers = lineage_by_platform.get(content.platform)
        if identifiers is None:
            if selected.source_kind == "excel_import_v2":
                identifiers = ensure_single_import_lineage(
                    session=session,
                    batch_id=lineage.batch_id,
                    platform=content.platform,
                    input_artifact=lineage.raw_artifact,
                    profile=content.source.source_type or "unknown",
                )
            else:
                identifiers = ensure_campaign_import_lineage(
                    session=session,
                    batch_id=lineage.batch_id,
                    platform=content.platform,
                    canonical_artifact=lineage.raw_artifact,
                    operation=lineage.operation,
                )
            lineage_by_platform[content.platform] = identifiers
        request_id, attempt_id = identifiers
        source = content.source.model_copy(
            update={
                "provider_name": "imports",
                "operation": lineage.operation,
                "provider_request_id": str(request_id),
                "provider_attempt_id": str(attempt_id),
                "raw_artifact_id": lineage.raw_artifact.id,
            }
        )
        return content.model_copy(update={"source": source})

    @staticmethod
    def _write_evidence(
        *,
        vehicle_repository: PostgresVehicleCatalogRepository,
        brand_repository: PostgresBrandVehicleRepository,
        content_id: UUID,
        content_version: int,
        resolution: BrandVehicleResolution,
        run: CanonicalReplayRunRecord,
    ) -> None:
        for item in resolution.vehicle_evidence:
            if item.source != "alias_match":
                raise ValueError("Replay 自动 Vehicle Evidence 只接受 alias_match")
            vehicle_repository.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=content_version,
                    vehicle_model_id=item.entity_id,
                    source="alias_match",
                    matched_text=item.matched_text,
                    source_field=item.source_field,
                    catalog_version=resolution.catalog_version,
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )
        brand_repository.merge_automatic_brand_evidence(
            content_id=content_id,
            content_version=content_version,
            evidence=resolution.brand_evidence,
            catalog_version=resolution.catalog_version,
            catalog_snapshot=run.filter_snapshot.catalog,
        )


def _zero_counters() -> CanonicalReplayCounters:
    return CanonicalReplayCounters(0, 0, 0, 0, 0, 0)


def _identity_shard(content: CanonicalContentV1, shard_count: int) -> int:
    """同一平台内容身份在所有 Artifact 中必须进入相同且有序的工作单元。"""

    identity = f"{content.platform}\0{content.external_content_id}".encode()
    digest = hashlib.blake2b(identity, digest_size=8).digest()
    return int.from_bytes(digest, "big") % shard_count


def _progress(run: CanonicalReplayRunRecord) -> int:
    if run.checkpoint_artifact_ordinal >= run.artifact_count:
        return 100
    return min(99, int(run.checkpoint_artifact_ordinal * 100 / run.artifact_count))


def _result(run: CanonicalReplayRunRecord) -> dict[str, object]:
    return {
        "run_id": str(run.id),
        "artifact_count": run.artifact_count,
        "rows_seen": run.rows_seen,
        "rows_matched": run.rows_matched,
        "rows_filtered_out": run.rows_filtered_out,
        "duplicates_removed": run.duplicates_removed,
        "rows_ingested": run.rows_ingested,
        "existing_convergence": run.existing_convergence,
        "invalid_artifact_rows": 0,
    }


__all__ = ["PostgresCanonicalReplayJobExecutor"]
