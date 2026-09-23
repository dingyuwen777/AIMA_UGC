"""管理员飞书发布 HTTP Application Service。"""

from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath, PureWindowsPath
from typing import BinaryIO, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.feishu_publication import (
    FeishuPublicationCreatedResponse,
    FeishuPublicationJobResponse,
    FeishuPublicationKind,
    FeishuPublicationResult,
    FeishuReportPublicationResult,
    FeishuRepresentativeSelectionResult,
)
from aima_ugc.modules.administration.feishu_publication_jobs import (
    FEISHU_PUBLICATION_MAX_ATTEMPTS,
    FEISHU_PUBLICATION_TIMEOUT_SECONDS,
    FEISHU_REPORT_PUBLICATION_JOB_TYPE,
    FEISHU_REPORT_PUBLICATION_PAYLOAD_VERSION,
    FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE,
    FEISHU_REPRESENTATIVE_SELECTION_PAYLOAD_VERSION,
    FeishuReportPublicationJobPayload,
    FeishuRepresentativeSelectionJobPayload,
)
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.ingestion.xlsx_security import (
    MAX_XLSX_FILE_BYTES,
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_stream,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.storage import ArtifactService, ArtifactSizeLimitError
from aima_ugc.platform.storage.models import ArtifactRecord
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_FEISHU_INPUT_ARTIFACT_KIND = "feishu-publication.input"
_SUPPORTED_JOB_TYPES = frozenset(
    {FEISHU_REPORT_PUBLICATION_JOB_TYPE, FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE}
)


class FeishuPublicationResourceNotFound(LookupError):
    """管理员发布 Job 不存在或不是允许查询的发布 Job。"""


class FeishuPublicationInvalidRequest(ValueError):
    """管理员发布请求字段不合法。"""


class FeishuPublicationUploadTooLarge(ValueError):
    """管理员发布上传文件超过 XLSX 安全上限。"""


class FeishuPublicationInvalidFile(ValueError):
    """管理员发布上传文件不是安全的 XLSX。"""


class FeishuPublicationHttpService(Protocol):
    def create_report_publication(
        self,
        *,
        current_filename: str,
        current_source: BinaryIO,
        previous_filename: str,
        previous_source: BinaryIO,
        start_date: str,
        end_date: str,
        principal: Principal,
        request_id: str,
    ) -> FeishuPublicationCreatedResponse: ...

    def create_representative_selection(
        self,
        *,
        filename: str,
        source: BinaryIO,
        principal: Principal,
        request_id: str,
    ) -> FeishuPublicationCreatedResponse: ...

    def get_job(self, job_id: UUID) -> FeishuPublicationJobResponse: ...


class PostgresFeishuPublicationHttpService:
    """只负责上传暂存、Job 入队与查询，不在请求线程执行飞书长任务。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def create_report_publication(
        self,
        *,
        current_filename: str,
        current_source: BinaryIO,
        previous_filename: str,
        previous_source: BinaryIO,
        start_date: str,
        end_date: str,
        principal: Principal,
        request_id: str,
    ) -> FeishuPublicationCreatedResponse:
        principal.require_administrator()
        actual_start, actual_end = _parse_date_range(start_date, end_date)
        current_name = _validate_filename(current_filename)
        previous_name = _validate_filename(previous_filename)
        current_artifact = self._store_xlsx(current_name, current_source)
        previous_artifact = self._store_xlsx(previous_name, previous_source)
        payload = FeishuReportPublicationJobPayload(
            input_artifact_id=current_artifact.id,
            previous_input_artifact_id=previous_artifact.id,
            input_filename=current_name,
            previous_input_filename=previous_name,
            start_date=actual_start,
            end_date=actual_end,
            dry_run=self._runtime.settings.feishu_dry_run,
        )
        with self._runtime.database.new_session() as session:
            with session.begin():
                job = PostgresJobRepository(session).enqueue(
                    job_type=FEISHU_REPORT_PUBLICATION_JOB_TYPE,
                    payload_version=FEISHU_REPORT_PUBLICATION_PAYLOAD_VERSION,
                    payload=payload.model_dump(mode="json"),
                    internal_idempotency_key=f"feishu-report-publication:{uuid4()}",
                    request_id=request_id,
                    priority=0,
                    max_attempts=FEISHU_PUBLICATION_MAX_ATTEMPTS,
                    timeout_seconds=FEISHU_PUBLICATION_TIMEOUT_SECONDS,
                )
                PostgresArtifactMetadataRepository(session).mark_linked(
                    current_artifact.id,
                    linked_at=beijing_now(),
                )
                PostgresArtifactMetadataRepository(session).mark_linked(
                    previous_artifact.id,
                    linked_at=beijing_now(),
                )
                _append_audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    job=job,
                    kind="report",
                    detail={
                        "input_filename": current_name,
                        "previous_input_filename": previous_name,
                        "start_date": actual_start.isoformat(),
                        "end_date": actual_end.isoformat(),
                    },
                )
        return FeishuPublicationCreatedResponse(job_id=job.id, kind="report")

    def create_representative_selection(
        self,
        *,
        filename: str,
        source: BinaryIO,
        principal: Principal,
        request_id: str,
    ) -> FeishuPublicationCreatedResponse:
        principal.require_administrator()
        safe_name = _validate_filename(filename)
        artifact = self._store_xlsx(safe_name, source)
        payload = FeishuRepresentativeSelectionJobPayload(
            input_artifact_id=artifact.id,
            input_filename=safe_name,
        )
        with self._runtime.database.new_session() as session:
            with session.begin():
                job = PostgresJobRepository(session).enqueue(
                    job_type=FEISHU_REPRESENTATIVE_SELECTION_JOB_TYPE,
                    payload_version=FEISHU_REPRESENTATIVE_SELECTION_PAYLOAD_VERSION,
                    payload=payload.model_dump(mode="json"),
                    internal_idempotency_key=f"feishu-representative-selection:{uuid4()}",
                    request_id=request_id,
                    priority=0,
                    max_attempts=FEISHU_PUBLICATION_MAX_ATTEMPTS,
                    timeout_seconds=FEISHU_PUBLICATION_TIMEOUT_SECONDS,
                )
                PostgresArtifactMetadataRepository(session).mark_linked(
                    artifact.id,
                    linked_at=beijing_now(),
                )
                _append_audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    job=job,
                    kind="representative_selection",
                    detail={"input_filename": safe_name},
                )
        return FeishuPublicationCreatedResponse(job_id=job.id, kind="representative_selection")

    def get_job(self, job_id: UUID) -> FeishuPublicationJobResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).get(job_id)
        finally:
            session.close()
        if job is None or job.job_type not in _SUPPORTED_JOB_TYPES:
            raise FeishuPublicationResourceNotFound
        return _job_response(job)

    def _store_xlsx(self, filename: str, source: BinaryIO) -> ArtifactRecord:
        try:
            source.seek(0, 2)
            file_size = source.tell()
            source.seek(0)
            validate_xlsx_stream(source, filename=filename, file_size=file_size)
            source.seek(0)
            return ArtifactService(
                metadata=PostgresArtifactMetadataGateway(self._runtime.database.new_session),
                store=self._runtime.artifact_store,
            ).store_stream(
                kind=_FEISHU_INPUT_ARTIFACT_KIND,
                content_type=_XLSX_CONTENT_TYPE,
                retention_class="feishu-publication-input",
                source=source,
                max_bytes=MAX_XLSX_FILE_BYTES,
                filename_suffix=".xlsx",
            )
        except XlsxResourceLimitError as exc:
            raise FeishuPublicationUploadTooLarge from exc
        except ArtifactSizeLimitError as exc:
            raise FeishuPublicationUploadTooLarge from exc
        except (InvalidXlsxError, OSError, ValueError) as exc:
            if isinstance(exc, FeishuPublicationInvalidRequest):
                raise
            raise FeishuPublicationInvalidFile from exc


def _parse_date_range(start_date: str, end_date: str) -> tuple[date, date]:
    start_text = start_date.strip()
    end_text = end_date.strip()
    if not start_text or not end_text:
        raise FeishuPublicationInvalidRequest("开始日期和结束日期必须填写")
    try:
        actual_start = date.fromisoformat(start_text)
        actual_end = date.fromisoformat(end_text)
    except ValueError as exc:
        raise FeishuPublicationInvalidRequest("日期必须使用 YYYY-MM-DD 格式") from exc
    if actual_start.isoformat() != start_text or actual_end.isoformat() != end_text:
        raise FeishuPublicationInvalidRequest("日期必须使用 YYYY-MM-DD 格式")
    if actual_start > actual_end:
        raise FeishuPublicationInvalidRequest("开始日期不能晚于结束日期")
    return actual_start, actual_end


def _validate_filename(filename: str) -> str:
    if (
        not filename
        or "\x00" in filename
        or ":" in filename
        or "/" in filename
        or "\\" in filename
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        or PurePosixPath(filename).name != filename
        or PureWindowsPath(filename).name != filename
        or len(filename) > 255
        or not filename.casefold().endswith(".xlsx")
    ):
        raise FeishuPublicationInvalidFile
    return filename


def _append_audit(
    session: Session,
    *,
    principal: Principal,
    request_id: str,
    job: JobRecord,
    kind: str,
    detail: dict[str, JsonValue],
) -> None:
    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=principal.principal_id,
            event_type="feishu_publication_job_created",
            object_type=kind,
            object_id=str(job.id),
            request_id=request_id,
            safe_detail=detail,
            created_at=beijing_now(),
        )
    )


def _job_response(job: JobRecord) -> FeishuPublicationJobResponse:
    payload: FeishuReportPublicationJobPayload | FeishuRepresentativeSelectionJobPayload
    source_filenames: tuple[str, ...]
    if job.job_type == FEISHU_REPORT_PUBLICATION_JOB_TYPE:
        payload = FeishuReportPublicationJobPayload.model_validate(job.payload)
        kind: FeishuPublicationKind = "report"
        source_filenames = (payload.input_filename, payload.previous_input_filename)
        result_kind: Literal["report", "representative_selection"] = "report"
    else:
        payload = FeishuRepresentativeSelectionJobPayload.model_validate(job.payload)
        kind = "representative_selection"
        source_filenames = (payload.input_filename,)
        result_kind = "representative_selection"
    result: FeishuPublicationResult | None = None
    if isinstance(job.result, dict):
        try:
            result = (
                FeishuReportPublicationResult.model_validate(job.result)
                if result_kind == "report"
                else FeishuRepresentativeSelectionResult.model_validate(job.result)
            )
        except ValueError:
            result = None
    return FeishuPublicationJobResponse(
        id=job.id,
        kind=kind,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        progress=job.progress,
        error_code=job.error_code,
        source_filenames=source_filenames,
        result=result,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


__all__ = [
    "FeishuPublicationHttpService",
    "FeishuPublicationInvalidFile",
    "FeishuPublicationInvalidRequest",
    "FeishuPublicationResourceNotFound",
    "FeishuPublicationUploadTooLarge",
    "PostgresFeishuPublicationHttpService",
]
