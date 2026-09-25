"""全历史 Canonical Replay 的精确、可恢复撤回执行器。"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.brand_vehicle import (
    PostgresBrandVehicleRepository,
)
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.content_lifecycle import (
    PostgresContentLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.replay_shards import PostgresReplayShardRepository
from aima_ugc.adapters.persistence.postgres.reversal_shards import PostgresReversalShardRepository
from aima_ugc.adapters.persistence.postgres.vehicles import (
    PostgresVehicleCatalogRepository,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.ingestion.canonical_replay import (
    CanonicalReplayAllRequestRecord,
    CanonicalReplayReversalJobPayload,
)
from aima_ugc.modules.ingestion.canonical_replay_tables import (
    canonical_replay_all_requests_table,
    canonical_replay_content_changes_table,
)
from aima_ugc.modules.ingestion.reversal_shards import REVERSAL_MIN_PARALLEL_CONTENTS
from aima_ugc.platform.capacity import (
    AdaptiveTierBatchController,
    detect_resources,
    select_job_window,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

if TYPE_CHECKING:
    from .adaptive_shard_worker import AdaptiveShardCoordinator

_CONTENT_BATCH_SIZE = 100


class PostgresCanonicalReplayReversalJobExecutor:
    """按 Content 分批逆序应用账本，并在每批提交时验证 Job Fence。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._retry_jobs: set[UUID] = set()
        self.shard_coordinator: AdaptiveShardCoordinator | None = None

    def _new_batch_tuner(self, job_id: UUID) -> AdaptiveTierBatchController:
        tuner = AdaptiveTierBatchController(
            improvement_margin=0.20,
            rows_per_cpu_core=500,
            memory_mib_per_1000_rows=3072,
        )
        if job_id in self._retry_jobs:
            tuner.database_retry()
        return tuner

    def execute(
        self,
        *,
        payload: CanonicalReplayReversalJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        execution_started = perf_counter()
        batch_durations_ms: list[int] = []
        batch_observations: dict[int, list[int]] = {}
        simple_lifecycle_count = 0
        simple_lifecycle_ms = 0
        batch_tuner = self._new_batch_tuner(fence.job_id)
        try:
            total, remaining = self._content_counts(payload.request_id)
            if self.shard_coordinator is not None and (
                self._has_shards(payload.request_id)
                or (
                    remaining >= REVERSAL_MIN_PARALLEL_CONTENTS
                    and select_job_window(detect_resources()) >= 2
                )
            ):

                def finish() -> JobHandlerResult:
                    record = self._finish(payload.request_id, fence=fence)
                    log_event(
                        self._runtime.logger,
                        logging.INFO,
                        "canonical_replay.reversal_completed",
                        "历史重筛撤回分片完成",
                        request_id=str(payload.request_id),
                        reverted_content_count=record.reverted_content_count,
                        skipped_content_count=record.skipped_content_count,
                        duration_ms=int((perf_counter() - execution_started) * 1000),
                    )
                    return JobHandlerResult.succeeded(
                        {
                            "request_id": str(payload.request_id),
                            "reverted_content_count": record.reverted_content_count,
                        }
                    )

                return self.shard_coordinator.execute_parent(
                    kind="replay",
                    parent_id=payload.request_id,
                    remaining_contents=remaining,
                    fence=fence,
                    context=context,
                    finish=finish,
                )
            completed = total - remaining
            while True:
                resources = detect_resources()
                batch_size, reason, previous = batch_tuner.choose(resources)
                if previous != batch_size:
                    log_event(
                        self._runtime.logger,
                        logging.INFO,
                        "capacity.reversal_batch_selected",
                        "重筛撤回批量调整",
                        request_id=str(payload.request_id),
                        previous_contents=previous,
                        selected_contents=batch_size,
                        reason=reason,
                        available_memory_mib=(
                            resources.memory_available_bytes // (1024 * 1024)
                            if resources.memory_available_bytes is not None
                            else None
                        ),
                    )
                batch_started = perf_counter()
                processed, simple_count, simple_ms = self._reverse_batch(
                    payload.request_id, fence=fence, limit=batch_size
                )
                simple_lifecycle_count += simple_count
                simple_lifecycle_ms += simple_ms
                batch_ms = int((perf_counter() - batch_started) * 1000)
                if processed:
                    batch_durations_ms.append(batch_ms)
                    observation = batch_observations.setdefault(batch_size, [0, 0, 0])
                    observation[0] += 1
                    observation[1] += processed
                    observation[2] += batch_ms
                    batch_tuner.succeeded(size=batch_size, rows=processed, duration_ms=batch_ms)
                completed += processed
                remaining = max(total - completed, 0)
                context.heartbeat(
                    progress=(
                        100 if remaining == 0 else min(99, int(completed * 100 / max(total, 1)))
                    )
                )
                if processed == 0:
                    record = self._finish(payload.request_id, fence=fence)
                    self._retry_jobs.discard(fence.job_id)
                    log_event(
                        self._runtime.logger,
                        logging.INFO,
                        "canonical_replay.reversal_completed",
                        "历史重筛撤回完成",
                        request_id=str(payload.request_id),
                        reverted_content_count=record.reverted_content_count,
                        skipped_content_count=record.skipped_content_count,
                        batch_count=len(batch_durations_ms),
                        batch_observations=[
                            {
                                "batch_size": size,
                                "batch_count": values[0],
                                "content_count": values[1],
                                "duration_ms": values[2],
                            }
                            for size, values in sorted(batch_observations.items())
                        ],
                        slowest_batch_ms=max(batch_durations_ms, default=0),
                        simple_lifecycle_count=simple_lifecycle_count,
                        simple_lifecycle_ms=simple_lifecycle_ms,
                        duration_ms=int((perf_counter() - execution_started) * 1000),
                    )
                    return JobHandlerResult.succeeded(
                        {
                            "request_id": str(record.id),
                            "reverted_content_count": record.reverted_content_count,
                            "hidden_content_count": record.hidden_content_count,
                            "retained_content_count": record.retained_content_count,
                            "skipped_content_count": record.skipped_content_count,
                            "restored_evidence_count": record.restored_evidence_count,
                            "skipped_evidence_count": record.skipped_evidence_count,
                        }
                    )
        except LeaseLostError:
            raise
        except LookupError, ValueError:
            return JobHandlerResult.failed("canonical_replay_reversal_invalid")
        except SQLAlchemyError:
            self._retry_jobs.add(fence.job_id)
            return JobHandlerResult.retry("canonical_replay_reversal_transient_error")

    def _has_shards(self, request_id: UUID) -> bool:
        session = self._runtime.database.new_session()
        try:
            return bool(PostgresReversalShardRepository(session).list("replay", request_id))
        finally:
            session.close()

    def process_shard(
        self,
        shard_id: UUID,
        *,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> int:
        session = self._runtime.database.new_session()
        try:
            shard = PostgresReversalShardRepository(session).get(shard_id)
            if shard is None or shard["kind"] != "replay":
                raise LookupError("历史重筛撤回工作单元不存在")
            request_id = cast(UUID, shard["replay_request_id"])
        finally:
            session.close()
        tuner = self._new_batch_tuner(fence.job_id)
        total = 0
        while True:
            if context.cancel_requested():
                raise LeaseLostError("撤回分片已取消")
            size, _, _ = tuner.choose(detect_resources())
            started = perf_counter()
            processed, _, _ = self._reverse_batch(
                request_id, fence=fence, limit=size, shard_id=shard_id
            )
            total += processed
            if not processed:
                context.heartbeat(progress=100)
                return total
            tuner.succeeded(
                size=size,
                rows=processed,
                duration_ms=max(1, int((perf_counter() - started) * 1000)),
            )
            context.heartbeat(progress=50)

    def _content_counts(self, request_id: UUID) -> tuple[int, int]:
        """一次扫描取得总量与未结清量，支持 Reversal Attempt 断点恢复。"""

        session = self._runtime.database.new_session()
        try:
            row = session.execute(
                select(
                    func.count(func.distinct(canonical_replay_content_changes_table.c.content_id)),
                    func.count(
                        func.distinct(canonical_replay_content_changes_table.c.content_id)
                    ).filter(canonical_replay_content_changes_table.c.reverted_at.is_(None)),
                ).where(canonical_replay_content_changes_table.c.all_request_id == request_id)
            ).one()
            return (
                int(row[0] or 0),
                int(row[1] or 0),
            )
        finally:
            session.close()

    def _reverse_batch(
        self,
        request_id: UUID,
        *,
        fence: JobExecutionFence,
        limit: int = _CONTENT_BATCH_SIZE,
        shard_id: UUID | None = None,
    ) -> tuple[int, int, int]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                shards = PostgresReversalShardRepository(session)
                shard = shards.assert_owner(shard_id, fence) if shard_id is not None else None
                if shard is not None and shard["replay_request_id"] != request_id:
                    raise LeaseLostError("历史重筛撤回工作单元父请求不匹配")
                request = PostgresCanonicalReplayRepository(session).get_all_request(
                    request_id,
                    for_update=shard is None,
                )
                if (
                    request is None
                    or not request.reversible
                    or request.lifecycle_status != "reverting"
                    or (shard is None and request.reversal_job_id != fence.job_id)
                ):
                    raise LeaseLostError("Canonical Replay 撤回 Job 已不属于当前父请求")
                content_query = select(canonical_replay_content_changes_table.c.content_id).where(
                    canonical_replay_content_changes_table.c.all_request_id == request_id,
                    canonical_replay_content_changes_table.c.reverted_at.is_(None),
                )
                if shard is not None:
                    content_query = content_query.where(
                        canonical_replay_content_changes_table.c.content_id
                        >= shard["lower_content_id"]
                    )
                    if shard["upper_content_id"] is not None:
                        content_query = content_query.where(
                            canonical_replay_content_changes_table.c.content_id
                            < shard["upper_content_id"]
                        )
                content_ids = tuple(
                    session.scalars(
                        content_query.distinct()
                        .order_by(canonical_replay_content_changes_table.c.content_id)
                        .limit(limit)
                    )
                )
                if not content_ids:
                    if shard is not None:
                        shards.advance(
                            cast(UUID, shard_id), checkpoint=None, processed=0, finished=True
                        )
                    return 0, 0, 0

                ledger_rows = tuple(
                    session.execute(
                        select(canonical_replay_content_changes_table)
                        .where(
                            canonical_replay_content_changes_table.c.all_request_id == request_id,
                            canonical_replay_content_changes_table.c.content_id.in_(content_ids),
                            canonical_replay_content_changes_table.c.reverted_at.is_(None),
                        )
                        .order_by(
                            canonical_replay_content_changes_table.c.content_id,
                            canonical_replay_content_changes_table.c.created_at,
                            canonical_replay_content_changes_table.c.id,
                        )
                        .with_for_update()
                    ).mappings()
                )
                rows_by_content: dict[UUID, list[RowMapping]] = {}
                for row in ledger_rows:
                    rows_by_content.setdefault(cast(UUID, row["content_id"]), []).append(row)
                states = {
                    cast(UUID, row.id): row
                    for row in session.execute(
                        select(
                            contents_table.c.id,
                            contents_table.c.current_version,
                            contents_table.c.replay_visibility_owner_id,
                        )
                        .where(contents_table.c.id.in_(content_ids))
                        .order_by(contents_table.c.id)
                        .with_for_update()
                    )
                }

                lifecycle = PostgresContentLifecycleRepository(session)
                vehicle_repository = PostgresVehicleCatalogRepository(session)
                brand_repository = PostgresBrandVehicleRepository(session)
                now = beijing_now()
                reverted = hidden = retained = skipped = restored_evidence = skipped_evidence = 0
                # 同版本、仅 Evidence 变化是实测主路径。先按 Owner 的锁/快照规则
                # 集合恢复，再一次结清归属和账本，避免每条内容重复往返数据库。
                evidence_only = tuple(
                    content_id
                    for content_id in content_ids
                    if content_id in rows_by_content
                    and states[content_id].replay_visibility_owner_id == request_id
                    and not any(
                        _has_content_delta(row["delta"]) for row in rows_by_content[content_id]
                    )
                )
                safe_evidence = tuple(
                    content_id
                    for content_id in evidence_only
                    if states[content_id].current_version
                    == rows_by_content[content_id][-1]["version_after"]
                )
                vehicle_restored_ids = vehicle_repository.restore_automatic_evidence_batch(
                    tuple(
                        (
                            content_id,
                            cast(int, states[content_id].current_version),
                            _json_rows(rows_by_content[content_id][-1]["vehicle_evidence_after"]),
                            _json_rows(rows_by_content[content_id][0]["vehicle_evidence_before"]),
                        )
                        for content_id in safe_evidence
                    )
                )
                brand_restored_ids = brand_repository.restore_automatic_brand_evidence_batch(
                    tuple(
                        (
                            content_id,
                            cast(int, states[content_id].current_version),
                            _json_rows(rows_by_content[content_id][-1]["brand_evidence_after"]),
                            _json_rows(rows_by_content[content_id][0]["brand_evidence_before"]),
                        )
                        for content_id in safe_evidence
                    )
                )
                if evidence_only:
                    owner_before = {
                        content_id: rows_by_content[content_id][0]["visibility_owner_before"]
                        for content_id in evidence_only
                    }
                    session.execute(
                        update(contents_table)
                        .where(contents_table.c.id.in_(evidence_only))
                        .values(
                            replay_visibility_owner_id=sql_cast(
                                case(owner_before, value=contents_table.c.id),
                                contents_table.c.replay_visibility_owner_id.type,
                            )
                        )
                    )
                    session.execute(
                        update(canonical_replay_content_changes_table)
                        .where(
                            canonical_replay_content_changes_table.c.all_request_id == request_id,
                            canonical_replay_content_changes_table.c.content_id.in_(evidence_only),
                            canonical_replay_content_changes_table.c.reverted_at.is_(None),
                        )
                        .values(
                            reverted_at=now,
                            reversal_version_no=case(
                                {
                                    content_id: states[content_id].current_version
                                    for content_id in evidence_only
                                },
                                value=canonical_replay_content_changes_table.c.content_id,
                            ),
                        )
                    )
                    reverted += len(evidence_only)
                    retained += len(evidence_only)
                    restored_evidence += len(vehicle_restored_ids) + len(brand_restored_ids)
                    skipped_evidence += 2 * len(evidence_only) - (
                        len(vehicle_restored_ids) + len(brand_restored_ids)
                    )
                evidence_only_set = set(evidence_only)
                # 已由后续写入接管的内容只需结清本次账本。批量更新保留各自的
                # 当前版本，避免为每条内容发送一次相同结构的 SQL。
                later_owned = tuple(
                    content_id
                    for content_id in content_ids
                    if content_id in rows_by_content
                    and content_id not in evidence_only_set
                    and states[content_id].replay_visibility_owner_id != request_id
                )
                if later_owned:
                    session.execute(
                        update(canonical_replay_content_changes_table)
                        .where(
                            canonical_replay_content_changes_table.c.all_request_id == request_id,
                            canonical_replay_content_changes_table.c.content_id.in_(later_owned),
                            canonical_replay_content_changes_table.c.reverted_at.is_(None),
                        )
                        .values(
                            reverted_at=now,
                            reversal_version_no=case(
                                {
                                    content_id: states[content_id].current_version
                                    for content_id in later_owned
                                },
                                value=canonical_replay_content_changes_table.c.content_id,
                            ),
                        )
                    )
                    reverted += len(later_owned)
                    retained += len(later_owned)
                    skipped += len(later_owned)
                    skipped_evidence += 2 * len(later_owned)
                later_owned_set = set(later_owned)
                simple_content_ids = tuple(
                    content_id
                    for content_id in content_ids
                    if content_id not in evidence_only_set
                    and content_id not in later_owned_set
                    and any(_has_content_delta(row["delta"]) for row in rows_by_content[content_id])
                    and all(
                        isinstance(row["delta"], dict)
                        and not row["delta"].get("account")
                        and isinstance(row["delta"].get("collections") or {}, dict)
                        and set(row["delta"].get("collections") or {}) <= {"alternate_ids"}
                        for row in rows_by_content[content_id]
                    )
                )
                simple_started = perf_counter()
                simple_versions = lifecycle.apply_simple_contributions_batch(
                    tuple(
                        row
                        for content_id in simple_content_ids
                        for row in rows_by_content[content_id]
                    ),
                    revoked_at=now,
                )
                simple_ms = int((perf_counter() - simple_started) * 1000)
                simple_owners: dict[UUID, UUID | None] = {}
                simple_review_entries: list[tuple[UUID, int, int]] = []
                simple_vehicle_entries: list[
                    tuple[UUID, int, int, list[dict[str, object]], list[dict[str, object]]]
                ] = []
                simple_brand_entries: list[
                    tuple[UUID, int, int, list[dict[str, object]], list[dict[str, object]]]
                ] = []
                for content_id in content_ids:
                    if content_id in evidence_only_set or content_id in later_owned_set:
                        continue
                    rows = tuple(rows_by_content.get(content_id, ()))
                    if not rows:
                        continue
                    current_state = states[content_id]
                    current_before = cast(int, current_state.current_version)
                    earliest = rows[0]
                    latest = rows[-1]
                    delta = earliest["delta"]
                    created_content = bool(
                        isinstance(delta, dict) and delta.get("created_content") is True
                    )
                    has_content_delta = any(_has_content_delta(row["delta"]) for row in rows)
                    if content_id in simple_versions:
                        reversal_version = simple_versions[content_id]
                    elif has_content_delta:
                        versions = lifecycle.apply_contributions(rows, revoked_at=now)
                        if not versions:
                            skipped += 1
                            continue
                        reversal_version = versions[0][1]
                    else:
                        # Replay 可能只幂等重写自动 Brand/Vehicle Evidence。此时追加
                        # Content Version 会把仍然有效的 AI/人工分析投影错误标成 stale。
                        reversal_version = current_before
                    next_owner = (
                        request_id if created_content else earliest["visibility_owner_before"]
                    )
                    if content_id in simple_versions:
                        simple_owners[content_id] = cast(UUID | None, next_owner)
                    else:
                        session.execute(
                            update(contents_table)
                            .where(contents_table.c.id == content_id)
                            .values(replay_visibility_owner_id=next_owner)
                        )
                    if created_content:
                        hidden += 1
                    else:
                        retained += 1

                    evidence_safe = current_before == latest["version_after"]
                    if evidence_safe and content_id in simple_versions:
                        source_version = cast(int, latest["version_after"])
                        simple_review_entries.append(
                            (cast(UUID, content_id), source_version, reversal_version)
                        )
                        simple_vehicle_entries.append(
                            (
                                cast(UUID, content_id),
                                source_version,
                                reversal_version,
                                _json_rows(latest["vehicle_evidence_after"]),
                                _json_rows(earliest["vehicle_evidence_before"]),
                            )
                        )
                        simple_brand_entries.append(
                            (
                                cast(UUID, content_id),
                                source_version,
                                reversal_version,
                                _json_rows(latest["brand_evidence_after"]),
                                _json_rows(earliest["brand_evidence_before"]),
                            )
                        )
                        evidence_batched = True
                        vehicle_restored = brand_restored = False
                    elif evidence_safe:
                        evidence_batched = False
                        if reversal_version != latest["version_after"]:
                            vehicle_repository.carry_manual_review(
                                content_id=cast(UUID, content_id),
                                source_version=cast(int, latest["version_after"]),
                                target_version=reversal_version,
                            )
                            brand_repository.carry_manual_brand_review(
                                content_id=cast(UUID, content_id),
                                source_version=cast(int, latest["version_after"]),
                                target_version=reversal_version,
                            )
                        vehicle_restored = vehicle_repository.restore_automatic_evidence(
                            content_id=cast(UUID, content_id),
                            source_version=cast(int, latest["version_after"]),
                            target_version=reversal_version,
                            expected_after=_json_rows(latest["vehicle_evidence_after"]),
                            before=_json_rows(earliest["vehicle_evidence_before"]),
                        )
                        brand_restored = brand_repository.restore_automatic_brand_evidence(
                            content_id=cast(UUID, content_id),
                            source_version=cast(int, latest["version_after"]),
                            target_version=reversal_version,
                            expected_after=_json_rows(latest["brand_evidence_after"]),
                            before=_json_rows(earliest["brand_evidence_before"]),
                        )
                    else:
                        evidence_batched = False
                        vehicle_restored = brand_restored = False
                    if not evidence_batched:
                        restored_evidence += int(vehicle_restored) + int(brand_restored)
                        skipped_evidence += int(not vehicle_restored) + int(not brand_restored)
                    if content_id not in simple_versions:
                        session.execute(
                            update(canonical_replay_content_changes_table)
                            .where(
                                canonical_replay_content_changes_table.c.all_request_id
                                == request_id,
                                canonical_replay_content_changes_table.c.content_id == content_id,
                                canonical_replay_content_changes_table.c.reverted_at.is_(None),
                            )
                            .values(reverted_at=now, reversal_version_no=reversal_version)
                        )
                    reverted += 1

                if simple_review_entries:
                    review_entries = tuple(simple_review_entries)
                    vehicle_repository.carry_manual_review_batch(review_entries)
                    brand_repository.carry_manual_brand_review_batch(review_entries)
                    vehicle_restored_ids = (
                        vehicle_repository.restore_automatic_evidence_new_version_batch(
                            tuple(simple_vehicle_entries)
                        )
                    )
                    brand_restored_ids = (
                        brand_repository.restore_automatic_brand_evidence_new_version_batch(
                            tuple(simple_brand_entries)
                        )
                    )
                    restored_evidence += len(vehicle_restored_ids) + len(brand_restored_ids)
                    skipped_evidence += 2 * len(review_entries) - (
                        len(vehicle_restored_ids) + len(brand_restored_ids)
                    )
                if simple_owners:
                    simple_ids = tuple(simple_owners)
                    session.execute(
                        update(contents_table)
                        .where(contents_table.c.id.in_(simple_ids))
                        .values(
                            replay_visibility_owner_id=sql_cast(
                                case(simple_owners, value=contents_table.c.id),
                                contents_table.c.replay_visibility_owner_id.type,
                            )
                        )
                    )
                    session.execute(
                        update(canonical_replay_content_changes_table)
                        .where(
                            canonical_replay_content_changes_table.c.all_request_id == request_id,
                            canonical_replay_content_changes_table.c.content_id.in_(simple_ids),
                            canonical_replay_content_changes_table.c.reverted_at.is_(None),
                        )
                        .values(
                            reverted_at=now,
                            reversal_version_no=case(
                                simple_versions,
                                value=canonical_replay_content_changes_table.c.content_id,
                            ),
                        )
                    )

                updated_request = cast(
                    CursorResult[object],
                    session.execute(
                        update(canonical_replay_all_requests_table)
                        .where(
                            canonical_replay_all_requests_table.c.id == request_id,
                            canonical_replay_all_requests_table.c.lifecycle_status == "reverting",
                            canonical_replay_all_requests_table.c.reversal_job_id
                            == request.reversal_job_id,
                        )
                        .values(
                            reverted_content_count=(
                                canonical_replay_all_requests_table.c.reverted_content_count
                                + reverted
                            ),
                            hidden_content_count=(
                                canonical_replay_all_requests_table.c.hidden_content_count + hidden
                            ),
                            retained_content_count=(
                                canonical_replay_all_requests_table.c.retained_content_count
                                + retained
                            ),
                            skipped_content_count=(
                                canonical_replay_all_requests_table.c.skipped_content_count
                                + skipped
                            ),
                            restored_evidence_count=(
                                canonical_replay_all_requests_table.c.restored_evidence_count
                                + restored_evidence
                            ),
                            skipped_evidence_count=(
                                canonical_replay_all_requests_table.c.skipped_evidence_count
                                + skipped_evidence
                            ),
                        )
                    ),
                )
                if updated_request.rowcount != 1:
                    raise LeaseLostError("历史重筛撤回父请求状态已改变")
                if shard is not None:
                    shards.advance(
                        cast(UUID, shard_id),
                        checkpoint=cast(UUID, content_ids[-1]),
                        processed=len(content_ids),
                        finished=False,
                    )
                return len(content_ids), len(simple_versions), simple_ms
        finally:
            session.close()

    def _finish(
        self,
        request_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> CanonicalReplayAllRequestRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                remaining = session.scalar(
                    select(func.count())
                    .select_from(canonical_replay_content_changes_table)
                    .where(
                        canonical_replay_content_changes_table.c.all_request_id == request_id,
                        canonical_replay_content_changes_table.c.reverted_at.is_(None),
                    )
                )
                if remaining:
                    raise RuntimeError("Canonical Replay 撤回账本仍有未处理记录")
                now = beijing_now()
                session.execute(
                    update(canonical_replay_all_requests_table)
                    .where(
                        canonical_replay_all_requests_table.c.id == request_id,
                        canonical_replay_all_requests_table.c.lifecycle_status == "reverting",
                        canonical_replay_all_requests_table.c.reversal_job_id == fence.job_id,
                    )
                    .values(lifecycle_status="reverted", reversed_at=now)
                )
                record = PostgresCanonicalReplayRepository(session).get_all_request(request_id)
                if record is None or record.lifecycle_status != "reverted":
                    raise LeaseLostError("Canonical Replay 撤回完成状态写入失败")
                return record
        finally:
            session.close()


def canonical_replay_job_terminal_callback(session: Session, job: JobRecord) -> None:
    """子 Replay 终态后，若全部子任务已结束则排队撤回 Job。"""

    run_id = job.payload.get("run_id")
    if run_id is None:
        return
    if job.status != "succeeded":
        jobs = PostgresJobRepository(session)
        for shard in PostgresReplayShardRepository(session).list(UUID(str(run_id))):
            child_id = cast(UUID | None, shard["job_id"])
            if (
                child_id is not None
                and child_id != job.id
                and shard["status"] in {"queued", "running"}
            ):
                jobs.request_cancel(child_id)
    repository = PostgresCanonicalReplayRepository(session)
    run = repository.get(UUID(str(run_id)))
    if run is not None and run.all_request_id is not None:
        repository.ensure_reversal_job_if_ready(run.all_request_id)


def canonical_replay_reversal_terminal_callback(
    session: Session,
    job: JobRecord,
) -> None:
    """撤回 Job 非成功终态会把父请求标记为可见失败。"""

    if job.status == "succeeded":
        return
    request_id = job.payload.get("request_id")
    if request_id is not None:
        shards = PostgresReversalShardRepository(session).list("replay", UUID(str(request_id)))
        jobs = PostgresJobRepository(session)
        for shard in shards:
            child_id = cast(UUID | None, shard["job_id"])
            if (
                child_id is not None
                and child_id != job.id
                and shard["status"] in {"queued", "running"}
            ):
                jobs.request_cancel(child_id)
        PostgresCanonicalReplayRepository(session).mark_reversal_failed(UUID(str(request_id)))


def _json_rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("Replay Evidence Snapshot 必须是对象数组")
    return [cast(dict[str, object], item) for item in value]


def _has_content_delta(value: object) -> bool:
    """判断 Replay 是否真的改变了 Content/Account Current，而非仅改 Evidence。"""

    if not isinstance(value, dict) or value.get("schema_version") != (
        "content-source-contribution.v1"
    ):
        raise ValueError("Replay Content Delta 版本不受支持")
    return bool(
        value.get("created_content") is True
        or value.get("content_fields")
        or value.get("author_snapshot")
        or value.get("collections")
        or value.get("account")
    )


__all__ = [
    "PostgresCanonicalReplayReversalJobExecutor",
    "canonical_replay_job_terminal_callback",
    "canonical_replay_reversal_terminal_callback",
]
