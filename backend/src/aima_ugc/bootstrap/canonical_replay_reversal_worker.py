"""全历史 Canonical Replay 的精确、可恢复撤回执行器。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
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
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_CONTENT_BATCH_SIZE = 100


class PostgresCanonicalReplayReversalJobExecutor:
    """按 Content 分批逆序应用账本，并在每批提交时验证 Job Fence。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def execute(
        self,
        *,
        payload: CanonicalReplayReversalJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        try:
            total = self._total_contents(payload.request_id)
            while True:
                processed = self._reverse_batch(payload.request_id, fence=fence)
                remaining = self._remaining_contents(payload.request_id)
                completed = total - remaining
                context.heartbeat(
                    progress=(
                        100 if remaining == 0 else min(99, int(completed * 100 / max(total, 1)))
                    )
                )
                if processed == 0:
                    record = self._finish(payload.request_id, fence=fence)
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
            return JobHandlerResult.retry("canonical_replay_reversal_transient_error")

    def _total_contents(self, request_id: UUID) -> int:
        session = self._runtime.database.new_session()
        try:
            return int(
                session.scalar(
                    select(
                        func.count(
                            func.distinct(canonical_replay_content_changes_table.c.content_id)
                        )
                    ).where(canonical_replay_content_changes_table.c.all_request_id == request_id)
                )
                or 0
            )
        finally:
            session.close()

    def _remaining_contents(self, request_id: UUID) -> int:
        session = self._runtime.database.new_session()
        try:
            return int(
                session.scalar(
                    select(
                        func.count(
                            func.distinct(canonical_replay_content_changes_table.c.content_id)
                        )
                    ).where(
                        canonical_replay_content_changes_table.c.all_request_id == request_id,
                        canonical_replay_content_changes_table.c.reverted_at.is_(None),
                    )
                )
                or 0
            )
        finally:
            session.close()

    def _reverse_batch(
        self,
        request_id: UUID,
        *,
        fence: JobExecutionFence,
    ) -> int:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                request = PostgresCanonicalReplayRepository(session).get_all_request(
                    request_id,
                    for_update=True,
                )
                if (
                    request is None
                    or not request.reversible
                    or request.lifecycle_status != "reverting"
                    or request.reversal_job_id != fence.job_id
                ):
                    raise LeaseLostError("Canonical Replay 撤回 Job 已不属于当前父请求")
                content_ids = tuple(
                    session.scalars(
                        select(canonical_replay_content_changes_table.c.content_id)
                        .where(
                            canonical_replay_content_changes_table.c.all_request_id == request_id,
                            canonical_replay_content_changes_table.c.reverted_at.is_(None),
                        )
                        .distinct()
                        .order_by(canonical_replay_content_changes_table.c.content_id)
                        .limit(_CONTENT_BATCH_SIZE)
                    )
                )
                if not content_ids:
                    return 0

                lifecycle = PostgresContentLifecycleRepository(session)
                vehicle_repository = PostgresVehicleCatalogRepository(session)
                brand_repository = PostgresBrandVehicleRepository(session)
                now = beijing_now()
                reverted = hidden = retained = skipped = restored_evidence = skipped_evidence = 0
                for content_id in content_ids:
                    rows = tuple(
                        session.execute(
                            select(canonical_replay_content_changes_table)
                            .where(
                                canonical_replay_content_changes_table.c.all_request_id
                                == request_id,
                                canonical_replay_content_changes_table.c.content_id == content_id,
                                canonical_replay_content_changes_table.c.reverted_at.is_(None),
                            )
                            .order_by(
                                canonical_replay_content_changes_table.c.created_at,
                                canonical_replay_content_changes_table.c.id,
                            )
                            .with_for_update()
                        ).mappings()
                    )
                    if not rows:
                        continue
                    current_state = session.execute(
                        select(
                            contents_table.c.current_version,
                            contents_table.c.replay_visibility_owner_id,
                        ).where(contents_table.c.id == content_id)
                    ).one()
                    current_before = cast(int, current_state.current_version)
                    owner = current_state.replay_visibility_owner_id
                    if owner != request_id:
                        # 后续普通导入或另一轮重筛已接管该内容时，当前、可见性和证据
                        # 都不再归属于本次重筛；只结清账本，避免撤回覆盖后续事实。
                        session.execute(
                            update(canonical_replay_content_changes_table)
                            .where(
                                canonical_replay_content_changes_table.c.all_request_id
                                == request_id,
                                canonical_replay_content_changes_table.c.content_id == content_id,
                                canonical_replay_content_changes_table.c.reverted_at.is_(None),
                            )
                            .values(
                                reverted_at=now,
                                reversal_version_no=current_before,
                            )
                        )
                        reverted += 1
                        retained += 1
                        skipped += 1
                        skipped_evidence += 2
                        continue
                    versions = lifecycle.apply_contributions(rows, revoked_at=now)
                    if not versions:
                        skipped += 1
                        continue
                    reversal_version = versions[0][1]
                    earliest = rows[0]
                    latest = rows[-1]
                    delta = earliest["delta"]
                    created_content = bool(
                        isinstance(delta, dict) and delta.get("created_content") is True
                    )
                    next_owner = (
                        request_id if created_content else earliest["visibility_owner_before"]
                    )
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
                    if evidence_safe:
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
                        vehicle_restored = brand_restored = False
                    restored_evidence += int(vehicle_restored) + int(brand_restored)
                    skipped_evidence += int(not vehicle_restored) + int(not brand_restored)
                    session.execute(
                        update(canonical_replay_content_changes_table)
                        .where(
                            canonical_replay_content_changes_table.c.all_request_id == request_id,
                            canonical_replay_content_changes_table.c.content_id == content_id,
                            canonical_replay_content_changes_table.c.reverted_at.is_(None),
                        )
                        .values(reverted_at=now, reversal_version_no=reversal_version)
                    )
                    reverted += 1

                session.execute(
                    update(canonical_replay_all_requests_table)
                    .where(canonical_replay_all_requests_table.c.id == request_id)
                    .values(
                        reverted_content_count=(
                            canonical_replay_all_requests_table.c.reverted_content_count + reverted
                        ),
                        hidden_content_count=(
                            canonical_replay_all_requests_table.c.hidden_content_count + hidden
                        ),
                        retained_content_count=(
                            canonical_replay_all_requests_table.c.retained_content_count + retained
                        ),
                        skipped_content_count=(
                            canonical_replay_all_requests_table.c.skipped_content_count + skipped
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
                )
                return len(content_ids)
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
        PostgresCanonicalReplayRepository(session).mark_reversal_failed(UUID(str(request_id)))


def _json_rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("Replay Evidence Snapshot 必须是对象数组")
    return [cast(dict[str, object], item) for item in value]


__all__ = [
    "PostgresCanonicalReplayReversalJobExecutor",
    "canonical_replay_job_terminal_callback",
    "canonical_replay_reversal_terminal_callback",
]
