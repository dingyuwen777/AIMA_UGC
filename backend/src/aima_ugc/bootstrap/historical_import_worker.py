"""Stage 12 Historical Campaign 的正式 Worker 执行器与终态收敛。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_content import (
    HistoricalBatchRow,
    PostgresHistoricalContentRepository,
    PostgresStandardContentRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.adapters.providers.imports.historical_chunk import (
    HistoricalChunkDescriptor,
    convert_historical_excel_to_chunks,
)
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.ingestion.historical_chunk import (
    read_historical_chunk,
)
from aima_ugc.modules.ingestion.historical_directory import (
    HistoricalDirectoryBrowser,
    HistoricalDirectoryEntry,
    HistoricalDirectoryUnavailable,
    InvalidHistoricalRelativePath,
)
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
    HistoricalDiscoverJobPayload,
    HistoricalImportChunkJobPayload,
    HistoricalSnapshotJobPayload,
)
from aima_ugc.modules.ingestion.historical_tables import processing_import_batch_items_table
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.ingestion.xlsx_security import (
    MAX_XLSX_FILE_BYTES,
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_archive,
)
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRecord
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService, ArtifactSizeLimitError
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_GZIP_CONTENT_TYPE = "application/gzip"


class PostgresHistoricalImportJobExecutor:
    """目录发现、不可变快照和有界 Chunk 导入的生产执行器。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._browser = HistoricalDirectoryBrowser(runtime.settings.historical_import_root)
        self._artifacts = ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.database.new_session),
            store=runtime.artifact_store,
        )

    def discover(
        self,
        *,
        payload: HistoricalDiscoverJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        try:
            campaign, profile = self._load_campaign(payload.campaign_id, fence)
            if campaign["status"] != "discovering":
                return JobHandlerResult.succeeded(
                    {"campaign_id": str(payload.campaign_id), "already_discovered": True}
                )
            selected = _string_tuple(profile.get("relative_paths"))
            entries = self._browser.discover_xlsx(
                relative_paths=selected,
                recursive=cast(bool, campaign["recursive"]),
                max_files=self._runtime.settings.historical_max_scan_files,
                max_depth=self._runtime.settings.historical_max_directory_depth,
            )
            if not entries:
                return JobHandlerResult.failed("historical_no_xlsx_files")
            context.heartbeat(progress=50)
            if context.cancel_requested():
                return JobHandlerResult.cancelled()
            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    PostgresJobRepository(session).lock_current_execution(fence)
                    repository = PostgresHistoricalImportRepository(session)
                    current = repository.get_campaign(payload.campaign_id, for_update=True)
                    if current is None:
                        return JobHandlerResult.failed("historical_campaign_not_found")
                    if current["status"] == "discovering":
                        repository.insert_source_items(
                            campaign_id=payload.campaign_id,
                            entries=entries,
                        )
                        repository.mark_discovered(
                            payload.campaign_id,
                            file_count=len(entries),
                        )
                    repository.schedule_snapshot_jobs(
                        payload.campaign_id,
                        max_in_flight=self._runtime.settings.historical_max_in_flight_jobs,
                    )
            finally:
                session.close()
            return JobHandlerResult.succeeded(
                {"campaign_id": str(payload.campaign_id), "file_count": len(entries)}
            )
        except LeaseLostError:
            raise
        except (
            HistoricalDirectoryUnavailable,
            InvalidHistoricalRelativePath,
            ValueError,
        ):
            return JobHandlerResult.failed("historical_discovery_invalid")
        except OSError:
            return JobHandlerResult.retry("historical_discovery_io_failed")

    def snapshot(
        self,
        *,
        payload: HistoricalSnapshotJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        source_artifact: ArtifactRecord | None = None
        try:
            item, campaign = self._load_snapshot_item(payload.campaign_item_id, fence)
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
                before = _source_entry(self._runtime.settings.historical_import_root, source_path)
                if _manifest_identity(before) != item["manifest_identity"]:
                    return JobHandlerResult.failed("historical_source_changed")
                with source_path.open("rb") as source:
                    source_artifact = self._artifacts.store_stream(
                        kind="historical-import.source",
                        content_type=_XLSX_CONTENT_TYPE,
                        retention_class="raw",
                        source=source,
                        max_bytes=MAX_XLSX_FILE_BYTES,
                        filename_suffix=".xlsx",
                    )
                after = _source_entry(self._runtime.settings.historical_import_root, source_path)
                if (
                    _manifest_identity(after) != item["manifest_identity"]
                    or _sha256_file(source_path) != source_artifact.sha256
                ):
                    return JobHandlerResult.failed("historical_source_changed")
                session = self._runtime.database.new_session()
                try:
                    with session.begin():
                        PostgresJobRepository(session).lock_current_execution(fence)
                        PostgresHistoricalImportRepository(session).bind_source_artifact(
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
            keywords = cast(dict[str, object], campaign["keyword_pack_snapshot"])
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
                    raise InvalidXlsxError("Historical Source Artifact 完整性校验失败")
                validate_xlsx_archive(frozen_path)

                def publish(descriptor: HistoricalChunkDescriptor) -> None:
                    self._publish_chunk(
                        source_item=item,
                        descriptor=descriptor,
                        fence=fence,
                    )
                    context.heartbeat(progress=min(90, 20 + descriptor.ordinal))

                summary = convert_historical_excel_to_chunks(
                    input_path=frozen_path,
                    output_dir=work_dir / "chunks",
                    profile_name=_required_string(profile, "profile"),
                    effective_keywords=_optional_string_tuple(
                        keywords.get("effective_keywords")
                    ),
                    vehicle_aliases=tuple(
                        alias
                        for model in _mapping_tuple(keywords.get("vehicle_models"))
                        for alias in _string_tuple(model.get("aliases"))
                    ),
                    observed_at=cast(datetime, campaign["created_at"]),
                    chunk_rows=_required_int(profile, "chunk_rows"),
                    publish=publish,
                )
            if summary.rows_seen == 0 or summary.chunks == 0:
                return JobHandlerResult.failed("historical_source_empty")
            if context.cancel_requested():
                return JobHandlerResult.cancelled()
            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    PostgresJobRepository(session).lock_current_execution(fence)
                    repository = PostgresHistoricalImportRepository(session)
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
            ArtifactSizeLimitError,
            HistoricalDirectoryUnavailable,
            InvalidHistoricalRelativePath,
            InvalidXlsxError,
            XlsxResourceLimitError,
            ValueError,
        ):
            return JobHandlerResult.failed("historical_snapshot_invalid")
        except OSError:
            return JobHandlerResult.retry("historical_snapshot_io_failed")

    def import_chunk(
        self,
        *,
        payload: HistoricalImportChunkJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        try:
            item, artifact, campaign_id = self._load_import_chunk(payload, fence)
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
                records = read_historical_chunk(
                    chunk_path,
                    max_rows=self._runtime.settings.historical_chunk_rows,
                )
            session = self._runtime.database.new_session()
            try:
                with session.begin():
                    jobs = PostgresJobRepository(session)
                    jobs.lock_current_execution(fence)
                    repository = PostgresHistoricalImportRepository(session)
                    current = repository.get_item(payload.chunk_item_id, for_update=True)
                    if current is None:
                        return JobHandlerResult.failed("historical_chunk_not_found")
                    if current["status"] == "succeeded":
                        return JobHandlerResult.succeeded(
                            {"chunk_item_id": str(payload.chunk_item_id), "already_succeeded": True}
                        )
                    batch = (
                        session.execute(
                            select(processing_import_batches_table).where(
                                processing_import_batches_table.c.id == payload.batch_id
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
                        PostgresHistoricalContentRepository(session)
                        if policy_version == "historical-fill-only.v1"
                        else PostgresStandardContentRepository(session)
                    )
                    summary = writer.ingest_rows(
                        batch_id=payload.batch_id,
                        campaign_item_id=payload.chunk_item_id,
                        chunk_ordinal=cast(int, current["ordinal"]),
                        rows=rows,
                    )
                    campaign = repository.get_campaign(campaign_id)
                    if campaign is None:
                        raise ValueError("Historical Campaign 不存在")
                    _append_historical_vehicle_evidence(
                        session,
                        batch_id=payload.batch_id,
                        rows=rows,
                        keyword_snapshot=cast(
                            dict[str, object], campaign["keyword_pack_snapshot"]
                        ),
                    )
                    repository.complete_chunk(
                        payload.chunk_item_id,
                        stats=asdict(summary),
                    )
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
        except ValueError, InvalidXlsxError, XlsxResourceLimitError:
            return JobHandlerResult.failed("historical_chunk_invalid")
        except OSError:
            return JobHandlerResult.retry("historical_chunk_io_failed")

    def _load_campaign(
        self,
        campaign_id: UUID,
        fence: JobExecutionFence,
    ) -> tuple[RowMapping, dict[str, object]]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                campaign = PostgresHistoricalImportRepository(session).get_campaign(campaign_id)
                if campaign is None:
                    raise ValueError("Historical Campaign 不存在")
                return campaign, cast(dict[str, object], campaign["profile_snapshot"])
        finally:
            session.close()

    def _load_snapshot_item(
        self,
        item_id: UUID,
        fence: JobExecutionFence,
    ) -> tuple[RowMapping, RowMapping]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresHistoricalImportRepository(session)
                item = repository.get_item(item_id)
                if item is None or item["item_kind"] != "source_file":
                    raise ValueError("Historical Source Item 不存在")
                campaign = repository.get_campaign(cast(UUID, item["campaign_id"]))
                if campaign is None:
                    raise ValueError("Historical Campaign 不存在")
                return item, campaign
        finally:
            session.close()

    def _load_import_chunk(
        self,
        payload: HistoricalImportChunkJobPayload,
        fence: JobExecutionFence,
    ) -> tuple[RowMapping, ArtifactRecord, UUID]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresHistoricalImportRepository(session)
                item = repository.get_item(payload.chunk_item_id)
                if item is None or item["item_kind"] != "chunk":
                    raise ValueError("Historical Chunk Item 不存在")
                artifact_id = cast(UUID | None, item["artifact_id"])
                if artifact_id is None:
                    raise ValueError("Historical Chunk 缺少 Artifact")
                artifact = PostgresArtifactMetadataRepository(session).get(artifact_id)
                if artifact is None or artifact.storage_status not in {"stored", "linked"}:
                    raise ValueError("Historical Chunk Artifact 不可用")
                batch = (
                    session.execute(
                        select(processing_import_batches_table).where(
                            processing_import_batches_table.c.id == payload.batch_id,
                            processing_import_batches_table.c.historical_campaign_item_id
                            == item["parent_item_id"],
                            processing_import_batches_table.c.historical_policy_version.in_(
                                ("historical-fill-only.v1", "standard-observation.v1")
                            ),
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if batch is None:
                    raise ValueError("Historical Chunk 与 Batch 来源不一致")
                return item, artifact, cast(UUID, item["campaign_id"])
        finally:
            session.close()

    def _bound_source_artifact(self, item: RowMapping) -> ArtifactRecord | None:
        artifact_id = cast(UUID | None, item["artifact_id"])
        if artifact_id is None:
            return None
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                artifact = PostgresArtifactMetadataRepository(session).get(artifact_id)
                if (
                    artifact is None
                    or artifact.storage_status not in {"stored", "linked"}
                    or artifact.sha256 != item["sha256"]
                ):
                    raise InvalidXlsxError("Historical Source Artifact 不可用")
                return artifact
        finally:
            session.close()

    def _publish_chunk(
        self,
        *,
        source_item: RowMapping,
        descriptor: HistoricalChunkDescriptor,
        fence: JobExecutionFence,
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                existing = PostgresHistoricalImportRepository(session).get_chunk(
                    cast(UUID, source_item["id"]),
                    descriptor.ordinal,
                )
                if existing is not None:
                    if existing["sha256"] != _sha256_file(descriptor.path):
                        raise ValueError("Historical Chunk 重放内容不一致")
                    artifact_id = cast(UUID | None, existing["artifact_id"])
                    if artifact_id is not None:
                        self._link_if_stored(artifact_id)
                    return
        finally:
            session.close()
        with descriptor.path.open("rb") as source:
            artifact = self._artifacts.store_stream(
                kind="historical-import.chunk",
                content_type=_GZIP_CONTENT_TYPE,
                retention_class="raw",
                source=source,
                max_bytes=MAX_XLSX_FILE_BYTES,
                filename_suffix=".gz",
            )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                PostgresHistoricalImportRepository(session).create_chunk(
                    source_item=source_item,
                    artifact_id=artifact.id,
                    sha256=cast(str, artifact.sha256),
                    ordinal=descriptor.ordinal,
                    row_start=descriptor.row_start,
                    row_end=descriptor.row_end,
                    row_count=descriptor.row_count,
                    stats={
                        "candidate": descriptor.candidate_count,
                        "filtered": descriptor.filtered_count,
                        "invalid": descriptor.invalid_count,
                    },
                )
        finally:
            session.close()
        self._artifacts.link(artifact.id)

    def _link_if_stored(self, artifact_id: UUID) -> None:
        """补偿业务引用已提交、Artifact linked 状态尚未提交的崩溃窗口。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresArtifactMetadataRepository(session)
                artifact = repository.get(artifact_id)
                if artifact is not None and artifact.storage_status == "stored":
                    repository.mark_linked(artifact_id, linked_at=beijing_now())
        finally:
            session.close()

    def _campaign_rows(
        self,
        *,
        session: Session,
        batch_id: UUID,
        artifact: ArtifactRecord,
        records: tuple[dict[str, object], ...],
        policy_version: str,
    ) -> tuple[HistoricalBatchRow, ...]:
        if policy_version == "historical-fill-only.v1":
            operation = "historical_excel_import"
        elif policy_version == "standard-observation.v1":
            operation = "excel_import"
        else:
            raise ValueError("Data Import Campaign 写入策略不受支持")
        candidates = [record for record in records if record.get("outcome") == "candidate"]
        platforms = sorted(
            {CanonicalContentV1.model_validate(record["content"]).platform for record in candidates}
        )
        lineage = {
            platform: _campaign_lineage(
                session=session,
                batch_id=batch_id,
                platform=platform,
                artifact=artifact,
                operation=operation,
            )
            for platform in platforms
        }
        rows: list[HistoricalBatchRow] = []
        for record in records:
            ordinal = cast(int, record["source_row_ordinal"])
            outcome = record.get("outcome")
            if outcome == "invalid":
                rows.append(
                    HistoricalBatchRow(
                        source_row_ordinal=ordinal,
                        content=None,
                        preclassified_outcome="invalid",
                        error_code=cast(str, record.get("error_code")),
                        matched_vehicle_aliases=(),
                    )
                )
                continue
            content = CanonicalContentV1.model_validate(record["content"])
            if outcome == "filtered":
                rows.append(
                    HistoricalBatchRow(
                        source_row_ordinal=ordinal,
                        content=content,
                        preclassified_outcome="filtered",
                        matched_vehicle_aliases=(),
                    )
                )
                continue
            if outcome != "candidate":
                raise ValueError("Historical Chunk outcome 不受支持")
            request_id, attempt_id = lineage[content.platform]
            source = content.source.model_copy(
                update={
                    "provider_name": "imports",
                    "operation": operation,
                    "provider_request_id": str(request_id),
                    "provider_attempt_id": str(attempt_id),
                    "raw_artifact_id": artifact.id,
                }
            )
            rows.append(
                HistoricalBatchRow(
                    source_row_ordinal=ordinal,
                    content=content.model_copy(update={"source": source}),
                    matched_vehicle_aliases=_optional_string_tuple(
                        record.get("matched_vehicle_aliases")
                    ),
                )
            )
        return tuple(rows)


def _append_historical_vehicle_evidence(
    session: Session,
    *,
    batch_id: UUID,
    rows: tuple[HistoricalBatchRow, ...],
    keyword_snapshot: dict[str, object],
) -> None:
    """用 Campaign 冻结别名映射追加证据，不读取实时目录重新解释历史结果。"""

    matched_by_ordinal = {
        row.source_row_ordinal: row.matched_vehicle_aliases
        for row in rows
        if row.matched_vehicle_aliases
    }
    if not matched_by_ordinal:
        return
    catalog_version = _required_int(keyword_snapshot, "vehicle_catalog_version")
    model_by_alias: dict[str, UUID] = {}
    for model in _mapping_tuple(keyword_snapshot.get("vehicle_models")):
        model_id = UUID(_required_string(model, "id"))
        for alias in _string_tuple(model.get("aliases")):
            model_by_alias[alias] = model_id
    ledgers = tuple(
        session.execute(
            select(
                processing_import_batch_items_table.c.source_row_ordinal,
                processing_import_batch_items_table.c.content_id,
                contents_table.c.current_version,
            )
            .join(
                contents_table,
                contents_table.c.id == processing_import_batch_items_table.c.content_id,
            )
            .where(
                processing_import_batch_items_table.c.batch_id == batch_id,
                processing_import_batch_items_table.c.source_row_ordinal.in_(
                    tuple(matched_by_ordinal)
                ),
                processing_import_batch_items_table.c.content_id.is_not(None),
            )
        ).mappings()
    )
    vehicle_repository = PostgresVehicleCatalogRepository(session)
    for ledger in ledgers:
        ordinal = cast(int, ledger["source_row_ordinal"])
        for alias in matched_by_ordinal[ordinal]:
            resolved_model_id = model_by_alias.get(alias)
            if resolved_model_id is None:
                raise ValueError("Historical Chunk 车型别名不在冻结快照中")
            vehicle_repository.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=cast(UUID, ledger["content_id"]),
                    content_version=cast(int, ledger["current_version"]),
                    vehicle_model_id=resolved_model_id,
                    source="import",
                    matched_text=alias,
                    source_field="title_text",
                    catalog_version=catalog_version,
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )


def historical_job_terminal_callback(session: Session, job: JobRecord) -> None:
    """与 Job 终态同事务收敛 Campaign/Item，覆盖 Deadline、取消和次数耗尽。"""

    if job.status == "succeeded":
        return
    repository = PostgresHistoricalImportRepository(session)
    if job.job_type == HISTORICAL_DISCOVER_JOB_TYPE:
        discover_payload = HistoricalDiscoverJobPayload.model_validate(job.payload)
        repository.fail_campaign(
            discover_payload.campaign_id,
            error_code=job.error_code or job.status,
        )
        return
    if job.job_type == HISTORICAL_SNAPSHOT_JOB_TYPE:
        snapshot_payload = HistoricalSnapshotJobPayload.model_validate(job.payload)
        item = repository.get_item(snapshot_payload.campaign_item_id, for_update=True)
        if item is None:
            return
        if job.status == "cancelled":
            repository.cancel_item(snapshot_payload.campaign_item_id)
        else:
            repository.fail_item(
                snapshot_payload.campaign_item_id,
                error_code=job.error_code or job.status,
            )
        campaign_id = cast(UUID, item["campaign_id"])
        campaign = repository.get_campaign(campaign_id)
        if campaign is not None and campaign["status"] == "snapshotting":
            repository.schedule_snapshot_jobs(
                campaign_id,
                max_in_flight=_campaign_max_in_flight(campaign),
            )
            repository.finalize_preflight(campaign_id)
        return
    if job.job_type != HISTORICAL_IMPORT_CHUNK_JOB_TYPE:
        return
    chunk_payload = HistoricalImportChunkJobPayload.model_validate(job.payload)
    item = repository.get_item(chunk_payload.chunk_item_id, for_update=True)
    if item is None:
        return
    if job.status == "cancelled":
        repository.cancel_item(chunk_payload.chunk_item_id)
    else:
        repository.fail_item(
            chunk_payload.chunk_item_id,
            error_code=job.error_code or job.status,
        )
    campaign_id = cast(UUID, item["campaign_id"])
    campaign = repository.get_campaign(campaign_id)
    if campaign is not None and campaign["status"] in {"queued", "running"}:
        repository.schedule_import_jobs(
            campaign_id=campaign_id,
            source_batches=repository.source_batches(campaign_id),
            max_in_flight=_campaign_max_in_flight(campaign),
        )
    repository.refresh_batch_and_campaign(
        campaign_id=campaign_id,
        batch_id=chunk_payload.batch_id,
    )


def _campaign_lineage(
    *,
    session: Session,
    batch_id: UUID,
    platform: str,
    artifact: ArtifactRecord,
    operation: str,
) -> tuple[UUID, UUID]:
    lineage_key = f"{platform}:{artifact.id}:{artifact.sha256}"
    request_id = uuid5(batch_id, f"campaign-provider-request:{operation}:{lineage_key}")
    attempt_id = uuid5(batch_id, f"campaign-provider-attempt:{operation}:{lineage_key}")
    request = ProviderRequestV1.create_for_import(
        request_id=request_id,
        import_batch_id=batch_id,
        provider="imports",
        platform=platform,
        operation=operation,
        request_params={"chunk_artifact_sha256": artifact.sha256},
        pagination_input={},
    )
    repository = PostgresProviderRepository(session)
    prepared = ProviderPersistenceService(repository).prepare_non_billable_attempt(
        request=request,
        attempt_id=attempt_id,
    )
    dispatching = repository.mark_dispatching(prepared.attempt.id)
    if dispatching.dispatch_started_at is None:
        raise RuntimeError("Data Import Campaign Attempt 未进入 dispatching")
    repository.finalize_dispatch(
        attempt=ProviderAttemptV1(
            attempt_id=dispatching.id,
            provider_request_id=prepared.request.id,
            attempt_no=dispatching.attempt_no,
            dispatch_status="completed",
            dispatch_started_at=dispatching.dispatch_started_at,
            completed_at=beijing_now(),
            raw_artifact_id=artifact.id,
            billing=ProviderBillingV1(status="not_billable"),
            created_at=dispatching.created_at,
        ),
        raw_artifact_id=artifact.id,
    )
    return prepared.request.id, dispatching.id


def _source_entry(root: Path | None, path: Path) -> HistoricalDirectoryEntry:
    if root is None:
        raise HistoricalDirectoryUnavailable("未配置历史导入根目录")
    resolved_root = root.resolve(strict=True)
    stat = path.stat(follow_symlinks=False)
    return HistoricalDirectoryEntry(
        relative_path=path.relative_to(resolved_root).as_posix(),
        name=path.name,
        kind="file",
        byte_size=stat.st_size,
        modified_at_ns=stat.st_mtime_ns,
    )


def _manifest_identity(entry: HistoricalDirectoryEntry) -> str:
    payload = json.dumps(
        [entry.relative_path, entry.byte_size, entry.modified_at_ns],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not value:
        raise ValueError("冻结配置缺少非空字符串列表")
    result = tuple(item for item in value if isinstance(item, str) and item)
    if len(result) != len(value):
        raise ValueError("冻结配置字符串列表不合法")
    return result


def _optional_string_tuple(value: object) -> tuple[str, ...]:
    """严格解析允许为空的冻结字符串序列。"""

    if not isinstance(value, list | tuple):
        raise ValueError("冻结配置字符串列表不合法")
    result = tuple(item for item in value if isinstance(item, str) and item)
    if len(result) != len(value):
        raise ValueError("冻结配置字符串列表不合法")
    return result


def _mapping_tuple(value: object) -> tuple[dict[str, object], ...]:
    """严格解析冻结配置中的对象序列。"""

    if not isinstance(value, list | tuple):
        raise ValueError("冻结配置对象列表不合法")
    result = tuple(item for item in value if isinstance(item, dict))
    if len(result) != len(value):
        raise ValueError("冻结配置对象列表不合法")
    return result


def _required_string(values: dict[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"冻结配置缺少 {key}")
    return value


def _required_int(values: dict[str, object], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"冻结配置缺少 {key}")
    return value


def _campaign_max_in_flight(campaign: RowMapping) -> int:
    profile = cast(dict[str, object], campaign["profile_snapshot"])
    return _required_int(profile, "max_in_flight_jobs")


__all__ = [
    "PostgresHistoricalImportJobExecutor",
    "historical_job_terminal_callback",
]
