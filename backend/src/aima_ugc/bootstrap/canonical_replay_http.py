"""Canonical Replay 的正式 PostgreSQL HTTP Application Service。"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import JsonValue, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.http import (
    CanonicalReplayAllCreatedResponse,
    CanonicalReplayAllCreateRequest,
    CanonicalReplayAllOperationResponse,
    CanonicalReplayCreatedResponse,
    CanonicalReplayCreateRequest,
    CanonicalReplayJobResultResponse,
    CanonicalReplayRunResponse,
    CanonicalReplayStatsResponse,
    JobStatusResponse,
)
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_ARTIFACTS_PER_RUN,
    CANONICAL_REPLAY_FAST_BATCH_SIZE,
    CanonicalReplayAllRequestRecord,
    CanonicalReplayRunRecord,
)
from aima_ugc.modules.ingestion.canonical_replay_http import (
    CanonicalReplayConflict,
    CanonicalReplayInputInvalid,
    CanonicalReplayResourceNotFound,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.jobs import JobIdempotencyConflict, JobRecord
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime


class PostgresCanonicalReplayHttpService:
    """用短事务创建/查询/取消 Replay，不在 API 内扫描 Artifact。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def create_all_replays(
        self,
        body: CanonicalReplayAllCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllCreatedResponse:
        """短事务冻结点击时目录与受理边界，只排队 Planner 后立即返回。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCanonicalReplayRepository(session)
                try:
                    catalog = PostgresBrandVehicleRepository(session).snapshot(brand_ids=None)
                    snapshot = BrandVehicleFilterSnapshot(catalog=catalog)
                    record, _planner = repository.enqueue_all_request(
                        idempotency_key=body.idempotency_key,
                        created_by=actor_ref,
                        request_id=request_id,
                        filter_snapshot=snapshot,
                    )
                    planning_status = repository.planning_status(record)
                except (LookupError, ValueError) as exc:
                    raise CanonicalReplayInputInvalid(str(exc)) from exc
                except (JobIdempotencyConflict, RuntimeError) as exc:
                    raise CanonicalReplayConflict(str(exc)) from exc
                _audit(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="canonical_replay_all_requested",
                    object_id=str(record.id),
                    detail={
                        "planning_status": planning_status,
                        "artifact_count": record.artifact_count,
                        "run_count": record.run_count,
                        "artifacts_per_run": record.artifacts_per_run,
                        "batch_size": record.batch_size,
                    },
                )
                return CanonicalReplayAllCreatedResponse(
                    request_id=record.id,
                    planning_status=planning_status,
                    artifact_count=record.artifact_count,
                    run_count=record.run_count,
                    artifacts_per_run=CANONICAL_REPLAY_ARTIFACTS_PER_RUN,
                    batch_size=CANONICAL_REPLAY_FAST_BATCH_SIZE,
                )
        except IntegrityError as exc:
            raise CanonicalReplayConflict from exc
        finally:
            session.close()

    def create_replay(
        self,
        body: CanonicalReplayCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayCreatedResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCanonicalReplayRepository(session)
                try:
                    run, job = repository.enqueue(
                        idempotency_key=body.idempotency_key,
                        artifact_ids=body.artifact_ids,
                        brand_ids=body.brand_ids,
                        batch_size=body.batch_size,
                        created_by=actor_ref,
                        request_id=request_id,
                    )
                except (LookupError, ValueError) as exc:
                    raise CanonicalReplayInputInvalid(str(exc)) from exc
                except (JobIdempotencyConflict, RuntimeError) as exc:
                    raise CanonicalReplayConflict(str(exc)) from exc
                _audit(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="canonical_replay_created",
                    object_id=str(run.id),
                    detail={
                        "job_id": str(job.id),
                        "artifact_count": run.artifact_count,
                        "catalog_version": run.filter_snapshot.catalog.catalog_version,
                    },
                )
                return CanonicalReplayCreatedResponse(
                    run_id=run.id,
                    job_id=job.id,
                    status=job.status,
                )
        except IntegrityError as exc:
            raise CanonicalReplayConflict from exc
        finally:
            session.close()

    def get_replay(self, run_id: UUID) -> CanonicalReplayRunResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return _load_response(session, run_id)
        finally:
            session.close()

    def cancel_replay(
        self,
        run_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayRunResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCanonicalReplayRepository(session)
                try:
                    job = repository.request_cancel(run_id)
                except LookupError as exc:
                    raise CanonicalReplayResourceNotFound from exc
                _audit(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="canonical_replay_cancel_requested",
                    object_id=str(run_id),
                    detail={"job_id": str(job.id), "job_status": job.status},
                )
                return _load_response(session, run_id)
        finally:
            session.close()

    def cancel_and_revoke_all(
        self,
        replay_request_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllOperationResponse:
        """协作取消全部活动子 Job，并在其终态后异步精确撤回。"""

        return self._request_all_reversal(
            replay_request_id,
            cancel_active=True,
            actor_ref=actor_ref,
            request_id=request_id,
        )

    def revoke_all(
        self,
        replay_request_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllOperationResponse:
        """对已结束的全量 Replay 排队异步精确撤回。"""

        return self._request_all_reversal(
            replay_request_id,
            cancel_active=False,
            actor_ref=actor_ref,
            request_id=request_id,
        )

    def _request_all_reversal(
        self,
        replay_request_id: UUID,
        *,
        cancel_active: bool,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllOperationResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCanonicalReplayRepository(session)
                try:
                    record = repository.request_all_reversal(
                        replay_request_id,
                        cancel_active=cancel_active,
                        actor_ref=actor_ref,
                        http_request_id=request_id,
                    )
                except LookupError as exc:
                    raise CanonicalReplayResourceNotFound from exc
                except (JobIdempotencyConflict, RuntimeError, ValueError) as exc:
                    raise CanonicalReplayConflict(str(exc)) from exc
                _audit(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type=(
                        "canonical_replay_cancel_and_revoke_requested"
                        if cancel_active
                        else "canonical_replay_revoke_requested"
                    ),
                    object_id=str(record.id),
                    detail={
                        "lifecycle_status": record.lifecycle_status,
                        "reversal_job_id": (
                            str(record.reversal_job_id)
                            if record.reversal_job_id is not None
                            else None
                        ),
                    },
                )
                return _operation_response(record)
        except IntegrityError as exc:
            raise CanonicalReplayConflict from exc
        finally:
            session.close()


def _load_response(session: Session, run_id: UUID) -> CanonicalReplayRunResponse:
    repository = PostgresCanonicalReplayRepository(session)
    run = repository.get(run_id)
    job = repository.get_job(run_id)
    if run is None or job is None:
        raise CanonicalReplayResourceNotFound
    return _run_response(
        run,
        artifact_ids=tuple(item.artifact_id for item in repository.list_artifacts(run.id)),
        job=job,
    )


def _run_response(
    run: CanonicalReplayRunRecord,
    *,
    artifact_ids: tuple[UUID, ...],
    job: JobRecord,
) -> CanonicalReplayRunResponse:
    return CanonicalReplayRunResponse(
        id=run.id,
        artifact_ids=artifact_ids,
        filter_scope="selected" if run.requested_brand_ids else "all_active",
        brand_ids=run.requested_brand_ids,
        catalog_version=run.filter_snapshot.catalog.catalog_version,
        artifact_count=run.artifact_count,
        checkpoint_artifact_ordinal=run.checkpoint_artifact_ordinal,
        checkpoint_row_number=run.checkpoint_row_number,
        batch_size=run.batch_size,
        stats=CanonicalReplayStatsResponse(
            rows_seen=run.rows_seen,
            rows_matched=run.rows_matched,
            rows_filtered_out=run.rows_filtered_out,
            duplicates_removed=run.duplicates_removed,
            rows_ingested=run.rows_ingested,
            existing_convergence=run.existing_convergence,
        ),
        job=_job_response(job),
        created_by=run.created_by,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _job_response(job: JobRecord) -> JobStatusResponse:
    result = None
    if isinstance(job.result, dict):
        try:
            result = CanonicalReplayJobResultResponse.model_validate(job.result)
        except ValidationError:
            result = None
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        progress=job.progress,
        error_code=job.error_code,
        result=result,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _operation_response(
    record: CanonicalReplayAllRequestRecord,
) -> CanonicalReplayAllOperationResponse:
    return CanonicalReplayAllOperationResponse(
        request_id=record.id,
        lifecycle_status=record.lifecycle_status,
        reversible=record.reversible,
        reversal_job_id=record.reversal_job_id,
        cancellation_requested_at=record.cancellation_requested_at,
        reversal_requested_at=record.reversal_requested_at,
        reversed_at=record.reversed_at,
    )


def _audit(
    session: Session,
    *,
    actor_ref: str,
    request_id: str,
    event_type: str,
    object_id: str,
    detail: dict[str, JsonValue],
) -> None:
    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=actor_ref,
            event_type=event_type,
            object_type="canonical_replay_run",
            object_id=object_id,
            request_id=request_id,
            safe_detail=detail,
            created_at=beijing_now(),
        )
    )


__all__ = ["PostgresCanonicalReplayHttpService"]
