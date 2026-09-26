"""Stage 8B Excel Import Job 的正式 Worker 执行器与终态收敛。"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.manual_ingestion import (
    PostgresProcessingImportBatchRepository,
)
from aima_ugc.adapters.persistence.postgres.voice_plaza_projection import (
    defer_voice_plaza_projection,
    flush_deferred_voice_plaza_projection,
)
from aima_ugc.adapters.providers.imports import (
    ExcelImportRejectedRowsError,
    convert_excel_to_canonical_jsonl,
)
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.ingestion import ProcessingImportBatchRecord
from aima_ugc.modules.ingestion.brand_vehicle_filter import (
    BrandVehicleFilterSnapshot,
    filter_and_deduplicate_canonical_contents,
)
from aima_ugc.modules.ingestion.import_job import (
    ImportJobPayload,
)
from aima_ugc.modules.ingestion.xlsx_security import (
    MAX_XLSX_FILE_BYTES,
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_archive,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.logging import log_event
from aima_ugc.platform.storage import (
    ArtifactRecord,
    ArtifactService,
    ArtifactSizeLimitError,
    CanonicalArtifactIntegrityError,
    CanonicalArtifactParent,
    CanonicalArtifactReader,
    CanonicalArtifactWriter,
)

from .manual_ingestion import ingest_unified_content_batch
from .runtime import PlatformRuntime


@dataclass(frozen=True, slots=True)
class _ImportExecution:
    """Attempt 内冻结的 Batch/Artifact/Payload/Job。"""

    batch: ProcessingImportBatchRecord
    artifact: ArtifactRecord | None
    payload: ImportJobPayload
    job: JobRecord
    canonical_artifact: ArtifactRecord | None


class PostgresImportJobExecutor:
    """每个 Attempt 从冻结 Artifact/关键词快照完整重跑 Stage 8A 正式链路。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._artifacts = ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.database.new_session),
            store=runtime.artifact_store,
        )
        self._canonical_writer = CanonicalArtifactWriter(artifacts=self._artifacts)
        self._canonical_reader = CanonicalArtifactReader(store=runtime.artifact_store)

    def execute(
        self,
        *,
        payload: ImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """执行当前 v2 Import；只使用冻结 Snapshot，不读取实时目录。"""

        return self._execute_v2(payload=payload, fence=fence, context=context)

    def _execute_v2(
        self,
        *,
        payload: ImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """按 mapping→Brand/Vehicle filtering→dedup→ingestion 执行 v2 Attempt。"""

        execution: _ImportExecution | None = None
        diagnostic_stage = "loading"
        diagnostic_operation = "load_execution"
        execution_started = perf_counter()
        try:
            execution = self._load_v2(fence, payload)
            if execution is None:
                return JobHandlerResult.failed("import_batch_not_found")
            if execution.batch.status == "succeeded":
                return JobHandlerResult.succeeded(
                    {
                        "batch_id": str(execution.batch.id),
                        "rows_ingested": _stat(execution.batch.stats, "rows_ingested"),
                    }
                )
            artifact = execution.artifact
            if artifact is None or artifact.storage_status not in {"stored", "linked"}:
                raise InvalidXlsxError("Import Source Artifact 不可用")
            profile = execution.batch.stats.get("profile")
            if not isinstance(profile, str) or not profile:
                raise ValueError("Import Batch 缺少冻结 Excel Profile")
            with TemporaryDirectory(prefix="aima-import-") as directory:
                diagnostic_operation = "open_temporary_directory"
                work_dir = Path(directory)
                canonical_artifact = execution.canonical_artifact
                canonical_contents: Iterable[CanonicalContentV1]
                source_read_ms = 0
                mapping_ms = 0
                canonical_write_ms = 0
                canonical_reused = canonical_artifact is not None
                temporary_peak_bytes = 0
                if canonical_artifact is None:
                    source_filename = execution.batch.stats.get("source_filename")
                    if not isinstance(source_filename, str) or not source_filename:
                        raise ValueError("Import Batch 缺少冻结源文件名")
                    input_path = work_dir / "source.xlsx"
                    diagnostic_stage = "reading"
                    self._stage(execution.batch, fence=fence, stage="reading")
                    source_read_started = perf_counter()
                    diagnostic_operation = "open_staged_source"
                    with input_path.open("xb") as destination:
                        diagnostic_operation = "copy_source_artifact"
                        copied = self._runtime.artifact_store.copy_to(
                            artifact.storage_key,
                            destination,
                        )
                    if copied.sha256 != artifact.sha256 or copied.byte_size != artifact.byte_size:
                        raise InvalidXlsxError("Artifact 完整性校验失败")
                    diagnostic_operation = "validate_xlsx"
                    validate_xlsx_archive(input_path)
                    temporary_peak_bytes = max(
                        temporary_peak_bytes,
                        _directory_bytes(work_dir),
                    )
                    source_read_ms = int((perf_counter() - source_read_started) * 1000)
                    context.heartbeat(progress=15)
                    if context.cancel_requested():
                        return JobHandlerResult.cancelled()

                    self._stage(execution.batch, fence=fence, stage="mapping")
                    diagnostic_stage = "mapping"
                    diagnostic_operation = "map_excel_to_canonical"
                    mapping_started = perf_counter()
                    conversion = convert_excel_to_canonical_jsonl(
                        input_path=input_path,
                        output_path=work_dir / "mapping" / "contents.jsonl",
                        profile_name=profile,
                    )
                    temporary_peak_bytes = max(
                        temporary_peak_bytes,
                        _directory_bytes(work_dir),
                    )
                    mapping_ms = int((perf_counter() - mapping_started) * 1000)
                    canonical_write_started = perf_counter()
                    diagnostic_stage = "canonical_writing"
                    diagnostic_operation = "write_canonical_artifact"
                    try:
                        canonical_artifact = self._canonical_writer.write(
                            _iter_canonical_jsonl(conversion.output_path),
                            parent=CanonicalArtifactParent(
                                processing_import_batch_id=execution.batch.id
                            ),
                            retention_class="canonical",
                            max_bytes=MAX_XLSX_FILE_BYTES,
                        )
                    except IntegrityError:
                        canonical_artifact = self._canonical_for_batch(execution.batch.id)
                        if canonical_artifact is None:
                            raise
                        canonical_reused = True
                    # Canonical 已不可变持久化；释放源 XLSX 与 Mapper JSONL 后再准备入库，
                    # 避免同一 Attempt 同时保留 source + mapping + prepared 三份大文件。
                    input_path.unlink(missing_ok=True)
                    conversion.output_path.unlink(missing_ok=True)
                    conversion.error_path.unlink(missing_ok=True)
                    canonical_contents = self._canonical_reader.read(canonical_artifact)
                    canonical_write_ms = int((perf_counter() - canonical_write_started) * 1000)
                else:
                    diagnostic_stage = "canonical_reading"
                    diagnostic_operation = "read_canonical_artifact"
                    canonical_contents = self._canonical_reader.read(canonical_artifact)
                context.heartbeat(progress=40)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                self._stage(
                    execution.batch,
                    fence=fence,
                    stage="filtering",
                )
                diagnostic_stage = "preparing"
                diagnostic_operation = "filter_and_deduplicate_canonical"
                preparation_started = perf_counter()
                preparation = filter_and_deduplicate_canonical_contents(
                    canonical_contents,
                    output_path=work_dir / "prepared" / "contents.jsonl",
                    snapshot=execution.payload.filter_snapshot,
                )
                preparation_ms = int((perf_counter() - preparation_started) * 1000)
                temporary_peak_bytes = max(
                    temporary_peak_bytes,
                    _directory_bytes(work_dir) + int(canonical_artifact.byte_size or 0),
                )
                context.heartbeat(progress=60)

                self._stage(
                    execution.batch,
                    fence=fence,
                    stage="deduplicating",
                    stats={
                        "rows_seen": preparation.rows_seen,
                        "rows_matched": preparation.rows_matched,
                        "rows_filtered_out": preparation.rows_filtered_out,
                    },
                )
                context.heartbeat(progress=80)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                ingestion_started = perf_counter()
                diagnostic_stage = "ingesting"
                diagnostic_operation = "persist_content_batch"
                rows_ingested = self._ingest_v2(
                    execution,
                    artifact=artifact,
                    fence=fence,
                    unified_content_path=preparation.output_path,
                    rows_seen=preparation.rows_seen,
                    rows_matched=preparation.rows_matched,
                    rows_filtered_out=preparation.rows_filtered_out,
                    duplicates_removed=preparation.duplicates_removed,
                )
                ingestion_ms = int((perf_counter() - ingestion_started) * 1000)
                duration_ms = int((perf_counter() - execution_started) * 1000)
                log_event(
                    self._runtime.logger,
                    logging.INFO,
                    "excel_import.pipeline_completed",
                    "Excel 导入流水线完成",
                    job_id=str(fence.job_id),
                    batch_id=str(execution.batch.id),
                    canonical_reused=canonical_reused,
                    rows_seen=preparation.rows_seen,
                    rows_matched=preparation.rows_matched,
                    rows_written=preparation.rows_written,
                    duplicates_removed=preparation.duplicates_removed,
                    rows_ingested=rows_ingested,
                    source_read_ms=source_read_ms,
                    mapping_ms=mapping_ms,
                    canonical_write_ms=canonical_write_ms,
                    preparation_ms=preparation_ms,
                    ingestion_ms=ingestion_ms,
                    duration_ms=duration_ms,
                    temporary_bytes=_directory_bytes(work_dir),
                    temporary_peak_bytes=temporary_peak_bytes,
                )
                return JobHandlerResult.succeeded(
                    {"batch_id": str(execution.batch.id), "rows_ingested": rows_ingested}
                )
        except LeaseLostError:
            raise
        except (
            ExcelImportRejectedRowsError,
            ArtifactSizeLimitError,
            InvalidXlsxError,
            XlsxResourceLimitError,
            CanonicalArtifactIntegrityError,
            ValueError,
        ):
            if execution is None:
                raise
            self._fail(execution.batch, fence=fence, error_code="invalid_import")
            return JobHandlerResult.failed("invalid_import")
        except OSError as exc:
            if execution is None:
                raise
            log_event(
                self._runtime.logger,
                logging.WARNING,
                "excel_import.io_failed",
                "Excel 导入发生可重试 I/O 错误",
                job_id=str(fence.job_id),
                batch_id=str(execution.batch.id),
                stage=diagnostic_stage,
                operation=diagnostic_operation,
                error_type=type(exc).__name__,
                errno=exc.errno,
                error_path=(Path(exc.filename).name if exc.filename is not None else None),
            )
            if execution.job.attempt >= execution.job.max_attempts:
                self._fail(execution.batch, fence=fence, error_code="import_io_failed")
                return JobHandlerResult.failed("import_io_failed")
            return JobHandlerResult.retry("import_io_failed")

    def _load_v2(
        self,
        fence: JobExecutionFence,
        payload: ImportJobPayload,
    ) -> _ImportExecution | None:
        """从 Batch 重读冻结 Snapshot，并与 Job Payload 做字节语义等价校验。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).validate_current_execution(fence)
                batch = PostgresProcessingImportBatchRepository(session).get_by_job_id(fence.job_id)
                if batch is None:
                    return None
                frozen = BrandVehicleFilterSnapshot.model_validate(
                    batch.stats.get("filter_snapshot")
                )
                if frozen != payload.filter_snapshot:
                    raise ValueError(
                        "Import Job Payload 与 Batch Brand/Vehicle Filter Snapshot 不一致"
                    )
                artifact = PostgresArtifactMetadataRepository(session).get(batch.input_artifact_id)
                canonical_artifact = PostgresArtifactMetadataRepository(
                    session
                ).get_canonical_for_parent(
                    CanonicalArtifactParent(processing_import_batch_id=batch.id)
                )
                return _ImportExecution(batch, artifact, payload, job, canonical_artifact)
        finally:
            session.close()

    def _ingest_v2(
        self,
        execution: _ImportExecution,
        *,
        artifact: ArtifactRecord,
        fence: JobExecutionFence,
        unified_content_path: Path,
        rows_seen: int,
        rows_matched: int,
        rows_filtered_out: int,
        duplicates_removed: int,
    ) -> int:
        """在 Job/Batch 当前执行锁内完成 Content 与 Brand/Vehicle Evidence 同事务写入。"""

        self._stage(
            execution.batch,
            fence=fence,
            stage="ingesting",
            stats={
                "rows_seen": rows_seen,
                "rows_matched": rows_matched,
                "rows_filtered_out": rows_filtered_out,
                "duplicates_removed": duplicates_removed,
            },
        )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                jobs = PostgresJobRepository(session)
                jobs.validate_current_execution(fence)
                batch = PostgresProcessingImportBatchRepository(session).get_by_job_id(
                    fence.job_id,
                    for_update=True,
                )
                if batch is None:
                    raise LookupError("Import Batch 不存在")
                if batch.status == "succeeded":
                    return _stat(batch.stats, "rows_ingested")
                current_artifact = PostgresArtifactMetadataRepository(session).get(
                    batch.input_artifact_id
                )
                if current_artifact is None:
                    raise LookupError("Import Source Artifact 不存在")
                if current_artifact.id != artifact.id:
                    raise RuntimeError("Import Source Artifact 在 Attempt 内发生变化")
                defer_voice_plaza_projection(session)
                write = ingest_unified_content_batch(
                    session=session,
                    batch_id=batch.id,
                    input_artifact=current_artifact,
                    unified_content_path=unified_content_path,
                    rows_seen=rows_seen,
                    rows_rejected=0,
                    brand_vehicle_filter_snapshot=execution.payload.filter_snapshot,
                )
                jobs.lock_current_execution(fence)
                affected_content_ids = tuple(
                    session.scalars(
                        select(content_source_contributions_table.c.content_id)
                        .select_from(
                            content_source_contributions_table.join(
                                provider_request_attempts_table,
                                provider_request_attempts_table.c.id
                                == content_source_contributions_table.c.provider_attempt_id,
                            ).join(
                                provider_requests_table,
                                provider_requests_table.c.id
                                == provider_request_attempts_table.c.provider_request_id,
                            )
                        )
                        .where(provider_requests_table.c.import_batch_id == batch.id)
                        .distinct()
                    )
                )
                flush_deferred_voice_plaza_projection(session, affected_content_ids)
                return write.rows_ingested
        finally:
            session.close()

    def _canonical_for_batch(self, batch_id: UUID) -> ArtifactRecord | None:
        """在唯一关系竞争后重读胜出的 linked Canonical Artifact。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return PostgresArtifactMetadataRepository(session).get_canonical_for_parent(
                    CanonicalArtifactParent(processing_import_batch_id=batch_id)
                )
        finally:
            session.close()

    def _stage(
        self,
        batch: ProcessingImportBatchRecord,
        *,
        fence: JobExecutionFence,
        stage: str,
        stats: dict[str, object] | None = None,
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                current = PostgresProcessingImportBatchRepository(session).get(batch.id)
                if current is None:
                    raise LookupError("Import Batch 不存在")
                PostgresProcessingImportBatchRepository(session).update_progress(
                    batch.id,
                    stage=stage,
                    stats={**current.stats, **(stats or {})},
                )
        finally:
            session.close()

    def _fail(
        self,
        batch: ProcessingImportBatchRecord,
        *,
        fence: JobExecutionFence,
        error_code: str,
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                current = PostgresProcessingImportBatchRepository(session).get(batch.id)
                if current is not None and current.status == "processing":
                    PostgresProcessingImportBatchRepository(session).mark_failed(
                        batch.id,
                        rows_seen=_stat(current.stats, "rows_seen"),
                        rows_ingested=0,
                        rows_rejected=_stat(current.stats, "rows_rejected"),
                        error_summary=error_code,
                    )
        finally:
            session.close()


def import_job_terminal_callback(session: Session, job: JobRecord) -> None:
    """与 Job 终态同事务收敛 Batch，覆盖取消与最终 Deadline 超时。"""

    repository = PostgresProcessingImportBatchRepository(session)
    batch = repository.get_by_job_id(job.id, for_update=True)
    if batch is None:
        return
    if job.status == "succeeded":
        if batch.status != "succeeded":
            raise RuntimeError("Import Job 成功但 Batch 尚未成功")
        return
    if job.status not in {"failed", "cancelled"} or batch.status != "processing":
        return
    repository.mark_failed(
        batch.id,
        rows_seen=_stat(batch.stats, "rows_seen"),
        rows_ingested=0,
        rows_rejected=_stat(batch.stats, "rows_rejected"),
        error_summary=job.error_code or job.status,
    )


def _stat(stats: dict[str, object], name: str) -> int:
    value = stats.get(name, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _directory_bytes(path: Path) -> int:
    """只统计当前 Attempt 私有临时目录，避免读取或暴露用户文件路径。"""

    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _iter_canonical_jsonl(path: Path) -> Iterator[CanonicalContentV1]:
    """把 Mapper 的临时 JSONL 重新收敛到当前 Canonical Contract。"""

    with path.open("rb") as source:
        for raw_line in source:
            try:
                yield CanonicalContentV1.model_validate_json(raw_line)
            except ValidationError as exc:
                raise ValueError("Mapper 输出不是合法 CanonicalContentV1") from exc


__all__ = ["PostgresImportJobExecutor", "import_job_terminal_callback"]
