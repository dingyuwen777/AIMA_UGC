"""Stage 8B Import / Keyword / Relevance HTTP Application Service。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import BinaryIO, cast
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.manual_ingestion import (
    PostgresProcessingImportBatchRepository,
)
from aima_ugc.adapters.persistence.postgres.relevance import (
    GlobalRelevanceUnavailable,
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.contracts.analysis import RelevanceSnapshotV1
from aima_ugc.contracts.http import (
    GlobalRelevanceConfigRequest,
    GlobalRelevanceConfigResponse,
    ImportBatchCreatedResponse,
    ImportBatchResponse,
    ImportJobResultResponse,
    ImportStage,
    ImportStatsResponse,
    JobStatusResponse,
    KeywordPackCreateRequest,
    KeywordPackKeywordCreateRequest,
    KeywordPackResponse,
    KeywordResponse,
)
from aima_ugc.modules.analysis import normalize_keyword_storage_text
from aima_ugc.modules.ingestion import ProcessingImportBatchRecord
from aima_ugc.modules.ingestion.http import (
    ImportConflict,
    ImportResourceNotFound,
    ImportUploadTooLarge,
    InvalidImportFile,
    RelevanceConfigurationError,
)
from aima_ugc.modules.ingestion.import_job import (
    IMPORT_JOB_MAX_ATTEMPTS,
    IMPORT_JOB_PAYLOAD_VERSION,
    IMPORT_JOB_TIMEOUT_SECONDS,
    IMPORT_JOB_TYPE,
    ImportJobPayload,
)
from aima_ugc.modules.ingestion.xlsx_security import (
    MAX_XLSX_FILE_BYTES,
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_stream,
)
from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.storage import ArtifactService, ArtifactSizeLimitError

from .runtime import PlatformRuntime

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_IMPORT_PROFILE = "aima-monitoring-excel.v1"


class PostgresImportHttpService:
    """Router 之后的事务、Artifact 与 Job 编排；不执行 Excel 长任务。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def create_import(
        self,
        *,
        filename: str,
        content_type: str | None,
        source: BinaryIO,
        request_id: str,
    ) -> ImportBatchCreatedResponse:
        del content_type
        safe_name = _validate_upload_filename(filename)
        snapshot, _ = self._read_relevance_snapshot()
        try:
            source.seek(0, 2)
            file_size = source.tell()
            source.seek(0)
            archive = validate_xlsx_stream(
                source,
                filename=safe_name,
                file_size=file_size,
            )
        except XlsxResourceLimitError as exc:
            raise ImportUploadTooLarge from exc
        except (InvalidXlsxError, OSError) as exc:
            raise InvalidImportFile from exc

        artifacts = ArtifactService(
            metadata=PostgresArtifactMetadataGateway(self._runtime.database.new_session),
            store=self._runtime.artifact_store,
        )
        try:
            source.seek(0)
            artifact = artifacts.store_stream(
                kind="file-import.raw",
                content_type=_XLSX_CONTENT_TYPE,
                retention_class="raw",
                source=source,
                max_bytes=MAX_XLSX_FILE_BYTES,
                filename_suffix=".xlsx",
            )
        except ArtifactSizeLimitError as exc:
            raise ImportUploadTooLarge from exc

        batch_id = uuid4()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).enqueue(
                    job_type=IMPORT_JOB_TYPE,
                    payload_version=IMPORT_JOB_PAYLOAD_VERSION,
                    payload=ImportJobPayload(
                        relevance=snapshot,
                    ).model_dump(mode="json"),
                    internal_idempotency_key=f"import-batch:{batch_id}",
                    request_id=request_id,
                    priority=0,
                    max_attempts=IMPORT_JOB_MAX_ATTEMPTS,
                    timeout_seconds=IMPORT_JOB_TIMEOUT_SECONDS,
                )
                PostgresProcessingImportBatchRepository(session).create(
                    batch_id=batch_id,
                    input_artifact_id=artifact.id,
                    job_id=job.id,
                    stats={
                        "stage": "queued",
                        "profile": _IMPORT_PROFILE,
                        "source_filename": safe_name,
                        "relevance": snapshot.model_dump(mode="json"),
                        "xlsx_member_count": archive.member_count,
                        "xlsx_total_uncompressed_bytes": archive.total_uncompressed_bytes,
                    },
                )
                PostgresArtifactMetadataRepository(session).mark_linked(
                    artifact.id,
                    linked_at=datetime.now(UTC),
                )
        finally:
            session.close()
        return ImportBatchCreatedResponse(batch_id=batch_id, job_id=job.id)

    def get_import_batch(self, batch_id: UUID) -> ImportBatchResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                batch = PostgresProcessingImportBatchRepository(session).get(batch_id)
                if batch is None or batch.job_id is None:
                    raise ImportResourceNotFound
                job = PostgresJobRepository(session).get(batch.job_id)
                if job is None:
                    raise ImportResourceNotFound
                return _batch_response(batch, job)
        finally:
            session.close()

    def get_job(self, job_id: UUID) -> JobStatusResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).get(job_id)
                if job is None or job.job_type != IMPORT_JOB_TYPE:
                    raise ImportResourceNotFound
                return _job_response(job)
        finally:
            session.close()

    def create_keyword_pack(self, request: KeywordPackCreateRequest) -> KeywordPackResponse:
        name = request.name.strip()
        if not name:
            raise ValueError("Keyword Pack 名称不能为空")
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                pack = PostgresKeywordCatalogRepository(session).create_pack(
                    KeywordPack(
                        id=uuid4(),
                        name=name,
                        description=request.description.strip(),
                        enabled=True,
                        version=1,
                    )
                )
                return _pack_response(PostgresKeywordCatalogRepository(session), pack)
        except IntegrityError as exc:
            raise ImportConflict from exc
        finally:
            session.close()

    def add_keyword(
        self,
        pack_id: UUID,
        request: KeywordPackKeywordCreateRequest,
    ) -> KeywordPackResponse:
        text = request.text.strip()
        try:
            normalized = normalize_keyword_storage_text(text)
        except ValueError as exc:
            raise ValueError("关键词不能为空") from exc
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresKeywordCatalogRepository(session)
                if repository.get_pack(pack_id) is None:
                    raise ImportResourceNotFound
                keyword = repository.get_or_create_keyword(
                    Keyword(
                        id=uuid4(),
                        text=text,
                        normalized_text=normalized,
                        enabled=True,
                    )
                )
                repository.add_item_if_missing(
                    KeywordPackItem(
                        pack_id=pack_id,
                        keyword_id=keyword.id,
                        platform="all",
                        priority=request.priority,
                        enabled=request.enabled,
                        note=request.note.strip(),
                    )
                )
                pack = repository.get_pack(pack_id)
                if pack is None:  # pragma: no cover - 持锁事务中的父记录不会消失
                    raise ImportResourceNotFound
                return _pack_response(repository, pack)
        finally:
            session.close()

    def get_keyword_pack(self, pack_id: UUID) -> KeywordPackResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresKeywordCatalogRepository(session)
                pack = repository.get_pack(pack_id)
                if pack is None:
                    raise ImportResourceNotFound
                return _pack_response(repository, pack)
        finally:
            session.close()

    def set_global_relevance(
        self,
        request: GlobalRelevanceConfigRequest,
    ) -> GlobalRelevanceConfigResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresGlobalRelevanceRepository(session)
                try:
                    repository.set(request.keyword_pack_id)
                    snapshot, updated_at = repository.snapshot()
                except LookupError as exc:
                    raise ImportResourceNotFound from exc
                except GlobalRelevanceUnavailable as exc:
                    raise RelevanceConfigurationError from exc
                return _relevance_response(snapshot, updated_at)
        finally:
            session.close()

    def get_global_relevance(self) -> GlobalRelevanceConfigResponse:
        snapshot, updated_at = self._read_relevance_snapshot()
        return _relevance_response(snapshot, updated_at)

    def _read_relevance_snapshot(self) -> tuple[RelevanceSnapshotV1, datetime]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                try:
                    return PostgresGlobalRelevanceRepository(session).snapshot()
                except GlobalRelevanceUnavailable as exc:
                    raise RelevanceConfigurationError from exc
        finally:
            session.close()


def _validate_upload_filename(filename: str) -> str:
    if (
        not filename
        or "\x00" in filename
        or ":" in filename
        or "/" in filename
        or "\\" in filename
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        or PurePosixPath(filename).name != filename
        or PureWindowsPath(filename).name != filename
        or not filename.casefold().endswith(".xlsx")
    ):
        raise InvalidImportFile
    return filename


def _pack_response(
    repository: PostgresKeywordCatalogRepository,
    pack: KeywordPack,
) -> KeywordPackResponse:
    return KeywordPackResponse(
        id=pack.id,
        name=pack.name,
        description=pack.description,
        enabled=pack.enabled,
        version=pack.version,
        keywords=tuple(
            KeywordResponse(
                id=keyword.id,
                text=keyword.text,
                platform=item.platform,
                enabled=keyword.enabled and item.enabled,
                priority=item.priority,
                note=item.note,
            )
            for keyword, item in repository.list_keywords_for_pack(pack.id)
        ),
    )


def _relevance_response(
    frozen: RelevanceSnapshotV1,
    updated_at: datetime,
) -> GlobalRelevanceConfigResponse:
    return GlobalRelevanceConfigResponse(
        keyword_pack_id=frozen.keyword_pack_id,
        keyword_pack_version=frozen.keyword_pack_version,
        version=frozen.config_version,
        effective_keywords=frozen.effective_keywords,
        updated_at=updated_at,
    )


def _job_response(job: JobRecord) -> JobStatusResponse:
    result: ImportJobResultResponse | None = None
    if isinstance(job.result, dict):
        batch_id = job.result.get("batch_id")
        rows_ingested = job.result.get("rows_ingested")
        if isinstance(batch_id, str) and isinstance(rows_ingested, int):
            result = ImportJobResultResponse(
                batch_id=UUID(batch_id),
                rows_ingested=rows_ingested,
            )
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


def _batch_response(batch: ProcessingImportBatchRecord, job: JobRecord) -> ImportBatchResponse:
    stage = batch.stats.get("stage", "queued")
    status = job.status
    if status == "succeeded":
        stage = "succeeded"
    elif status == "failed":
        stage = "failed"
    elif status == "cancelled":
        stage = "cancelled"
    return ImportBatchResponse(
        id=batch.id,
        input_artifact_id=batch.input_artifact_id,
        status=status,
        stage=cast(ImportStage, stage),
        stats=ImportStatsResponse(
            **{name: _stat(batch.stats, name) for name in ImportStatsResponse.model_fields}
        ),
        error_summary=batch.error_summary or job.error_code,
        created_at=batch.created_at,
        started_at=batch.started_at,
        finished_at=batch.finished_at or job.finished_at,
        job=_job_response(job),
    )


def _stat(stats: dict[str, object], name: str) -> int:
    value = stats.get(name, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


__all__ = ["PostgresImportHttpService"]
