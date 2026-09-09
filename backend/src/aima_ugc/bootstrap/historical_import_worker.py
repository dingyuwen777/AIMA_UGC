"""Stage 3 Historical Worker 覆盖层；legacy Campaign 原样委托，v2 使用统一 Resolver。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.modules.ingestion.brand_vehicle_filter import (
    BrandVehicleFilterSnapshot,
    resolve_canonical_brand_vehicle,
)
from aima_ugc.modules.ingestion.historical_chunk import HISTORICAL_CHUNK_SCHEMA_VERSION
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError

from . import _historical_import_worker_base as _base


class PostgresHistoricalImportJobExecutor(_base.PostgresHistoricalImportJobExecutor):
    """按 Campaign Snapshot schema 显式分流；旧 queued/running Campaign 不改变解释方式。"""

    def snapshot(
        self,
        *,
        payload: _base.HistoricalSnapshotJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """legacy Snapshot 委托 v1；Stage 3 Snapshot 输出 v2 Brand/Vehicle Chunk。"""

        item, campaign = self._load_snapshot_item(payload.campaign_item_id, fence)
        snapshot_payload = cast(dict[str, object], campaign["keyword_pack_snapshot"])
        if snapshot_payload.get("schema_version") != "brand-vehicle-filter.v1":
            return super().snapshot(payload=payload, fence=fence, context=context)
        filter_snapshot = BrandVehicleFilterSnapshot.model_validate(snapshot_payload)
        source_artifact: _base.ArtifactRecord | None = None
        try:
            if item["status"] == "ready":
                artifact_id = cast(UUID | None, item["artifact_id"])
                if artifact_id is not None:
                    self._link_if_stored(artifact_id)
                return JobHandlerResult.succeeded(
                    {"campaign_item_id": str(payload.campaign_item_id), "already_ready": True}
                )
            source_artifact = self._bound_source_artifact(item)
            if source_artifact is None:
                source_path = self._browser.resolve(cast(str, item["relative_path"]))
                before = _base._source_entry(
                    self._runtime.settings.historical_import_root,
                    source_path,
                )
                if _base._manifest_identity(before) != item["manifest_identity"]:
                    return JobHandlerResult.failed("historical_source_changed")
                with source_path.open("rb") as source:
                    source_artifact = self._artifacts.store_stream(
                        kind="historical-import.source",
                        content_type=_base._XLSX_CONTENT_TYPE,
                        retention_class="raw",
                        source=source,
                        max_bytes=_base.MAX_XLSX_FILE_BYTES,
                        filename_suffix=".xlsx",
                    )
                after = _base._source_entry(
                    self._runtime.settings.historical_import_root,
                    source_path,
                )
                if (
                    _base._manifest_identity(after) != item["manifest_identity"]
                    or _base._sha256_file(source_path) != source_artifact.sha256
                ):
                    return JobHandlerResult.failed("historical_source_changed")
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        _base.PostgresJobRepository(session).lock_current_execution(fence)
                        _base.PostgresHistoricalImportRepository(session).bind_source_artifact(
                            item_id=payload.campaign_item_id,
                            artifact_id=source_artifact.id,
                            sha256=source_artifact.sha256,
                        )
                finally:
                    session.close()
                self._artifacts.link(source_artifact.id)
            context.heartbeat(progress=15)
            if context.cancel_requested():
                return JobHandlerResult.cancelled()

            profile = cast(dict[str, object], campaign["profile_snapshot"])
            with TemporaryDirectory(prefix="aima-historical-snapshot-") as directory:
                work_dir = Path(directory)
                frozen_path = work_dir / "source.xlsx"
                with frozen_path.open("xb") as destination:
                    copied = self._runtime.artifact_store.copy_to(
                        source_artifact.storage_key,
                        destination,
                    )
                if (
                    copied.sha256 != source_artifact.sha256
                    or copied.byte_size != source_artifact.byte_size
                ):
                    raise _base.InvalidXlsxError("Historical Source Artifact 完整性校验失败")
                _base.validate_xlsx_archive(frozen_path)

                def publish(descriptor: _base.HistoricalChunkDescriptor) -> None:
                    self._publish_chunk(
                        source_item=item,
                        descriptor=descriptor,
                        fence=fence,
                    )
                    context.heartbeat(progress=min(90, 20 + descriptor.ordinal))

                summary = _base.convert_historical_excel_to_chunks(
                    input_path=frozen_path,
                    output_dir=work_dir / "chunks",
                    profile_name=_base._required_string(profile, "profile"),
                    filter_snapshot=filter_snapshot,
                    observed_at=cast(datetime, campaign["created_at"]),
                    chunk_rows=_base._required_int(profile, "chunk_rows"),
                    publish=publish,
                )
            if summary.rows_seen == 0 or summary.chunks == 0:
                return JobHandlerResult.failed("historical_source_empty")
            if context.cancel_requested():
                return JobHandlerResult.cancelled()
            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    _base.PostgresJobRepository(session).lock_current_execution(fence)
                    repository = _base.PostgresHistoricalImportRepository(session)
                    repository.complete_source_snapshot(
                        item_id=payload.campaign_item_id,
                        artifact_id=source_artifact.id,
                        sha256=source_artifact.sha256,
                        row_count=summary.rows_seen,
                        stats=asdict(summary),
                    )
                    repository.schedule_snapshot_jobs(
                        cast(UUID, item["campaign_id"]),
                        max_in_flight=self._runtime.settings.historical_max_in_flight_jobs,
                    )
                    repository.finalize_preflight(cast(UUID, item["campaign_id"]))
            finally:
                session.close()
            self._link_if_stored(source_artifact.id)
            return JobHandlerResult.succeeded(
                {
                    "campaign_item_id": str(payload.campaign_item_id),
                    "rows_seen": summary.rows_seen,
                    "chunks": summary.chunks,
                }
            )
        except LeaseLostError:
            raise
        except (
            _base.ArtifactSizeLimitError,
            _base.HistoricalDirectoryUnavailable,
            _base.InvalidHistoricalRelativePath,
            _base.InvalidXlsxError,
            _base.XlsxResourceLimitError,
            ValueError,
        ):
            return JobHandlerResult.failed("historical_snapshot_invalid")
        except OSError:
            return JobHandlerResult.retry("historical_snapshot_io_failed")

    def import_chunk(
        self,
        *,
        payload: _base.HistoricalImportChunkJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """v2 Chunk 与 Brand/Vehicle Snapshot 强配对；legacy Campaign 继续基线实现。"""

        try:
            item, artifact, campaign_id = self._load_import_chunk(payload, fence)
            campaign_snapshot = self._campaign_filter_payload(campaign_id)
            if campaign_snapshot.get("schema_version") != "brand-vehicle-filter.v1":
                return super().import_chunk(payload=payload, fence=fence, context=context)
            filter_snapshot = BrandVehicleFilterSnapshot.model_validate(campaign_snapshot)
            if item["status"] == "succeeded":
                return JobHandlerResult.succeeded(
                    {"chunk_item_id": str(payload.chunk_item_id), "already_succeeded": True}
                )
            if context.cancel_requested():
                return JobHandlerResult.cancelled()
            with TemporaryDirectory(prefix="aima-historical-import-") as directory:
                chunk_path = Path(directory) / "chunk.jsonl.gz"
                with chunk_path.open("xb") as destination:
                    copied = self._runtime.artifact_store.copy_to(
                        artifact.storage_key,
                        destination,
                    )
                if copied.sha256 != artifact.sha256 or copied.byte_size != artifact.byte_size:
                    raise ValueError("Historical Chunk Artifact 完整性校验失败")
                records = _base.read_historical_chunk(
                    chunk_path,
                    max_rows=self._runtime.settings.historical_chunk_rows,
                )
            if not records or any(
                record.get("schema_version") != HISTORICAL_CHUNK_SCHEMA_VERSION
                for record in records
            ):
                raise ValueError("Stage 3 Campaign 只能消费 historical-canonical-row.v2")

            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    jobs = _base.PostgresJobRepository(session)
                    jobs.lock_current_execution(fence)
                    _base.lock_historical_campaign_cancel_gate(session, campaign_id, shared=True)
                    repository = _base.PostgresHistoricalImportRepository(session)
                    campaign = repository.get_campaign(campaign_id)
                    if campaign is None:
                        return JobHandlerResult.failed("historical_campaign_not_found")
                    if campaign["status"] == "cancelling":
                        jobs.request_cancel(fence.job_id)
                        return JobHandlerResult.cancelled()
                    current = repository.get_item(payload.chunk_item_id, for_update=True)
                    if current is None:
                        return JobHandlerResult.failed("historical_chunk_not_found")
                    if current["status"] == "succeeded":
                        return JobHandlerResult.succeeded(
                            {"chunk_item_id": str(payload.chunk_item_id), "already_succeeded": True}
                        )
                    batch = (
                        session.execute(
                            _base.select(_base.processing_import_batches_table).where(
                                _base.processing_import_batches_table.c.id == payload.batch_id
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if batch is None or batch["status"] != "processing":
                        return JobHandlerResult.cancelled()
                    repository.mark_chunk_running(payload.chunk_item_id)
                    policy_version = cast(str, batch["historical_policy_version"])
                    rows = self._campaign_rows(
                        session=session,
                        batch_id=payload.batch_id,
                        artifact=artifact,
                        records=records,
                        policy_version=policy_version,
                    )
                    writer = (
                        _base.PostgresHistoricalContentRepository(session)
                        if policy_version == "historical-fill-only.v1"
                        else _base.PostgresStandardContentRepository(session)
                    )
                    summary = writer.ingest_rows(
                        batch_id=payload.batch_id,
                        campaign_item_id=payload.chunk_item_id,
                        chunk_ordinal=cast(int, current["ordinal"]),
                        rows=rows,
                    )
                    _append_historical_brand_vehicle_evidence(
                        session,
                        batch_id=payload.batch_id,
                        rows=rows,
                        filter_snapshot=filter_snapshot,
                    )
                    repository.complete_chunk(payload.chunk_item_id, stats=asdict(summary))
                    source_batches = repository.source_batches(campaign_id)
                    repository.schedule_import_jobs(
                        campaign_id=campaign_id,
                        source_batches=source_batches,
                        max_in_flight=self._runtime.settings.historical_max_in_flight_jobs,
                    )
                    status = repository.refresh_batch_and_campaign(
                        campaign_id=campaign_id,
                        batch_id=payload.batch_id,
                    )
                    jobs.lock_current_execution(fence)
            finally:
                session.close()
            return JobHandlerResult.succeeded(
                {
                    "chunk_item_id": str(payload.chunk_item_id),
                    "campaign_status": status,
                    **asdict(summary),
                }
            )
        except LeaseLostError:
            raise
        except ValueError, _base.InvalidXlsxError, _base.XlsxResourceLimitError:
            return JobHandlerResult.failed("historical_chunk_invalid")
        except OSError:
            return JobHandlerResult.retry("historical_chunk_io_failed")

    def _campaign_filter_payload(self, campaign_id: UUID) -> dict[str, object]:
        """只读取已冻结的 Campaign JSON Snapshot，不触碰实时 Brand/Vehicle 目录。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                campaign = _base.PostgresHistoricalImportRepository(session).get_campaign(
                    campaign_id
                )
                if campaign is None:
                    raise ValueError("Historical Campaign 不存在")
                return cast(dict[str, object], campaign["keyword_pack_snapshot"])
        finally:
            session.close()


def _append_historical_brand_vehicle_evidence(
    session: _base.Session,
    *,
    batch_id: UUID,
    rows: tuple[_base.HistoricalBatchRow, ...],
    filter_snapshot: BrandVehicleFilterSnapshot,
) -> None:
    """按行账本把同一冻结 Snapshot 的 Resolver 结果写回 Brand/Vehicle Evidence。"""

    candidate_by_ordinal = {
        row.source_row_ordinal: row.content
        for row in rows
        if row.content is not None and row.preclassified_outcome is None
    }
    if not candidate_by_ordinal:
        return
    ledgers = tuple(
        session.execute(
            _base.select(
                _base.processing_import_batch_items_table.c.source_row_ordinal,
                _base.processing_import_batch_items_table.c.content_id,
                _base.contents_table.c.current_version,
            )
            .join(
                _base.contents_table,
                _base.contents_table.c.id == _base.processing_import_batch_items_table.c.content_id,
            )
            .where(
                _base.processing_import_batch_items_table.c.batch_id == batch_id,
                _base.processing_import_batch_items_table.c.source_row_ordinal.in_(
                    tuple(candidate_by_ordinal)
                ),
                _base.processing_import_batch_items_table.c.content_id.is_not(None),
            )
        ).mappings()
    )
    vehicle_repository = PostgresVehicleCatalogRepository(session)
    brand_repository = PostgresBrandVehicleRepository(session)
    for ledger in ledgers:
        ordinal = cast(int, ledger["source_row_ordinal"])
        content = candidate_by_ordinal[ordinal]
        resolution = resolve_canonical_brand_vehicle(filter_snapshot, content)
        if not resolution.matched:
            raise ValueError("Historical candidate 与冻结 Brand/Vehicle Snapshot 发生解释漂移")
        content_id = cast(UUID, ledger["content_id"])
        content_version = cast(int, ledger["current_version"])
        for evidence in resolution.vehicle_evidence:
            vehicle_repository.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=content_version,
                    vehicle_model_id=evidence.entity_id,
                    source="import",
                    matched_text=evidence.matched_text,
                    source_field=evidence.source_field,
                    catalog_version=filter_snapshot.catalog.catalog_version,
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=_base.beijing_now(),
                )
            )
        brand_repository.replace_automatic_brand_evidence(
            content_id=content_id,
            content_version=content_version,
            evidence=resolution.brand_evidence,
            catalog_version=filter_snapshot.catalog.catalog_version,
        )


historical_job_terminal_callback = _base.historical_job_terminal_callback

__all__ = ["PostgresHistoricalImportJobExecutor", "historical_job_terminal_callback"]
