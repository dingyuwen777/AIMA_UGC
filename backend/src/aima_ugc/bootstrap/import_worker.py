"""Stage 8B Excel Import Job 的正式 Worker 执行器与终态收敛。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.manual_ingestion import (
    PostgresProcessingImportBatchRepository,
)
from aima_ugc.adapters.providers.imports import (
    ExcelImportRejectedRowsError,
    convert_excel_to_canonical_jsonl,
)
from aima_ugc.modules.analysis import (
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
)
from aima_ugc.modules.ingestion import ProcessingImportBatchRecord
from aima_ugc.modules.ingestion.brand_vehicle_filter import (
    BrandVehicleFilterSnapshot,
    filter_canonical_content_by_brand_vehicle_jsonl,
)
from aima_ugc.modules.ingestion.import_job import (
    AnyImportJobPayload,
    BrandVehicleImportJobPayload,
    ImportJobPayload,
    ImportKeywordSelectionSnapshot,
)
from aima_ugc.modules.ingestion.xlsx_security import (
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_archive,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.storage import ArtifactRecord

from .manual_ingestion import ingest_unified_content_batch
from .runtime import PlatformRuntime


@dataclass(frozen=True, slots=True)
class _ImportExecution:
    batch: ProcessingImportBatchRecord
    artifact: ArtifactRecord | None
    payload: ImportJobPayload
    job: JobRecord


@dataclass(frozen=True, slots=True)
class _Stage3ImportExecution:
    """v2 Attempt 内冻结的 Batch/Artifact/Payload/Job。"""

    batch: ProcessingImportBatchRecord
    artifact: ArtifactRecord | None
    payload: BrandVehicleImportJobPayload
    job: JobRecord


class PostgresImportJobExecutor:
    """每个 Attempt 从冻结 Artifact/关键词快照完整重跑 Stage 8A 正式链路。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def _execute_v1(
        self,
        *,
        payload: ImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        execution: _ImportExecution | None = None
        try:
            execution = self._load(fence, payload)
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
            effective_keywords = execution.payload.keyword_selection.effective_keywords
            vehicle_aliases = tuple(
                alias
                for model in execution.payload.keyword_selection.vehicle_models
                for alias in model.aliases
            )
            profile = execution.batch.stats.get("profile")
            if not isinstance(profile, str) or not profile:
                raise ValueError("Import Batch 缺少冻结 Excel Profile")
            with TemporaryDirectory(prefix="aima-import-") as directory:
                work_dir = Path(directory)
                source_filename = execution.batch.stats.get("source_filename")
                if not isinstance(source_filename, str) or not source_filename:
                    raise ValueError("Import Batch 缺少冻结源文件名")
                # 原文件名只作审计事实；正式临时路径固定，避免宿主 OS 路径语义漂移。
                input_path = work_dir / "source.xlsx"
                self._stage(execution.batch, fence=fence, stage="reading")
                with input_path.open("xb") as destination:
                    copied = self._runtime.artifact_store.copy_to(
                        artifact.storage_key,
                        destination,
                    )
                if copied.sha256 != artifact.sha256 or copied.byte_size != artifact.byte_size:
                    raise InvalidXlsxError("Artifact 完整性校验失败")
                validate_xlsx_archive(input_path)
                context.heartbeat(progress=15)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                self._stage(execution.batch, fence=fence, stage="mapping")
                conversion = convert_excel_to_canonical_jsonl(
                    input_path=input_path,
                    output_path=work_dir / "canonical" / "contents.jsonl",
                    profile_name=profile,
                )
                context.heartbeat(progress=40)

                self._stage(
                    execution.batch,
                    fence=fence,
                    stage="filtering",
                    stats={"rows_seen": conversion.rows_seen},
                )
                filtering = filter_canonical_content_jsonl(
                    input_path=conversion.output_path,
                    output_path=work_dir / "filtered" / "contents.jsonl",
                    keywords=effective_keywords,
                    vehicle_aliases=vehicle_aliases,
                )
                context.heartbeat(progress=60)

                self._stage(
                    execution.batch,
                    fence=fence,
                    stage="deduplicating",
                    stats={
                        "rows_seen": conversion.rows_seen,
                        "rows_matched": filtering.rows_written,
                        "rows_filtered_out": filtering.rows_filtered_out,
                    },
                )
                deduplication = deduplicate_content_jsonl(
                    input_path=filtering.output_path,
                    output_path=work_dir / "deduplicated" / "contents.jsonl",
                )
                context.heartbeat(progress=80)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                summary = self._ingest(
                    execution,
                    artifact=artifact,
                    fence=fence,
                    unified_content_path=deduplication.output_path,
                    rows_seen=conversion.rows_seen,
                    rows_matched=filtering.rows_written,
                    rows_filtered_out=filtering.rows_filtered_out,
                    duplicates_removed=deduplication.duplicates_removed,
                )
                return JobHandlerResult.succeeded(
                    {
                        "batch_id": str(execution.batch.id),
                        "rows_ingested": summary,
                    }
                )
        except LeaseLostError:
            raise
        except ExcelImportRejectedRowsError, InvalidXlsxError, XlsxResourceLimitError, ValueError:
            if execution is None:
                raise
            self._fail(execution.batch, fence=fence, error_code="invalid_import")
            return JobHandlerResult.failed("invalid_import")
        except OSError:
            if execution is None:
                raise
            if execution.job.attempt >= execution.job.max_attempts:
                self._fail(execution.batch, fence=fence, error_code="import_io_failed")
                return JobHandlerResult.failed("import_io_failed")
            return JobHandlerResult.retry("import_io_failed")

    def execute(
        self,
        *,
        payload: AnyImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """v1 原样委托基线；v2 不读取实时目录。"""

        if isinstance(payload, ImportJobPayload):
            return self._execute_v1(payload=payload, fence=fence, context=context)
        if not isinstance(payload, BrandVehicleImportJobPayload):
            raise TypeError("Import Worker 收到不支持的 Payload")
        return self._execute_v2(payload=payload, fence=fence, context=context)

    def _execute_v2(
        self,
        *,
        payload: BrandVehicleImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """按 mapping→Brand/Vehicle filtering→dedup→ingestion 执行 v2 Attempt。"""

        execution: _Stage3ImportExecution | None = None
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
                work_dir = Path(directory)
                source_filename = execution.batch.stats.get("source_filename")
                if not isinstance(source_filename, str) or not source_filename:
                    raise ValueError("Import Batch 缺少冻结源文件名")
                input_path = work_dir / "source.xlsx"
                self._stage(execution.batch, fence=fence, stage="reading")
                with input_path.open("xb") as destination:
                    copied = self._runtime.artifact_store.copy_to(
                        artifact.storage_key,
                        destination,
                    )
                if copied.sha256 != artifact.sha256 or copied.byte_size != artifact.byte_size:
                    raise InvalidXlsxError("Artifact 完整性校验失败")
                validate_xlsx_archive(input_path)
                context.heartbeat(progress=15)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                self._stage(execution.batch, fence=fence, stage="mapping")
                conversion = convert_excel_to_canonical_jsonl(
                    input_path=input_path,
                    output_path=work_dir / "canonical" / "contents.jsonl",
                    profile_name=profile,
                )
                context.heartbeat(progress=40)

                self._stage(
                    execution.batch,
                    fence=fence,
                    stage="filtering",
                    stats={"rows_seen": conversion.rows_seen},
                )
                filtering = filter_canonical_content_by_brand_vehicle_jsonl(
                    input_path=conversion.output_path,
                    output_path=work_dir / "filtered" / "contents.jsonl",
                    snapshot=execution.payload.filter_snapshot,
                )
                context.heartbeat(progress=60)

                self._stage(
                    execution.batch,
                    fence=fence,
                    stage="deduplicating",
                    stats={
                        "rows_seen": conversion.rows_seen,
                        "rows_matched": filtering.rows_written,
                        "rows_filtered_out": filtering.rows_filtered_out,
                    },
                )
                deduplication = deduplicate_content_jsonl(
                    input_path=filtering.output_path,
                    output_path=work_dir / "deduplicated" / "contents.jsonl",
                )
                context.heartbeat(progress=80)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                rows_ingested = self._ingest_v2(
                    execution,
                    artifact=artifact,
                    fence=fence,
                    unified_content_path=deduplication.output_path,
                    rows_seen=conversion.rows_seen,
                    rows_matched=filtering.rows_written,
                    rows_filtered_out=filtering.rows_filtered_out,
                    duplicates_removed=deduplication.duplicates_removed,
                )
                return JobHandlerResult.succeeded(
                    {"batch_id": str(execution.batch.id), "rows_ingested": rows_ingested}
                )
        except LeaseLostError:
            raise
        except (
            ExcelImportRejectedRowsError,
            InvalidXlsxError,
            XlsxResourceLimitError,
            ValueError,
        ):
            if execution is None:
                raise
            self._fail(execution.batch, fence=fence, error_code="invalid_import")
            return JobHandlerResult.failed("invalid_import")
        except OSError:
            if execution is None:
                raise
            if execution.job.attempt >= execution.job.max_attempts:
                self._fail(execution.batch, fence=fence, error_code="import_io_failed")
                return JobHandlerResult.failed("import_io_failed")
            return JobHandlerResult.retry("import_io_failed")

    def _load_v2(
        self,
        fence: JobExecutionFence,
        payload: BrandVehicleImportJobPayload,
    ) -> _Stage3ImportExecution | None:
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
                return _Stage3ImportExecution(batch, artifact, payload, job)
        finally:
            session.close()

    def _ingest_v2(
        self,
        execution: _Stage3ImportExecution,
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
                return write.rows_ingested
        finally:
            session.close()

    def _load(
        self,
        fence: JobExecutionFence,
        payload: ImportJobPayload,
    ) -> _ImportExecution | None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = PostgresJobRepository(session).validate_current_execution(fence)
                batch = PostgresProcessingImportBatchRepository(session).get_by_job_id(fence.job_id)
                if batch is None:
                    return None
                frozen_selection = ImportKeywordSelectionSnapshot.model_validate(
                    batch.stats.get("keyword_selection")
                )
                if frozen_selection != payload.keyword_selection:
                    raise ValueError("Import Job Payload 与 Batch Keyword Selection 快照不一致")
                artifact = PostgresArtifactMetadataRepository(session).get(batch.input_artifact_id)
                return _ImportExecution(batch, artifact, payload, job)
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

    def _ingest(
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
                write = ingest_unified_content_batch(
                    session=session,
                    batch_id=batch.id,
                    input_artifact=current_artifact,
                    unified_content_path=unified_content_path,
                    rows_seen=rows_seen,
                    rows_rejected=0,
                    vehicle_catalog_version=(
                        execution.payload.keyword_selection.vehicle_catalog_version
                    ),
                    vehicle_alias_bindings=tuple(
                        (model.id, alias)
                        for model in execution.payload.keyword_selection.vehicle_models
                        for alias in model.aliases
                    ),
                )
                jobs.lock_current_execution(fence)
                return write.rows_ingested
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


__all__ = ["PostgresImportJobExecutor", "import_job_terminal_callback"]
