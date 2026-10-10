"""Stage 8D Data Export HTTP Application Service。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import BinaryIO, cast
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.persistence.postgres.export_column_defaults import (
    PostgresExportColumnDefaultRepository,
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
from aima_ugc.contracts.product import ExportColumnDefaultResponse, ExportColumnDefaultUpdateRequest
from aima_ugc.modules.content.http import ContentSelectionEmpty
from aima_ugc.modules.identity import AuthorizationDenied, Principal
from aima_ugc.modules.reporting.column_catalog import (
    EXPORT_COLUMN_CATALOG_VERSION,
    resolve_export_columns,
)
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
    ExportColumnDefaultConflict,
    ExportColumnsInvalid,
)
from aima_ugc.modules.reporting.models import DataExportRecord
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.storage.retention import EXPORT_RETENTION
from aima_ugc.platform.time import beijing_now

from .analysis_identity import active_analysis_configuration
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
        principal: Principal,
    ) -> DataExportCreatedResponse:
        """授权列先于事务/Job，创建者只来自可信 Principal。"""
        columns = _resolve_columns(request.columns, principal)
        if not principal.principal_id.strip():
            raise AuthorizationDenied
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configuration = active_analysis_configuration(session, self._runtime.settings)
                target_request = request.targets
                content_queries = PostgresContentQueryRepository(
                    session,
                    analysis_identity=configuration.identity,
                )
                target_statement = (
                    content_queries.freeze_target_statement(filters=target_request.filters)
                    if target_request.scope == "query" and target_request.filters is not None
                    else content_queries.freeze_target_statement(filters=ContentFilterSnapshot())
                    if target_request.scope == "query"
                    else content_queries.freeze_target_statement(
                        content_ids=target_request.content_ids
                    )
                )
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
                    "requested_by": principal.principal_id,
                }
                target_count = PostgresDataExportRepository(session).create(
                    export_id=export_id,
                    job_id=job.id,
                    request_snapshot=snapshot,
                    created_by=principal.principal_id,
                    target_statement=target_statement,
                    columns=columns,
                    column_catalog_version=EXPORT_COLUMN_CATALOG_VERSION,
                )
                if target_count == 0:
                    raise ContentSelectionEmpty
                return DataExportCreatedResponse(
                    export_id=export_id,
                    job_id=job.id,
                    target_count=target_count,
                )
        finally:
            session.close()

    def get_export(self, export_id: UUID, *, principal: Principal) -> DataExportResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                export = PostgresDataExportRepository(session).get(
                    export_id,
                    created_by=_owner_filter(principal),
                )
                if export is None:
                    raise DataExportResourceNotFound
                job = PostgresJobRepository(session).get(export.job_id)
                if job is None or job.job_type != DATA_EXPORT_JOB_TYPE:
                    raise DataExportResourceNotFound
                return _export_response(export, job)
        finally:
            session.close()

    def list_exports(self, *, principal: Principal) -> DataExportListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresDataExportRepository(session)
                exports = repository.list_recent(created_by=_owner_filter(principal))
                jobs = PostgresJobRepository(session)
                responses: list[DataExportResponse] = []
                for export in exports:
                    job = jobs.get(export.job_id)
                    if job is not None and job.job_type == DATA_EXPORT_JOB_TYPE:
                        responses.append(_export_response(export, job))
                return DataExportListResponse(items=tuple(responses))
        finally:
            session.close()

    def download_export(self, export_id: UUID, *, principal: Principal) -> ArtifactDownload:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                export = PostgresDataExportRepository(session).get(
                    export_id,
                    created_by=_owner_filter(principal),
                )
                if export is None:
                    raise DataExportResourceNotFound
                job = PostgresJobRepository(session).get(export.job_id)
                # 历史文件也按当前角色核验冻结列，再获取 Artifact/大文件。
                try:
                    if principal.role != "administrator" and (
                        not export.columns or export.column_catalog_version < 3
                    ):
                        raise ValueError("历史文件没有可验证的全部工作表字段权限")
                    resolve_export_columns(
                        export.columns, administrator=principal.role == "administrator"
                    )
                except ValueError as exc:
                    raise AuthorizationDenied(
                        "当前账号不能下载包含内部定位字段的文件，请重新导出"
                    ) from exc
                if (
                    job is None
                    or job.job_type != DATA_EXPORT_JOB_TYPE
                    or job.status != "succeeded"
                    or export.artifact_id is None
                ):
                    raise DataExportNotReady
                artifact = PostgresArtifactMetadataRepository(session).get(export.artifact_id)
                if (
                    artifact is None
                    or artifact.storage_status != "linked"
                    or artifact.byte_size is None
                    or artifact.storage_backend != self._runtime.artifact_store.backend_name
                    or _export_expired(
                        export,
                        artifact.expires_at,
                        artifact.stored_at,
                        artifact.created_at,
                    )
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

    def get_column_default(self, principal: Principal) -> ExportColumnDefaultResponse:
        """投影当前有效列；降权或目录变更不写回原始保存记录。"""
        with self._runtime.database.new_session() as session:
            row = PostgresExportColumnDefaultRepository(session).get(principal.principal_id)
            return _column_default_response(row, principal)

    def save_column_default(
        self,
        request: ExportColumnDefaultUpdateRequest,
        *,
        principal: Principal,
    ) -> ExportColumnDefaultResponse:
        """目录与 revision 都必须匹配，恢复默认仍递增 revision。"""
        if request.catalog_version != EXPORT_COLUMN_CATALOG_VERSION:
            raise ExportColumnDefaultConflict
        if request.columns is not None:
            _resolve_columns(request.columns, principal)
        with self._runtime.database.new_session() as session, session.begin():
            row = PostgresExportColumnDefaultRepository(session).save(
                principal.principal_id,
                revision=request.revision,
                columns=request.columns,
                catalog_version=request.catalog_version,
            )
            return _column_default_response(row, principal)


def _owner_filter(principal: Principal) -> str | None:
    """管理员全局查询；普通用户在 SQL 中先按可信身份过滤。"""
    return None if principal.role == "administrator" else principal.principal_id


def _resolve_columns(columns: tuple[str, ...], principal: Principal) -> tuple[str, ...]:
    """把列目录领域拒绝翻译为现有 422 错误边界。"""
    try:
        return resolve_export_columns(columns, administrator=principal.role == "administrator")
    except ValueError as exc:
        raise ExportColumnsInvalid from exc


def _column_default_response(row: object, principal: Principal) -> ExportColumnDefaultResponse:
    """有效自定义组合不吸收新增列；全部失效时返回空投影供 UI 提示回退。"""
    from sqlalchemy.engine import RowMapping

    from aima_ugc.modules.reporting.column_catalog import EXPORT_COLUMNS

    if row is None:
        return ExportColumnDefaultResponse(
            revision=0,
            columns=None,
            saved_catalog_version=None,
            updated_at=None,
        )
    saved = cast(RowMapping, row)
    allowed = {
        item.key
        for item in EXPORT_COLUMNS
        if principal.role == "administrator" or not item.administrator_only
    }
    selected = saved["selected_columns"]
    return ExportColumnDefaultResponse(
        revision=saved["revision"],
        columns=tuple(key for key in selected if key in allowed) if selected is not None else None,
        saved_catalog_version=saved["saved_catalog_version"],
        updated_at=saved["updated_at"],
    )


def _export_expired(
    export: DataExportRecord,
    expires_at: datetime | None,
    stored_at: datetime | None,
    created_at: datetime,
) -> bool:
    """即使历史 Artifact 尚未被 Scheduler 回填 expires_at，也按 7 天规则拒绝下载。"""

    if expires_at is None:
        base_at = export.completed_at or stored_at or created_at
        expires_at = base_at + EXPORT_RETENTION
    return expires_at <= beijing_now()


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
        columns=export.columns,
        column_catalog_version=export.column_catalog_version,
    )


__all__ = ["PostgresReportingHttpService"]
