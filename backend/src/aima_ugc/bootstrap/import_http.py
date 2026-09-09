"""Stage 3 Import HTTP 覆盖层：新任务使用 Brand/Vehicle Filter，旧能力委托迁移基线。"""

from __future__ import annotations

from typing import BinaryIO
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.import_job import (
    BRAND_VEHICLE_IMPORT_JOB_PAYLOAD_VERSION,
    BRAND_VEHICLE_IMPORT_JOB_TYPE,
    IMPORT_JOB_MAX_ATTEMPTS,
    IMPORT_JOB_TIMEOUT_SECONDS,
    LEGACY_IMPORT_JOB_TYPE,
    BrandVehicleImportJobPayload,
)

from . import _import_http_base as _base
from ._import_http_base import *  # noqa: F403

# Historical legacy Campaign 仍通过此公开名字读取 v1 Keyword/Vehicle Snapshot。
read_import_keyword_selection = _base.read_import_keyword_selection


class PostgresImportHttpService(_base.PostgresImportHttpService):
    """新建 Import 只冻结 Brand Scope；其余查询/Keyword 配置沿用稳定基线。"""

    def create_import(
        self,
        *,
        filename: str,
        content_type: str | None,
        source: BinaryIO,
        brand_ids: tuple[UUID, ...],
        request_id: str,
    ) -> _base.ImportBatchCreatedResponse:
        """创建 v2 Import；空 `brand_ids` 明确表示冻结全部 active Brand。"""

        del content_type
        if len(brand_ids) > 100 or len(brand_ids) != len(set(brand_ids)):
            raise _base.RelevanceConfigurationError
        safe_name = _base._validate_upload_filename(filename)
        filter_snapshot = self._read_brand_vehicle_filter_snapshot(brand_ids)
        try:
            source.seek(0, 2)
            file_size = source.tell()
            source.seek(0)
            archive = _base.validate_xlsx_stream(
                source,
                filename=safe_name,
                file_size=file_size,
            )
        except _base.XlsxResourceLimitError as exc:
            raise _base.ImportUploadTooLarge from exc
        except (_base.InvalidXlsxError, OSError) as exc:
            raise _base.InvalidImportFile from exc

        artifacts = _base.ArtifactService(
            metadata=_base.PostgresArtifactMetadataGateway(self._runtime.database.new_session),
            store=self._runtime.artifact_store,
        )
        try:
            source.seek(0)
            artifact = artifacts.store_stream(
                kind="file-import.raw",
                content_type=_base._XLSX_CONTENT_TYPE,
                retention_class="raw",
                source=source,
                max_bytes=_base.MAX_XLSX_FILE_BYTES,
                filename_suffix=".xlsx",
            )
        except _base.ArtifactSizeLimitError as exc:
            raise _base.ImportUploadTooLarge from exc

        batch_id = uuid4()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = _base.PostgresJobRepository(session).enqueue(
                    job_type=BRAND_VEHICLE_IMPORT_JOB_TYPE,
                    payload_version=BRAND_VEHICLE_IMPORT_JOB_PAYLOAD_VERSION,
                    payload=BrandVehicleImportJobPayload(
                        filter_snapshot=filter_snapshot,
                    ).model_dump(mode="json"),
                    internal_idempotency_key=f"import-batch:{batch_id}",
                    request_id=request_id,
                    priority=0,
                    max_attempts=IMPORT_JOB_MAX_ATTEMPTS,
                    timeout_seconds=IMPORT_JOB_TIMEOUT_SECONDS,
                )
                _base.PostgresProcessingImportBatchRepository(session).create(
                    batch_id=batch_id,
                    input_artifact_id=artifact.id,
                    job_id=job.id,
                    stats={
                        "stage": "queued",
                        "profile": _base._IMPORT_PROFILE,
                        "source_filename": safe_name,
                        "filter_snapshot": filter_snapshot.model_dump(mode="json"),
                        "xlsx_member_count": archive.member_count,
                        "xlsx_total_uncompressed_bytes": archive.total_uncompressed_bytes,
                    },
                )
                _base.PostgresArtifactMetadataRepository(session).mark_linked(
                    artifact.id,
                    linked_at=_base.beijing_now(),
                )
        finally:
            session.close()
        return _base.ImportBatchCreatedResponse(batch_id=batch_id, job_id=job.id)

    def get_job(self, job_id: UUID) -> _base.JobStatusResponse:
        """查询接口同时承认升级前 v1 与 Stage 3 v2 Import Job。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                job = _base.PostgresJobRepository(session).get(job_id)
                if job is None or job.job_type not in {
                    LEGACY_IMPORT_JOB_TYPE,
                    BRAND_VEHICLE_IMPORT_JOB_TYPE,
                }:
                    raise _base.ImportResourceNotFound
                return _base._job_response(job)
        finally:
            session.close()

    def _read_brand_vehicle_filter_snapshot(
        self,
        brand_ids: tuple[UUID, ...],
    ) -> BrandVehicleFilterSnapshot:
        """在独立短事务中读取 Stage 2 锁保护 Snapshot，并立刻冻结为 Job 数据。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                try:
                    catalog = PostgresBrandVehicleRepository(session).snapshot(
                        brand_ids=brand_ids or None
                    )
                except (LookupError, ValueError) as exc:
                    raise _base.RelevanceConfigurationError from exc
                return BrandVehicleFilterSnapshot(catalog=catalog)
        finally:
            session.close()


__all__ = [
    *getattr(_base, "__all__", ()),
    "PostgresImportHttpService",
    "read_import_keyword_selection",
]
