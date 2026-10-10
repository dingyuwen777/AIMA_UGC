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

from sqlalchemy import case, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.analysis_reuse import PostgresAnalysisReuseRepository
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.brand_vehicle_classification import (
    resolve_current_brand_vehicle_batch,
)
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
    RevokedCanonicalReplaySource,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
    PostgresCompleteNewContentBatchItem,
    PostgresContentClassificationInput,
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
from aima_ugc.adapters.persistence.postgres.workload_slots import (
    acquire_background_write_slot,
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
    AdaptiveTierBatchController,
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
_REPLAY_RESOURCE_GROWTH_ABSOLUTE_CEILING = 64_000
_REPLAY_LOCK_TIMEOUT = "3s"
_PARENT_CANCELLATION_CHECK_SECONDS = 1.0


class _ReplayParentCancellationProbe:
    """按时间节流读取父取消意图，供只有一个 Worker 时及时让出执行槽。"""

    def __init__(self, runtime: PlatformRuntime, request_id: UUID | None) -> None:
        self._runtime = runtime
        self._request_id = request_id
        self._next_check_at = 0.0
        self._cancelled = False

    def requested(self, context: JobExecutionContextProtocol) -> bool:
        if context.cancel_requested():
            return True
        if self._cancelled:
            return True
        if self._request_id is None or perf_counter() < self._next_check_at:
            return False
        self._next_check_at = perf_counter() + _PARENT_CANCELLATION_CHECK_SECONDS
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                self._cancelled = PostgresCanonicalReplayRepository(
                    session
                ).is_all_cancellation_requested(self._request_id)
                if self._cancelled:
                    # 父取消意图可以先于协调 Job 到达当前运行中的子 Job。这里同步写入
                    # 当前 Job 的取消位，让执行器停止与通用 Job 状态收敛保持同一事实。
                    PostgresJobRepository(session).request_cancel(context.fence.job_id)
            return self._cancelled
        finally:
            session.close()


def _replay_batch_tiers(
    max_rows: int,
    *,
    allow_resource_growth: bool = False,
) -> tuple[int, ...]:
    """从兼容提示生成逐级批量；全历史任务可继续按资源和实测收益升档。"""

    if max_rows < 1:
        raise ValueError("Replay 批量上限必须为正整数")
    candidates = [
        max(1, max_rows // 16),
        max(1, max_rows // 8),
        max(1, max_rows // 4),
        max(1, max_rows // 2),
        max_rows,
    ]
    if allow_resource_growth:
        candidate = max_rows * 2
        while candidate <= _REPLAY_RESOURCE_GROWTH_ABSOLUTE_CEILING:
            candidates.append(candidate)
            candidate *= 2
    return tuple(sorted(set(candidates)))


def _new_replay_batch_tuner(
    max_rows: int,
    *,
    allow_resource_growth: bool = False,
) -> AdaptiveTierBatchController | None:
    """父 Replay 与持久分片共用相同墙钟/资源反馈，不留下固定大批次旁路。"""

    tiers = _replay_batch_tiers(
        max_rows,
        allow_resource_growth=allow_resource_growth,
    )
    if len(tiers) == 1:
        return None
    # 历史任务可能保存了非常小的批量。先按原提示安全起步，再依靠吞吐探测
    # 逐级增长，避免固定下标把 1 行提示直接放大到 4 行。
    initial_target = max(1, max_rows // 4)
    initial_index = max(index for index, tier in enumerate(tiers) if tier <= initial_target)
    return AdaptiveTierBatchController(
        tiers=tiers,
        improvement_margin=0.08,
        transaction_ceiling_ms=3_000,
        rows_per_cpu_core=1_000,
        memory_mib_per_1000_rows=1_024,
        initial_index=initial_index,
    )


class _ReplayScanBatchController:
    """按实际命中率把 matched 事务目标换算成有界 raw 扫描窗口。"""

    def __init__(self, *, max_scan_rows: int, sampled_rows: int, matched_rows: int) -> None:
        if max_scan_rows < 1 or sampled_rows < 0 or not 0 <= matched_rows <= sampled_rows:
            raise ValueError("Replay 扫描批量参数无效")
        self.max_scan_rows = max_scan_rows
        self._hit_ratio = matched_rows / sampled_rows if sampled_rows else 1.0

    @property
    def estimated_hit_ratio(self) -> float:
        """返回仅用于批量决策和脱敏日志的当前命中率估计。"""

        return self._hit_ratio

    def choose(
        self,
        *,
        matched_target_rows: int,
        scan_ceiling_rows: int | None = None,
    ) -> int:
        """低命中时扩大只读扫描，但绝不超过冻结批量和当前资源给出的上界。"""

        if matched_target_rows < 1:
            raise ValueError("Replay matched target 必须为正整数")
        ceiling = self.max_scan_rows if scan_ceiling_rows is None else scan_ceiling_rows
        if ceiling < matched_target_rows or ceiling > self.max_scan_rows:
            raise ValueError("Replay scan ceiling 超出允许边界")
        if self._hit_ratio <= 0:
            return ceiling
        estimated = int(matched_target_rows / self._hit_ratio)
        if estimated * self._hit_ratio < matched_target_rows:
            estimated += 1
        return max(
            matched_target_rows,
            min(ceiling, estimated),
        )

    def observe(self, *, raw_rows: int, matched_rows: int) -> None:
        """用最近完整批次缓慢修正命中率，避免单个异常批次造成窗口震荡。"""

        if raw_rows < 1 or not 0 <= matched_rows <= raw_rows:
            raise ValueError("Replay 实际批次命中统计无效")
        observed = matched_rows / raw_rows
        self._hit_ratio = self._hit_ratio * 0.75 + observed * 0.25


def _partition_resolved_batch(
    resolved: tuple[tuple[CanonicalContentV1, BrandVehicleResolution], ...],
    *,
    matched_target_rows: int,
    raw_limit_rows: int | None = None,
) -> tuple[tuple[tuple[CanonicalContentV1, BrandVehicleResolution], ...], ...]:
    """把一次大扫描按命中数切成连续事务块，避免命中率突升制造超大数据库事务。"""

    if matched_target_rows < 1:
        raise ValueError("Replay matched target 必须为正整数")
    if raw_limit_rows is not None and raw_limit_rows < 1:
        raise ValueError("Replay raw limit 必须为正整数")
    if not resolved:
        return ()
    chunks: list[tuple[tuple[CanonicalContentV1, BrandVehicleResolution], ...]] = []
    start = 0
    matched = 0
    for index, (_content, resolution) in enumerate(resolved):
        if resolution.matched:
            matched += 1
        if matched >= matched_target_rows or (
            raw_limit_rows is not None and index + 1 - start >= raw_limit_rows
        ):
            chunks.append(resolved[start : index + 1])
            start = index + 1
            matched = 0
    if start < len(resolved):
        chunks.append(resolved[start:])
    return tuple(chunks)


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


@dataclass(frozen=True, slots=True)
class _ReplaySourceRecord:
    """跨 Artifact 聚合批次中一行 Canonical 对应的冻结来源。"""

    selected: CanonicalReplayArtifactRecord
    artifact: ArtifactRecord


class PostgresCanonicalReplayJobExecutor:
    """先预检完整输入集，再按有界批次和当前 Fence 幂等 Replay。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._current_resolver = BrandVehicleResolver()
        self.shard_coordinator: AdaptiveShardCoordinator | None = None

    def execute(
        self,
        *,
        payload: CanonicalReplayJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """接管先重新预检全部输入；随后从已提交 checkpoint 继续。"""

        batch_tuner: AdaptiveTierBatchController | None = None
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
            "workload_slot_wait_ms": 0,
            "foreground_pressure_batches": 0,
        }
        try:
            run, selected = self._load_execution(payload.run_id, fence)
            cancel_probe = _ReplayParentCancellationProbe(self._runtime, run.all_request_id)
            batch_tuner = _new_replay_batch_tuner(
                run.batch_size,
                allow_resource_growth=True,
            )
            if run.checkpoint_artifact_ordinal >= run.artifact_count:
                return JobHandlerResult.succeeded(_result(run))

            # 预检资格仅属于本次 Attempt；接管必须重新证明输入全集。
            reader = CanonicalArtifactReader(store=self._runtime.artifact_store)
            preflight_started = perf_counter()
            phase = "preflight"
            preflight_ok, sampled_rows, matched_rows = self._preflight_all(
                selected,
                run=run,
                reader=reader,
                fence=fence,
                context=context,
                cancel_probe=cancel_probe,
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

            adaptive_ceiling_rows = (
                batch_tuner.tiers[-1] if batch_tuner is not None else run.batch_size
            )
            scan_controller = _ReplayScanBatchController(
                max_scan_rows=max(adaptive_ceiling_rows, adaptive_ceiling_rows * 4),
                sampled_rows=sampled_rows,
                matched_rows=matched_rows,
            )
            resolver = BrandVehicleResolver(run.filter_snapshot.catalog)
            previous_scan_signature: tuple[int, int] | None = None
            ingestion_started = perf_counter()
            next_progress_log_at = ingestion_started + 60.0
            phase = "ingestion"
            cursor_ordinal = run.checkpoint_artifact_ordinal
            cursor_row_number = run.checkpoint_row_number
            iterator: Generator[CanonicalContentV1] | None = None
            iterator_selected: CanonicalReplayArtifactRecord | None = None
            iterator_artifact: ArtifactRecord | None = None
            try:
                while run.checkpoint_artifact_ordinal < run.artifact_count:
                    if cancel_probe.requested(context):
                        return JobHandlerResult.cancelled()
                    resources = detect_resources()
                    if batch_tuner is None:
                        matched_target, reason, previous = (
                            run.batch_size,
                            "frozen_single_row",
                            None,
                        )
                    else:
                        matched_target, reason, previous = batch_tuner.choose(resources)
                    if previous != matched_target:
                        log_event(
                            self._runtime.logger,
                            logging.INFO,
                            "capacity.replay_batch_selected",
                            "历史重筛数据库目标批量调整",
                            run_id=str(run.id),
                            previous_rows=previous,
                            selected_rows=matched_target,
                            configured_batch_hint=run.batch_size,
                            adaptive_ceiling_rows=adaptive_ceiling_rows,
                            unit="matched_rows",
                            reason=reason,
                        )
                    scan_ceiling_rows = min(
                        scan_controller.max_scan_rows,
                        max(matched_target, matched_target * 4),
                    )
                    scan_rows = scan_controller.choose(
                        matched_target_rows=matched_target,
                        scan_ceiling_rows=scan_ceiling_rows,
                    )
                    scan_signature = (matched_target, scan_rows)
                    if previous_scan_signature != scan_signature:
                        log_event(
                            self._runtime.logger,
                            logging.INFO,
                            "capacity.replay_scan_batch_selected",
                            "历史重筛按命中率调整扫描窗口",
                            run_id=str(run.id),
                            matched_target_rows=matched_target,
                            raw_scan_rows=scan_rows,
                            max_scan_rows=scan_controller.max_scan_rows,
                            resource_scan_ceiling_rows=scan_ceiling_rows,
                            estimated_hit_ratio=round(scan_controller.estimated_hit_ratio, 4),
                        )
                        previous_scan_signature = scan_signature

                    artifact_read_started = perf_counter()
                    batch: list[CanonicalContentV1] = []
                    source_records: list[_ReplaySourceRecord] = []
                    checkpoints: list[tuple[int, int]] = []
                    while len(batch) < scan_rows and cursor_ordinal < run.artifact_count:
                        candidate = selected[cursor_ordinal]
                        # 统一 Data Import 的 Canonical 本身已经是有界 Chunk，且 Campaign
                        # 允许并发撤销；不把它与相邻 Artifact 放进同一事务。兼容单文件
                        # 与 Provider Canonical 则可跨文件聚合，消除小文件事务放大。
                        if batch and (
                            candidate.source_kind == "data_import_canonical_chunk_v2"
                            or source_records[-1].selected.source_kind
                            == "data_import_canonical_chunk_v2"
                        ):
                            break
                        if iterator is None:
                            artifact_ordinal = candidate.ordinal
                            try:
                                loaded = self._load_artifact(candidate, fence=fence)
                            except RevokedCanonicalReplaySource:
                                if batch:
                                    break
                                run = self._advance_empty_artifact(run, candidate, fence=fence)
                                skipped_revoked_artifacts += 1
                                cursor_ordinal = run.checkpoint_artifact_ordinal
                                cursor_row_number = run.checkpoint_row_number
                                context.heartbeat(progress=_progress(run))
                                continue
                            iterator_selected = candidate
                            iterator_artifact = loaded
                            iterator = cast(
                                Generator[CanonicalContentV1],
                                reader.read_preflighted(loaded),
                            )
                            for _ in islice(iterator, cursor_row_number):
                                pass
                        if iterator_selected is None or iterator_artifact is None:
                            raise RuntimeError("Replay Artifact 读取游标未初始化")
                        remaining = scan_rows - len(batch)
                        rows = tuple(islice(iterator, remaining))
                        if not rows:
                            iterator.close()
                            iterator = None
                            iterator_selected = None
                            iterator_artifact = None
                            cursor_ordinal += 1
                            cursor_row_number = 0
                            continue
                        for content in rows:
                            cursor_row_number += 1
                            batch.append(content)
                            source_records.append(
                                _ReplaySourceRecord(
                                    selected=iterator_selected,
                                    artifact=iterator_artifact,
                                )
                            )
                            checkpoints.append((cursor_ordinal, cursor_row_number))
                    batch_metrics["artifact_read_ms"] += int(
                        (perf_counter() - artifact_read_started) * 1000
                    )
                    if not batch:
                        run = self._advance_checkpoint(
                            run,
                            next_artifact_ordinal=cursor_ordinal,
                            next_row_number=cursor_row_number,
                            fence=fence,
                        )
                        context.heartbeat(progress=_progress(run))
                        continue

                    resolution_started = perf_counter()
                    resolved = tuple(
                        (
                            content,
                            resolve_canonical_brand_vehicle(
                                run.filter_snapshot,
                                content,
                                resolver=resolver,
                            ),
                        )
                        for content in batch
                    )
                    resolution_ms = int((perf_counter() - resolution_started) * 1000)
                    actual_matched = sum(resolution.matched for _content, resolution in resolved)
                    if len(batch) == scan_rows:
                        scan_controller.observe(
                            raw_rows=len(batch),
                            matched_rows=actual_matched,
                        )
                    resolved_chunks = _partition_resolved_batch(
                        resolved,
                        matched_target_rows=matched_target,
                        raw_limit_rows=(
                            1000
                            if run.filter_snapshot.catalog.resolver_semantics
                            == "brand_scoped_vehicle_v2"
                            else None
                        ),
                    )
                    chunk_start = 0
                    revoked_during_batch = False
                    for chunk_index, resolved_chunk in enumerate(resolved_chunks):
                        if cancel_probe.requested(context):
                            return JobHandlerResult.cancelled()
                        chunk_end = chunk_start + len(resolved_chunk)
                        chunk_sources = tuple(source_records[chunk_start:chunk_end])
                        next_artifact_ordinal, next_row_number = checkpoints[chunk_end - 1]
                        transaction_contents = tuple(
                            content for content, _resolution in resolved_chunk
                        )
                        transaction_matched = sum(
                            resolution.matched for _content, resolution in resolved_chunk
                        )
                        batch_started = perf_counter()
                        try:
                            run = self._ingest_batch(
                                run,
                                chunk_sources[0].selected,
                                chunk_sources[0].artifact,
                                transaction_contents,
                                fence=fence,
                                batch_metrics=batch_metrics,
                                source_records=chunk_sources,
                                next_artifact_ordinal=next_artifact_ordinal,
                                next_row_number=next_row_number,
                                resolved=resolved_chunk,
                                resolution_ms=resolution_ms if chunk_index == 0 else 0,
                            )
                        except RevokedCanonicalReplaySource:
                            revoked = chunk_sources[0].selected
                            run = self._advance_empty_artifact(run, revoked, fence=fence)
                            skipped_revoked_artifacts += 1
                            if iterator is not None:
                                iterator.close()
                            iterator = None
                            iterator_selected = None
                            iterator_artifact = None
                            cursor_ordinal = run.checkpoint_artifact_ordinal
                            cursor_row_number = run.checkpoint_row_number
                            revoked_during_batch = True
                            break
                        if batch_tuner is not None:
                            batch_tuner.succeeded(
                                size=matched_target,
                                rows=transaction_matched,
                                duration_ms=int((perf_counter() - batch_started) * 1000),
                            )
                        chunk_start = chunk_end
                        context.heartbeat(progress=_progress(run))
                        now = perf_counter()
                        if now >= next_progress_log_at:
                            log_event(
                                self._runtime.logger,
                                logging.INFO,
                                "canonical_replay.progress_sample",
                                "Canonical Replay 周期进度与阶段耗时。",
                                job_id=str(fence.job_id),
                                run_id=str(run.id),
                                progress=_progress(run),
                                rows_seen=run.rows_seen,
                                rows_matched=run.rows_matched,
                                rows_ingested=run.rows_ingested,
                                existing_convergence=run.existing_convergence,
                                duration_ms=int((now - ingestion_started) * 1000),
                                **batch_metrics,
                            )
                            next_progress_log_at = now + 60.0
                    if revoked_during_batch:
                        continue
            finally:
                if iterator is not None:
                    iterator.close()
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
        except (OSError, SQLAlchemyError) as exc:
            log_event(
                self._runtime.logger,
                logging.WARNING,
                "canonical_replay.transient_retry",
                "Canonical Replay 遇到可重试的 I/O 或数据库异常。",
                job_id=str(fence.job_id),
                run_id=str(payload.run_id),
                phase=phase,
                artifact_ordinal=artifact_ordinal,
                error_class=type(exc).__name__,
                sqlstate=getattr(getattr(exc, "orig", None), "sqlstate", None),
                batch_metrics=batch_metrics,
            )
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
        batch_tuner = _new_replay_batch_tuner(
            run.batch_size,
            allow_resource_growth=True,
        )
        adaptive_ceiling_rows = batch_tuner.tiers[-1] if batch_tuner is not None else run.batch_size
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
            "workload_slot_wait_ms": 0,
            "foreground_pressure_batches": 0,
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
                    resources = detect_resources()
                    if batch_tuner is None:
                        proposed_size, reason, previous = (
                            run.batch_size,
                            "frozen_single_row",
                            None,
                        )
                    else:
                        proposed_size, reason, previous = batch_tuner.choose(resources)
                    if previous != proposed_size:
                        log_event(
                            self._runtime.logger,
                            logging.INFO,
                            "capacity.replay_shard_batch_selected",
                            "Replay 分片批量调整",
                            run_id=str(run.id),
                            shard_id=str(shard_id),
                            previous_rows=previous,
                            selected_rows=proposed_size,
                            configured_batch_hint=run.batch_size,
                            adaptive_ceiling_rows=adaptive_ceiling_rows,
                            reason=reason,
                        )
                    artifact_read_started = perf_counter()
                    raw_batch = tuple(islice(iterator, proposed_size))
                    metrics["artifact_read_ms"] += int(
                        (perf_counter() - artifact_read_started) * 1000
                    )
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
                        batch_started = perf_counter()
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
                        if batch_tuner is not None:
                            batch_tuner.succeeded(
                                size=proposed_size,
                                rows=len(raw_batch),
                                duration_ms=int((perf_counter() - batch_started) * 1000),
                            )
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
        cancel_probe: _ReplayParentCancellationProbe,
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
                if cancel_probe.requested(context):
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
                    if cancel_probe.requested(context):
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
                    expected_artifact_ordinal=run.checkpoint_artifact_ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=selected.ordinal + 1,
                    next_row_number=0,
                    counters=_zero_counters(),
                    fence=fence,
                )
        finally:
            session.close()

    def _advance_checkpoint(
        self,
        run: CanonicalReplayRunRecord,
        *,
        next_artifact_ordinal: int,
        next_row_number: int,
        fence: JobExecutionFence,
    ) -> CanonicalReplayRunRecord:
        """原子越过一段没有业务行的 Artifact 尾部，不制造逐文件事务。"""

        if (
            next_artifact_ordinal < run.checkpoint_artifact_ordinal
            or next_artifact_ordinal > run.artifact_count
            or next_row_number < 0
            or (
                next_artifact_ordinal == run.checkpoint_artifact_ordinal
                and next_row_number <= run.checkpoint_row_number
            )
        ):
            raise ValueError("Replay 空区间 checkpoint 没有前进")
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return PostgresCanonicalReplayRepository(session).advance(
                    run_id=run.id,
                    expected_artifact_ordinal=run.checkpoint_artifact_ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=next_artifact_ordinal,
                    next_row_number=next_row_number,
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
        source_records: tuple[_ReplaySourceRecord, ...] | None = None,
        next_artifact_ordinal: int | None = None,
        next_row_number: int | None = None,
        resolved: tuple[tuple[CanonicalContentV1, BrandVehicleResolution], ...] | None = None,
        resolution_ms: int | None = None,
    ) -> CanonicalReplayRunRecord:
        batch_started = perf_counter()
        if resolved is None:
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
        elif len(resolved) != len(contents):
            raise ValueError("Replay 预解析结果与 raw batch 数量不一致")
        if source_records is None:
            source_records = tuple(
                _ReplaySourceRecord(selected=selected, artifact=artifact) for _ in contents
            )
        elif len(source_records) != len(contents):
            raise ValueError("Replay 来源记录与 raw batch 数量不一致")
        if resolution_ms is None:
            resolution_ms = 0
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
        workload_slot = None
        try:
            with session.begin():
                workload_slot = acquire_background_write_slot(
                    session,
                    resources=detect_resources(),
                    work_id=shard_id or fence.job_id,
                )
                # 后台重筛遇到在线事务锁竞争时主动让路；超时会回滚本批并进入 Job retry。
                session.execute(text(f"SET LOCAL lock_timeout = '{_REPLAY_LOCK_TIMEOUT}'"))
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
                            or current.checkpoint_artifact_ordinal
                            != run.checkpoint_artifact_ordinal
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
                source_contexts: dict[UUID, _ImportLineageContext | None] = {}
                lineage_by_artifact: dict[UUID, dict[str, tuple[UUID, UUID]]] = {}
                for source in source_records:
                    if source.selected.artifact_id not in source_contexts:
                        source_contexts[source.selected.artifact_id] = (
                            self._load_import_lineage_context(
                                session,
                                source.selected,
                                source.artifact,
                            )
                        )
                        lineage_by_artifact[source.selected.artifact_id] = {}
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
                for (content, resolution), source in zip(
                    resolved,
                    source_records,
                    strict=True,
                ):
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
                        selected=source.selected,
                        lineage=source_contexts[source.selected.artifact_id],
                        lineage_by_platform=lineage_by_artifact[source.selected.artifact_id],
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
                fallback_snapshot_ms = int((perf_counter() - fallback_snapshot_started) * 1000)
                fallback_content_started = perf_counter()
                fallback_items = content_repository.ingest_contents_with_before_snapshots_batch(
                    tuple(zip(fallback_observations, before_snapshots, strict=True)),
                    replay_accepted_before=(
                        repository.all_request_admission_times((current.all_request_id,))[
                            current.all_request_id
                        ]
                        if current.all_request_id is not None
                        and run.filter_snapshot.catalog.resolver_semantics
                        == "brand_scoped_vehicle_v2"
                        else None
                    ),
                )
                current_resolutions: dict[tuple[UUID, int], BrandVehicleResolution] = {}
                if run.filter_snapshot.catalog.resolver_semantics == "brand_scoped_vehicle_v2":
                    review_carry = tuple(
                        (item.result.target_id, item.before.version_no, item.result.version_no)
                        for item in fallback_items
                        if item.before.version_no is not None
                        and item.before.version_no != item.result.version_no
                        and not item.protected_by_later_write
                    )
                    review_pairs = tuple(
                        {
                            (content_id, version)
                            for content_id, source, target in review_carry
                            for version in (source, target)
                        }
                    )
                    vehicle_repository.load_locked_manual_vehicle_ids_batch(review_pairs)
                    brand_repository.load_locked_manual_brand_ids_batch(review_pairs)
                    vehicle_repository.carry_manual_review_batch(review_carry)
                    brand_repository.carry_manual_brand_review_batch(review_carry)
                    current_inputs = content_repository.lock_current_classification_inputs(
                        content_ids=tuple(
                            item.result.target_id
                            for item in fallback_items
                            if not item.protected_by_later_write
                        )
                    )
                    current_resolutions = self._resolve_current_classifications(
                        run, current_inputs, vehicle_repository, brand_repository
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
                    if fallback_item.protected_by_later_write:
                        continue
                    result = fallback_item.result
                    resolution = current_resolutions.get(
                        (result.target_id, result.version_no), resolution
                    )
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
                                if evidence.source == "alias_match"
                            ),
                        )
                    )
                    fallback_brand_entries.append(
                        (
                            result.target_id,
                            result.version_no,
                            tuple(
                                item
                                for item in resolution.brand_evidence
                                if item.source != "manual_review"
                            ),
                        )
                    )
                selected_scope = run.filter_snapshot.catalog.filter_scope == "selected"
                source_pairs = tuple(
                    (
                        (item.before.content_id, item.before.version_no)
                        if item.before.content_id is not None and item.before.version_no is not None
                        else None
                    )
                    for item in fallback_items
                    if not item.protected_by_later_write
                )
                (
                    vehicle_before_by_pair,
                    vehicle_after_by_pair,
                ) = vehicle_repository.converge_automatic_alias_evidence_for_replay(
                    entries=tuple(fallback_vehicle_entries),
                    source_pairs=source_pairs,
                    replace_existing=not selected_scope,
                    include_import_text_matches=(
                        run.filter_snapshot.catalog.resolver_semantics == "brand_scoped_vehicle_v2"
                    ),
                    replace_vehicle_model_ids=(
                        run.filter_snapshot.catalog.automatic_evidence_vehicle_ids
                        if run.filter_snapshot.catalog.resolver_semantics
                        == "brand_scoped_vehicle_v2"
                        else None
                    ),
                )
                (
                    brand_before_by_pair,
                    brand_after_by_pair,
                ) = brand_repository.converge_automatic_brand_evidence_for_replay(
                    entries=tuple(fallback_brand_entries),
                    source_pairs=source_pairs,
                    catalog_snapshot=run.filter_snapshot.catalog,
                    preserve_unconfirmed=selected_scope,
                )
                fallback_evidence_ms = int((perf_counter() - fallback_evidence_started) * 1000)
                protected_pairs = tuple(
                    (item.result.target_id, item.result.version_no)
                    for item in fallback_items
                    if item.protected_by_later_write
                )
                if protected_pairs:
                    protected_vehicles = vehicle_repository.snapshot_automatic_evidence_batch(
                        pairs=protected_pairs
                    )
                    protected_brands = brand_repository.snapshot_automatic_brand_evidence_batch(
                        pairs=protected_pairs
                    )
                    vehicle_before_by_pair.update(protected_vehicles)
                    vehicle_after_by_pair.update(protected_vehicles)
                    brand_before_by_pair.update(protected_brands)
                    brand_after_by_pair.update(protected_brands)
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
                    contribution_delta = build_content_contribution_delta(
                        observation, before, fallback_item.contribution_after
                    )
                    if run.filter_snapshot.catalog.resolver_semantics == "brand_scoped_vehicle_v2":
                        # 历史任一来源命中与当前 Evidence 分类分别持有。
                        contribution_delta["resolver_outcome"] = "matched"
                        if after_pair in current_resolutions:
                            contribution_delta["classification_outcome"] = (
                                "matched"
                                if current_resolutions[after_pair].matched
                                else "unmatched"
                            )
                        elif fallback_item.protected_by_later_write:
                            contribution_delta["classification_preserved"] = True
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
                            "delta": contribution_delta,
                            "visibility_owner_before": (
                                fallback_item.visibility_owner_before
                                if run.filter_snapshot.catalog.resolver_semantics
                                == "brand_scoped_vehicle_v2"
                                else owner_before_by_content.get(before.content_id)
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
                negative_content_ids = self._converge_unmatched_current(
                    session,
                    run=current,
                    resolved=resolved,
                    source_records=source_records,
                    source_contexts=source_contexts,
                    lineage_by_artifact=lineage_by_artifact,
                    content_repository=content_repository,
                    vehicle_repository=vehicle_repository,
                    brand_repository=brand_repository,
                    ledger_rows=ledger_rows,
                    positive_identities=set(resolution_by_identity),
                )
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
                checkpoint_artifact = (
                    selected.ordinal if next_artifact_ordinal is None else next_artifact_ordinal
                )
                checkpoint_row = (
                    run.checkpoint_row_number
                    + (raw_row_count if raw_row_count is not None else len(contents))
                    if next_row_number is None
                    else next_row_number
                )
                if shard_id is None:
                    advanced = repository.advance(
                        run_id=run.id,
                        expected_artifact_ordinal=run.checkpoint_artifact_ordinal,
                        expected_row_number=run.checkpoint_row_number,
                        next_artifact_ordinal=checkpoint_artifact,
                        next_row_number=checkpoint_row,
                        counters=counters,
                        fence=fence,
                    )
                else:
                    advanced = PostgresReplayShardRepository(session).advance(
                        shard_id=shard_id,
                        run_id=run.id,
                        expected_artifact_ordinal=selected.ordinal,
                        expected_row_number=run.checkpoint_row_number,
                        next_artifact_ordinal=checkpoint_artifact,
                        next_row_number=checkpoint_row,
                        counters=counters,
                        fence=fence,
                        finished=False,
                    )
                ledger_checkpoint_ms = int((perf_counter() - ledger_checkpoint_started) * 1000)
                projection_started = perf_counter()
                PostgresAnalysisReuseRepository(session).converge_reuses(
                    tuple((item.result.target_id, item.result.version_no) for item in batch_created)
                    + tuple(
                        (item.result.target_id, item.result.version_no) for item in fallback_items
                    )
                )
                projection_content_count = flush_deferred_voice_plaza_projection(
                    session,
                    tuple(item.result.target_id for item in batch_created)
                    + tuple(item.result.target_id for item in fallback_items)
                    + negative_content_ids,
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
            artifact_ordinal=run.checkpoint_artifact_ordinal,
            next_artifact_ordinal=advanced.checkpoint_artifact_ordinal,
            row_start=run.checkpoint_row_number,
            next_row_number=advanced.checkpoint_row_number,
            row_count=len(contents),
            raw_row_count=raw_row_count if raw_row_count is not None else len(contents),
            matched_count=matched,
            resolver_semantics=run.filter_snapshot.catalog.resolver_semantics,
            negative_convergence_count=len(negative_content_ids),
            protected_by_later_write_count=sum(
                item.protected_by_later_write for item in fallback_items
            ),
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
            workload_slot=workload_slot.slot if workload_slot is not None else None,
            workload_slot_count=(workload_slot.slot_count if workload_slot is not None else None),
            workload_slot_wait_ms=(workload_slot.wait_ms if workload_slot is not None else None),
            foreground_pressure=(
                workload_slot.foreground_pressure if workload_slot is not None else None
            ),
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
        if workload_slot is not None:
            batch_metrics["workload_slot_wait_ms"] += workload_slot.wait_ms
            batch_metrics["foreground_pressure_batches"] += int(workload_slot.foreground_pressure)
        return advanced

    def _resolve_current_classifications(
        self,
        run: CanonicalReplayRunRecord,
        inputs: tuple[PostgresContentClassificationInput, ...],
        vehicle_repository: PostgresVehicleCatalogRepository,
        brand_repository: PostgresBrandVehicleRepository,
    ) -> dict[tuple[UUID, int], BrandVehicleResolution]:
        """使用已稳定的 Current 与人工选择；预编译目录跨批次复用。"""

        return resolve_current_brand_vehicle_batch(
            snapshot=run.filter_snapshot.catalog,
            inputs=inputs,
            vehicle_repository=vehicle_repository,
            brand_repository=brand_repository,
            resolver=self._current_resolver,
        )

    def _converge_unmatched_current(
        self,
        session: Session,
        *,
        run: CanonicalReplayRunRecord,
        resolved: tuple[tuple[CanonicalContentV1, BrandVehicleResolution], ...],
        source_records: tuple[_ReplaySourceRecord, ...],
        source_contexts: dict[UUID, _ImportLineageContext | None],
        lineage_by_artifact: dict[UUID, dict[str, tuple[UUID, UUID]]],
        content_repository: PostgresCompleteContentRepository,
        vehicle_repository: PostgresVehicleCatalogRepository,
        brand_repository: PostgresBrandVehicleRepository,
        ledger_rows: list[dict[str, object]],
        positive_identities: set[tuple[str, str]],
    ) -> tuple[UUID, ...]:
        """全目录负向扫描只更新已有 Current；不消费后续正向 Raw 的入库身份。"""

        if (
            run.all_request_id is None
            or run.filter_snapshot.catalog.filter_scope == "selected"
            or run.filter_snapshot.catalog.resolver_semantics != "brand_scoped_vehicle_v2"
        ):
            return ()
        sources: dict[tuple[str, str], tuple[CanonicalContentV1, _ReplaySourceRecord]] = {
            (content.platform, content.external_content_id): (content, source)
            for (content, resolution), source in zip(resolved, source_records, strict=True)
            if not resolution.matched
            and (content.platform, content.external_content_id) not in positive_identities
        }
        inputs = content_repository.lock_current_classification_inputs(identities=tuple(sources))
        replay_repository = PostgresCanonicalReplayRepository(session)
        admission = replay_repository.all_request_admission_times(
            tuple(
                {
                    run.all_request_id,
                    *(
                        item.replay_visibility_owner_id
                        for item in inputs
                        if item.replay_visibility_owner_id is not None
                    ),
                }
            )
        )
        accepted_before = admission[run.all_request_id]
        inputs = tuple(
            item
            for item in inputs
            if (
                item.latest_normal_filter_match_at is None
                or item.latest_normal_filter_match_at <= accepted_before
            )
            and (
                item.replay_visibility_owner_id is None
                or admission[item.replay_visibility_owner_id] <= accepted_before
            )
        )
        if not inputs:
            return ()
        resolutions = self._resolve_current_classifications(
            run, inputs, vehicle_repository, brand_repository
        )
        observations = []
        for item in inputs:
            content, source = sources[(item.platform, item.external_content_id)]
            observations.append(
                self._content_with_lineage(
                    session,
                    content,
                    selected=source.selected,
                    lineage=source_contexts[source.selected.artifact_id],
                    lineage_by_platform=lineage_by_artifact[source.selected.artifact_id],
                )
            )
        frozen = capture_content_contribution_snapshots_batch(
            session,
            tuple(
                (observation, item.content_id)
                for observation, item in zip(observations, inputs, strict=True)
            ),
        )
        pairs = tuple((item.content_id, item.content_version) for item in inputs)
        now = beijing_now()
        vehicle_entries = tuple(
            (
                item.content_id,
                item.content_version,
                tuple(
                    ContentVehicleEvidence(
                        id=uuid4(),
                        content_id=item.content_id,
                        content_version=item.content_version,
                        vehicle_model_id=evidence.entity_id,
                        source="alias_match",
                        matched_text=evidence.matched_text,
                        source_field=evidence.source_field,
                        catalog_version=run.filter_snapshot.catalog.catalog_version,
                        confidence=1.0,
                        is_manual_locked=False,
                        is_active=True,
                        created_at=now,
                    )
                    for evidence in resolutions[
                        (item.content_id, item.content_version)
                    ].vehicle_evidence
                    if evidence.source == "alias_match"
                ),
            )
            for item in inputs
        )
        vehicle_before, vehicle_after = (
            vehicle_repository.converge_automatic_alias_evidence_for_replay(
                entries=vehicle_entries,
                source_pairs=pairs,
                replace_existing=True,
                include_import_text_matches=True,
            )
        )
        brand_before, brand_after = brand_repository.converge_automatic_brand_evidence_for_replay(
            entries=tuple(
                (
                    item.content_id,
                    item.content_version,
                    tuple(
                        evidence
                        for evidence in resolutions[
                            (item.content_id, item.content_version)
                        ].brand_evidence
                        if evidence.source != "manual_review"
                    ),
                )
                for item in inputs
            ),
            source_pairs=pairs,
            catalog_snapshot=run.filter_snapshot.catalog,
            preserve_unconfirmed=False,
        )
        changed_pairs = []
        for item, observation, before in zip(inputs, observations, frozen, strict=True):
            pair = (item.content_id, item.content_version)
            resolution = resolutions[pair]
            if (
                vehicle_before[pair] == vehicle_after[pair]
                and brand_before[pair] == brand_after[pair]
                and not resolution.matched
            ):
                continue
            delta = build_content_contribution_delta(observation, before, before)
            delta["resolver_outcome"] = "matched" if resolution.matched else "unmatched"
            delta["replay_evidence_only"] = True
            if (
                observation.source.provider_attempt_id is None
                or observation.source.raw_artifact_id is None
            ):
                raise ValueError("Replay 贡献账本要求 Attempt 与 Raw 来源")
            changed_pairs.append(pair)
            ledger_rows.append(
                {
                    "id": uuid4(),
                    "all_request_id": run.all_request_id,
                    "run_id": run.id,
                    "content_id": item.content_id,
                    "provider_attempt_id": UUID(observation.source.provider_attempt_id),
                    "raw_artifact_id": observation.source.raw_artifact_id,
                    "version_before": item.content_version,
                    "version_after": item.content_version,
                    "delta": delta,
                    "visibility_owner_before": item.replay_visibility_owner_id,
                    "vehicle_evidence_before": vehicle_before[pair],
                    "vehicle_evidence_after": vehicle_after[pair],
                    "brand_evidence_before": brand_before[pair],
                    "brand_evidence_after": brand_after[pair],
                    "created_at": now,
                }
            )
        content_repository.claim_replay_evidence_changes(tuple(changed_pairs))
        return tuple(item[0] for item in changed_pairs)

    @staticmethod
    def _flush_ledger_rows(session: Session, rows: list[dict[str, object]]) -> None:
        """账本 SQL 合批但保持有界内存，所有片段仍属于同一 checkpoint 事务。"""

        if rows:
            table = canonical_replay_content_changes_table
            statement = pg_insert(table)
            incoming = statement.excluded
            evidence_only = incoming.delta["replay_evidence_only"].astext == "true"
            previous_evidence_only = table.c.delta["replay_evidence_only"].astext == "true"
            continuous = func.coalesce(
                (table.c.version_after == incoming.version_before)
                & (table.c.vehicle_evidence_after == incoming.vehicle_evidence_before)
                & (table.c.brand_evidence_after == incoming.brand_evidence_before)
                & (incoming.visibility_owner_before == incoming.all_request_id),
                False,
            )
            matched_outcome = case(
                (
                    (
                        table.c.delta["replay_evidence_only"].astext.is_distinct_from("true")
                        | (table.c.delta["resolver_outcome"].astext == "matched")
                        | incoming.delta["replay_evidence_only"].astext.is_distinct_from("true")
                        | (incoming.delta["resolver_outcome"].astext == "matched")
                    ),
                    "matched",
                ),
                else_="unmatched",
            )
            # 只有 owner、版本和 Evidence 连续才折叠；外部写入后的新段单独可撤回。
            upsert = statement.on_conflict_do_update(
                constraint="uq_canonical_replay_content_changes_run_content",
                set_={
                    "version_after": incoming.version_after,
                    "version_before": case(
                        (continuous, table.c.version_before), else_=incoming.version_before
                    ),
                    "visibility_owner_before": case(
                        (continuous, table.c.visibility_owner_before),
                        else_=incoming.visibility_owner_before,
                    ),
                    "vehicle_evidence_before": case(
                        (continuous, table.c.vehicle_evidence_before),
                        else_=incoming.vehicle_evidence_before,
                    ),
                    "brand_evidence_before": case(
                        (continuous, table.c.brand_evidence_before),
                        else_=incoming.brand_evidence_before,
                    ),
                    "created_at": case((continuous, table.c.created_at), else_=incoming.created_at),
                    "vehicle_evidence_after": incoming.vehicle_evidence_after,
                    "brand_evidence_after": incoming.brand_evidence_after,
                    "delta": case(
                        (
                            evidence_only & continuous,
                            table.c.delta.op("||")(
                                func.jsonb_build_object(
                                    "resolver_outcome",
                                    matched_outcome,
                                    "classification_outcome",
                                    incoming.delta["resolver_outcome"],
                                )
                            ),
                        ),
                        else_=incoming.delta.op("||")(
                            func.jsonb_build_object("resolver_outcome", matched_outcome)
                        ),
                    ),
                    "provider_attempt_id": case(
                        (evidence_only & continuous, table.c.provider_attempt_id),
                        else_=incoming.provider_attempt_id,
                    ),
                    "raw_artifact_id": case(
                        (evidence_only & continuous, table.c.raw_artifact_id),
                        else_=incoming.raw_artifact_id,
                    ),
                },
                where=(table.c.all_request_id == incoming.all_request_id)
                & table.c.reverted_at.is_(None)
                & (evidence_only | previous_evidence_only),
            ).returning(table.c.id)
            applied = session.scalars(upsert, rows).all()
            if len(applied) != len(rows):
                raise ValueError("Replay 同一 Run 重复提交非 Evidence-only 内容贡献")
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
