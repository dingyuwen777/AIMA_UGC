"""Stage 8D Data Export HTTP Application Service。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import BinaryIO
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.reporting import PostgresDataExportRepository
from aima_ugc.contracts.http import (
    ContentFilterSnapshot,
    DataExportCreatedResponse,
    DataExportJobResultResponse,
    DataExportListResponse,
    DataExportResponse,
    DataExportStatsResponse,
    DataExportSubmitRequest,
    JobStatusResponse,
)
from aima_ugc.modules.content.http import ContentSelectionEmpty
from aima_ugc.modules.reporting.data_export_job import (
    DATA_EXPORT_JOB_MAX_ATTEMPTS,
    DATA_EXPORT_JOB_PAYLOAD_VERSION,
    DATA_EXPORT_JOB_TIMEOUT_SECONDS,
    DATA_EXPORT_JOB_TYPE,
    DataExportJobPayload,
)
from aima_ugc.modules.reporting.http import (
    ArtifactDownload,
    DataExportNotReady,
    DataExportResourceNotFound,
)
from aima_ugc.modules.reporting.models import DataExportRecord
from aima_ugc.platform.jobs import JobRecord

from .analysis_identity import current_analysis_identity
from .runtime import PlatformRuntime

_DOWNLOAD_CHUNK_BYTES = 1024 * 1024


class PostgresReportingHttpService:
    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def create_export(
        self,
        request: DataExportSubmitRequest,
        *,
        request_id: str,
    ) -> DataExportCreatedResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                target_request = request.targets
                content_queries = PostgresContentQueryRepository(
                    session,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                )
                targets = (
                    content_queries.freeze_targets(filters=target_request.filters)
                    if target_request.scope == "query" and target_request.filters is not None
                    else content_queries.freeze_targets(filters=ContentFilterSnapshot())
                    if target_request.scope == "query"
                    else content_queries.freeze_targets(content_ids=target_request.content_ids)
                )
                if not targets:
                    raise ContentSelectionEmpty
                export_id = uuid4()
                job = PostgresJobRepository(session).enqueue(
                    job_type=DATA_EXPORT_JOB_TYPE,
                    payload_version=DATA_EXPORT_JOB_PAYLOAD_VERSION,
                    payload=DataExportJobPayload(export_id=export_id).model_dump(mode="json"),
                    internal_idempotency_key=f"content-export:{export_id}",
                    request_id=request_id,
                    priority=0,
                    max_attempts=DATA_EXPORT_JOB_MAX_ATTEMPTS,
                    timeout_seconds=DATA_EXPORT_JOB_TIMEOUT_SECONDS,
                )
                snapshot: dict[str, object] = {
                    "scope": target_request.scope,
                    "target_count": len(targets),
                    "filters": (
                        target_request.filters.model_dump(mode="json", exclude_none=True)
                        if target_request.filters is not None
                        else None
                    ),
                    "content_ids": (
                        [str(item) for item in target_request.content_ids]
                        if target_request.content_ids
                        else []
                    ),
                }
                PostgresDataExportRepository(session).create(
                    export_id=export_id,
                    job_id=job.id,
                    request_snapshot=snapshot,
                    targets=targets,
                )
                return DataExportCreatedResponse(
                    export_id=export_id,
                    job_id=job.id,
                    target_count=len(targets),
                )
        finally:
            session.close()

    def get_export(self, export_id: UUID) -> DataExportResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                export = PostgresDataExportRepository(session).get(export_id)
                if export is None:
                    raise DataExportResourceNotFound
                job = PostgresJobRepository(session).get(export.job_id)
                if job is None or job.job_type != DATA_EXPORT_JOB_TYPE:
                    raise DataExportResourceNotFound
                return _export_response(export, job)
        finally:
            session.close()

    def list_exports(self) -> DataExportListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresDataExportRepository(session)
                exports = repository.list_recent()
                jobs = PostgresJobRepository(session)
                responses: list[DataExportResponse] = []
                for export in exports:
                    job = jobs.get(export.job_id)
                    if job is not None and job.job_type == DATA_EXPORT_JOB_TYPE:
                        responses.append(_export_response(export, job))
                return DataExportListResponse(items=tuple(responses))
        finally:
            session.close()

    def download_export(self, export_id: UUID) -> ArtifactDownload:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                export = PostgresDataExportRepository(session).get(export_id)
                if export is None:
                    raise DataExportResourceNotFound
                job = PostgresJobRepository(session).get(export.job_id)
                if job is None or job.status != "succeeded" or export.artifact_id is None:
                    raise DataExportNotReady
                artifact = PostgresArtifactMetadataRepository(session).get(export.artifact_id)
                if (
                    artifact is None
                    or artifact.storage_status != "linked"
                    or artifact.byte_size is None
                    or artifact.storage_backend != self._runtime.artifact_store.backend_name
                ):
                    raise DataExportNotReady
                stream = self._runtime.artifact_store.open_read(artifact.storage_key)
                return ArtifactDownload(
                    content_type=artifact.content_type,
                    filename=f"aima-ugc-voice-plaza-{export.id}.xlsx",
                    byte_size=artifact.byte_size,
                    chunks=_iter_file(stream),
                )
        finally:
            session.close()


def _iter_file(stream: BinaryIO) -> Iterator[bytes]:
    try:
        while chunk := stream.read(_DOWNLOAD_CHUNK_BYTES):
            yield chunk
    finally:
        stream.close()


def _export_response(export: DataExportRecord, job: JobRecord) -> DataExportResponse:
    result = (
        DataExportJobResultResponse.model_validate(job.result)
        if isinstance(job.result, dict)
        else None
    )
    job_response = JobStatusResponse(
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
    stats = (
        DataExportStatsResponse.model_validate(export.stats) if export.stats is not None else None
    )
    return DataExportResponse(
        id=export.id,
        job=job_response,
        artifact_id=export.artifact_id,
        filename=(
            f"aima-ugc-voice-plaza-{export.id}.xlsx" if export.artifact_id is not None else None
        ),
        stats=stats,
        created_at=export.created_at,
        completed_at=export.completed_at,
    )


__all__ = ["PostgresReportingHttpService"]
