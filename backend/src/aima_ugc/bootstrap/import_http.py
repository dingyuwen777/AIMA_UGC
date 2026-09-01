"""Stage 8B Import / Keyword / Relevance HTTP Application Service。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath, PureWindowsPath
from typing import BinaryIO, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.import_batch_queries import (
    PostgresImportBatchQueryRepository,
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
from aima_ugc.adapters.persistence.postgres.scheduled_keywords import (
    MissingScheduledKeywordPackError,
    PostgresScheduledKeywordSnapshotReader,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.contracts.analysis import RelevanceSnapshotV1
from aima_ugc.contracts.http import (
    GlobalRelevanceConfigRequest,
    GlobalRelevanceConfigResponse,
    ImportBatchCreatedResponse,
    ImportBatchListQuery,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportBatchStatus,
    ImportBatchSummaryResponse,
    ImportJobResultResponse,
    ImportStage,
    ImportStatsResponse,
    JobStatusResponse,
    KeywordPackCreateRequest,
    KeywordPackKeywordCreateRequest,
    KeywordPackResponse,
    KeywordResponse,
)
from aima_ugc.modules.analysis import (
    RelevanceKeyword,
    RelevanceService,
    normalize_keyword_storage_text,
)
from aima_ugc.modules.ingestion import ProcessingImportBatchRecord
from aima_ugc.modules.ingestion.http import (
    ImportConflict,
    ImportCursorUnavailable,
    ImportResourceNotFound,
    ImportUploadTooLarge,
    InvalidImportFile,
    RelevanceConfigurationError,
)
from aima_ugc.modules.ingestion.import_batch_cursor import (
    ImportBatchCursorCodec,
    ImportBatchCursorPosition,
)
from aima_ugc.modules.ingestion.import_job import (
    IMPORT_JOB_MAX_ATTEMPTS,
    IMPORT_JOB_PAYLOAD_VERSION,
    IMPORT_JOB_TIMEOUT_SECONDS,
    IMPORT_JOB_TYPE,
    ImportJobPayload,
    ImportKeywordPackSnapshot,
    ImportKeywordSelectionSnapshot,
    ImportVehicleModelSnapshot,
)
from aima_ugc.modules.ingestion.query import ImportBatchReadQuery, ImportBatchReadRecord
from aima_ugc.modules.ingestion.xlsx_security import (
    MAX_XLSX_FILE_BYTES,
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_stream,
)
from aima_ugc.modules.system.models import AuditEvent, Keyword, KeywordPack, KeywordPackItem
from aima_ugc.platform.jobs import JobRecord
from aima_ugc.platform.security import SecretFileError, read_secret_file
from aima_ugc.platform.storage import ArtifactService, ArtifactSizeLimitError
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_IMPORT_PROFILE = "aima-monitoring-excel.v1"
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def read_import_keyword_selection(
    runtime: PlatformRuntime,
    keyword_pack_ids: tuple[UUID, ...],
    vehicle_model_ids: tuple[UUID, ...] = (),
) -> ImportKeywordSelectionSnapshot:
    """复用正式目录读取链，冻结 Import/Historical Campaign 的资源选择。"""

    if (not keyword_pack_ids and not vehicle_model_ids) or len(keyword_pack_ids) > 20:
        raise RelevanceConfigurationError
    if len(keyword_pack_ids) != len(set(keyword_pack_ids)):
        raise RelevanceConfigurationError
    if len(vehicle_model_ids) > 100 or len(vehicle_model_ids) != len(set(vehicle_model_ids)):
        raise RelevanceConfigurationError
    session = runtime.database.new_session()
    try:
        with session.begin():
            try:
                catalog = PostgresScheduledKeywordSnapshotReader(session).read(keyword_pack_ids)
            except (MissingScheduledKeywordPackError, ValueError) as exc:
                raise RelevanceConfigurationError from exc
            if any(not pack.enabled for pack in catalog.keyword_packs):
                raise RelevanceConfigurationError
            if keyword_pack_ids:
                configured = tuple(
                    RelevanceKeyword(text=entry.keyword_text, priority=entry.priority)
                    for entry in catalog.entries
                    if entry.pack_enabled and entry.keyword_enabled and entry.item_enabled
                )
                try:
                    effective = RelevanceService(configured).effective_keywords
                except ValueError as exc:
                    raise RelevanceConfigurationError from exc
            else:
                effective = ()
            try:
                vehicle_snapshot = PostgresVehicleCatalogRepository(session).snapshot(
                    vehicle_model_ids
                )
            except LookupError as exc:
                raise RelevanceConfigurationError from exc
            aliases_by_model: dict[UUID, list[str]] = {
                model_id: [] for model_id in vehicle_model_ids
            }
            for model_id, alias in vehicle_snapshot.alias_bindings:
                aliases_by_model[model_id].append(alias)
            versions = dict(vehicle_snapshot.vehicle_versions)
            return ImportKeywordSelectionSnapshot(
                keyword_packs=tuple(
                    ImportKeywordPackSnapshot(id=pack.pack_id, version=pack.version)
                    for pack in catalog.keyword_packs
                ),
                effective_keywords=effective,
                vehicle_catalog_version=vehicle_snapshot.catalog_version,
                vehicle_models=tuple(
                    ImportVehicleModelSnapshot(
                        id=model_id,
                        version=versions[model_id],
                        aliases=tuple(aliases_by_model[model_id]),
                    )
                    for model_id in vehicle_model_ids
                ),
            )
    finally:
        session.close()


class PostgresImportHttpService:
    """Router 之后的事务、Artifact 与 Job 编排；不执行 Excel 长任务。"""

    def __init__(
        self,
        runtime: PlatformRuntime,
        *,
        cursor_signing_secret: bytes | None = None,
    ) -> None:
        self._runtime = runtime
        self._cursor_signing_secret = cursor_signing_secret

    def create_import(
        self,
        *,
        filename: str,
        content_type: str | None,
        source: BinaryIO,
        keyword_pack_ids: tuple[UUID, ...],
        vehicle_model_ids: tuple[UUID, ...] = (),
        request_id: str,
    ) -> ImportBatchCreatedResponse:
        del content_type
        safe_name = _validate_upload_filename(filename)
        selection = self._read_import_keyword_selection(keyword_pack_ids, vehicle_model_ids)
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
                        keyword_selection=selection,
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
                        "keyword_selection": selection.model_dump(mode="json"),
                        "xlsx_member_count": archive.member_count,
                        "xlsx_total_uncompressed_bytes": archive.total_uncompressed_bytes,
                    },
                )
                PostgresArtifactMetadataRepository(session).mark_linked(
                    artifact.id,
                    linked_at=beijing_now(),
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

    def list_import_batches(self, query: ImportBatchListQuery) -> ImportBatchListResponse:
        codec = self._cursor_codec()
        query_hash = _import_batch_query_hash(query)
        position = (
            codec.decode(query.cursor, query_hash=query_hash) if query.cursor is not None else None
        )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                rows = PostgresImportBatchQueryRepository(session).list_batches(
                    ImportBatchReadQuery(
                        identifier=query.identifier,
                        status=query.status,
                        stage=query.stage,
                        created_from=query.created_from,
                        created_to=query.created_to,
                        position=position,
                        limit=query.limit + 1,
                    )
                )
        finally:
            session.close()
        has_more = len(rows) > query.limit
        page = rows[: query.limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = codec.encode(
                ImportBatchCursorPosition(created_at=last.created_at, batch_id=last.batch_id),
                query_hash=query_hash,
            )
        return ImportBatchListResponse(
            items=tuple(_query_batch_response(row) for row in page),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def get_import_batch_summary(self) -> ImportBatchSummaryResponse:
        as_of = beijing_now()
        local_now = as_of.astimezone(_SHANGHAI)
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                summary = PostgresImportBatchQueryRepository(session).summary(
                    today_start_utc=today_start.astimezone(UTC),
                    tomorrow_start_utc=tomorrow_start.astimezone(UTC),
                )
        finally:
            session.close()
        return ImportBatchSummaryResponse(
            processing_count=summary.processing_count,
            completed_today_count=summary.completed_today_count,
            rows_ingested_today=summary.rows_ingested_today,
            as_of=as_of,
        )

    def _cursor_codec(self) -> ImportBatchCursorCodec:
        secret = self._cursor_signing_secret
        if secret is None:
            try:
                value = read_secret_file(
                    self._runtime.settings.import_batch_cursor_signing_key_file,
                    root=self._runtime.settings.secret_dir,
                ).get_secret_value()
                secret = value.encode("utf-8")
            except SecretFileError as exc:
                raise ImportCursorUnavailable from exc
        try:
            return ImportBatchCursorCodec(secret=secret)
        except ValueError as exc:
            raise ImportCursorUnavailable from exc

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

    def create_keyword_pack(
        self,
        request: KeywordPackCreateRequest,
        *,
        actor_ref: str = "system:direct-service-call",
        request_id: str = "direct-service-call",
    ) -> KeywordPackResponse:
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
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="keyword_pack_created",
                    object_type="keyword_pack",
                    object_id=str(pack.id),
                    detail={"version": pack.version, "enabled": pack.enabled},
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
        *,
        actor_ref: str = "system:direct-service-call",
        request_id: str = "direct-service-call",
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
                        platform_scope="all",
                        priority=request.priority,
                        enabled=request.enabled,
                        note=request.note.strip(),
                    )
                )
                pack = repository.get_pack(pack_id)
                if pack is None:  # pragma: no cover - 持锁事务中的父记录不会消失
                    raise ImportResourceNotFound
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="keyword_pack_item_added",
                    object_type="keyword_pack",
                    object_id=str(pack_id),
                    detail={
                        "keyword_id": str(keyword.id),
                        "priority": request.priority,
                        "enabled": request.enabled,
                    },
                )
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
        *,
        actor_ref: str = "system:direct-service-call",
        request_id: str = "direct-service-call",
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
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="global_relevance_config_updated",
                    object_type="global_relevance_config",
                    object_id="global",
                    detail={
                        "keyword_pack_id": str(snapshot.keyword_pack_id),
                        "keyword_pack_version": snapshot.keyword_pack_version,
                    },
                )
                return _relevance_response(snapshot, updated_at)
        finally:
            session.close()

    def get_global_relevance(self) -> GlobalRelevanceConfigResponse:
        snapshot, updated_at = self._read_relevance_snapshot()
        return _relevance_response(snapshot, updated_at)

    def _read_import_keyword_selection(
        self,
        keyword_pack_ids: tuple[UUID, ...],
        vehicle_model_ids: tuple[UUID, ...] = (),
    ) -> ImportKeywordSelectionSnapshot:
        return read_import_keyword_selection(
            self._runtime, keyword_pack_ids, vehicle_model_ids
        )

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


def _audit_configuration(
    session: Session,
    *,
    actor_ref: str,
    request_id: str,
    event_type: str,
    object_type: str,
    object_id: str,
    detail: dict[str, JsonValue],
) -> None:
    """把配置变更和对应业务写入放在同一数据库事务。"""

    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=actor_ref,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            safe_detail=detail,
            created_at=beijing_now(),
        )
    )


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
                platform_scope=item.platform_scope,
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
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        progress=job.progress,
        error_code=job.error_code,
        result=_job_result_response(job.result),
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
        source_filename=_source_filename(batch.stats),
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


def _query_batch_response(record: ImportBatchReadRecord) -> ImportBatchResponse:
    job = JobStatusResponse(
        id=record.job_id,
        job_type=record.job_type,
        status=cast(ImportBatchStatus, record.status),
        attempt=record.attempt,
        max_attempts=record.max_attempts,
        progress=record.progress,
        error_code=record.job_error_code,
        result=_job_result_response(record.job_result),
        created_at=record.job_created_at,
        started_at=record.job_started_at,
        finished_at=record.job_finished_at,
    )
    return ImportBatchResponse(
        id=record.batch_id,
        input_artifact_id=record.input_artifact_id,
        source_filename=record.source_filename,
        status=cast(ImportBatchStatus, record.status),
        stage=cast(ImportStage, record.stage),
        stats=ImportStatsResponse(
            **{name: _stat(record.stats, name) for name in ImportStatsResponse.model_fields}
        ),
        error_summary=record.error_summary or record.job_error_code,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at or record.job_finished_at,
        job=job,
    )


def _job_result_response(value: object) -> ImportJobResultResponse | None:
    if not isinstance(value, dict):
        return None
    batch_id = value.get("batch_id")
    rows_ingested = value.get("rows_ingested")
    if (
        not isinstance(batch_id, str)
        or not isinstance(rows_ingested, int)
        or isinstance(rows_ingested, bool)
        or rows_ingested < 0
    ):
        return None
    try:
        parsed_batch_id = UUID(batch_id)
    except ValueError:
        return None
    return ImportJobResultResponse(batch_id=parsed_batch_id, rows_ingested=rows_ingested)


def _source_filename(stats: dict[str, object]) -> str | None:
    value = stats.get("source_filename")
    return value if isinstance(value, str) and value else None


def _import_batch_query_hash(query: ImportBatchListQuery) -> str:
    def timestamp(value: datetime | None) -> str | None:
        return value.astimezone(UTC).isoformat() if value is not None else None

    payload = {
        "created_from": timestamp(query.created_from),
        "created_to": timestamp(query.created_to),
        "identifier": str(query.identifier) if query.identifier is not None else None,
        "limit": query.limit,
        "sort": "created_at_desc,id_desc",
        "stage": query.stage,
        "status": query.status,
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _stat(stats: dict[str, object], name: str) -> int:
    value = stats.get(name, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


__all__ = ["PostgresImportHttpService", "read_import_keyword_selection"]
