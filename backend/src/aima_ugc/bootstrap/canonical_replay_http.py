"""Canonical Replay 的正式 PostgreSQL HTTP Application Service。"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import JsonValue, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.http import (
    CanonicalReplayCreatedResponse,
    CanonicalReplayCreateRequest,
    CanonicalReplayJobResultResponse,
    CanonicalReplayRunResponse,
    CanonicalReplayStatsResponse,
    JobStatusResponse,
)
from aima_ugc.modules.ingestion.canonical_replay import CanonicalReplayRunRecord
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
