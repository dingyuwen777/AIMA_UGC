"""Stage 3 Excel Import Worker 覆盖层；v1 委托基线，v2 使用统一 Brand/Vehicle Filter。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from aima_ugc.modules.ingestion.brand_vehicle_filter import (
    BrandVehicleFilterSnapshot,
    filter_canonical_content_by_brand_vehicle_jsonl,
)
from aima_ugc.modules.ingestion.import_job import (
    AnyImportJobPayload,
    BrandVehicleImportJobPayload,
    ImportJobPayload,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.storage import ArtifactRecord

from . import _import_worker_base as _base
from .manual_ingestion import ingest_unified_content_batch


@dataclass(frozen=True, slots=True)
class _Stage3ImportExecution:
    """v2 Attempt 内冻结的 Batch/Artifact/Payload/Job。"""

    batch: _base.ProcessingImportBatchRecord
    artifact: ArtifactRecord | None
    payload: BrandVehicleImportJobPayload
    job: JobRecord


class PostgresImportJobExecutor(_base.PostgresImportJobExecutor):
    """显式兼容 v1，并为 v2 完整重跑冻结 Brand/Vehicle Filter 链。"""

    def execute(
        self,
        *,
        payload: AnyImportJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """v1 原样委托基线；v2 不读取实时目录。"""

        if isinstance(payload, ImportJobPayload):
            return super().execute(payload=payload, fence=fence, context=context)
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
                        "rows_ingested": _base._stat(execution.batch.stats, "rows_ingested"),
                    }
                )
            artifact = execution.artifact
            if artifact is None or artifact.storage_status not in {"stored", "linked"}:
                raise _base.InvalidXlsxError("Import Source Artifact 不可用")
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
                    raise _base.InvalidXlsxError("Artifact 完整性校验失败")
                _base.validate_xlsx_archive(input_path)
                context.heartbeat(progress=15)
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()

                self._stage(execution.batch, fence=fence, stage="mapping")
                conversion = _base.convert_excel_to_canonical_jsonl(
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
                deduplication = _base.deduplicate_content_jsonl(
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
            _base.ExcelImportRejectedRowsError,
            _base.InvalidXlsxError,
            _base.XlsxResourceLimitError,
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
                job = _base.PostgresJobRepository(session).validate_current_execution(fence)
                batch = _base.PostgresProcessingImportBatchRepository(session).get_by_job_id(
                    fence.job_id
                )
                if batch is None:
                    return None
                frozen = BrandVehicleFilterSnapshot.model_validate(
                    batch.stats.get("filter_snapshot")
                )
                if frozen != payload.filter_snapshot:
                    raise ValueError(
                        "Import Job Payload 与 Batch Brand/Vehicle Filter Snapshot 不一致"
                    )
                artifact = _base.PostgresArtifactMetadataRepository(session).get(
                    batch.input_artifact_id
                )
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
                jobs = _base.PostgresJobRepository(session)
                jobs.validate_current_execution(fence)
                batch = _base.PostgresProcessingImportBatchRepository(session).get_by_job_id(
                    fence.job_id,
                    for_update=True,
                )
                if batch is None:
                    raise LookupError("Import Batch 不存在")
                if batch.status == "succeeded":
                    return _base._stat(batch.stats, "rows_ingested")
                current_artifact = _base.PostgresArtifactMetadataRepository(session).get(
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


import_job_terminal_callback = _base.import_job_terminal_callback

__all__ = ["PostgresImportJobExecutor", "import_job_terminal_callback"]
