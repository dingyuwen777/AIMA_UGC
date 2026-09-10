"""Persistent Canonical Replay 的正式 PostgreSQL Job 执行器。"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from itertools import islice
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.canonical_replay import (
    PostgresCanonicalReplayRepository,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.import_lineage import (
    ensure_campaign_import_lineage,
    ensure_single_import_lineage,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.collection.tables import (
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.ingestion.brand_vehicle_filter import resolve_canonical_brand_vehicle
from aima_ugc.modules.ingestion.canonical_replay import (
    CanonicalReplayArtifactRecord,
    CanonicalReplayCounters,
    CanonicalReplayJobPayload,
    CanonicalReplayRunRecord,
)
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaign_items_table
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.modules.vehicles.brand_vehicle import BrandVehicleResolution
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol, LeaseLostError
from aima_ugc.platform.storage import (
    ArtifactRecord,
    CanonicalArtifactIntegrityError,
    CanonicalArtifactReader,
)
from aima_ugc.platform.storage.tables import canonical_artifact_links_table
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime

_PREFLIGHT_BATCH_SIZE = 500


@dataclass(frozen=True, slots=True)
class _ImportLineageContext:
    batch_id: UUID
    raw_artifact: ArtifactRecord
    operation: str


class PostgresCanonicalReplayJobExecutor:
    """先预检完整输入集，再按有界批次和当前 Fence 幂等 Replay。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._reader = CanonicalArtifactReader(store=runtime.artifact_store)

    def execute(
        self,
        *,
        payload: CanonicalReplayJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        """接管先重新预检全部输入；随后从已提交 checkpoint 继续。"""

        try:
            run, selected = self._load_execution(payload.run_id, fence)
            if run.checkpoint_artifact_ordinal >= run.artifact_count:
                return JobHandlerResult.succeeded(_result(run))

            if not self._preflight_all(selected, fence=fence, context=context):
                return JobHandlerResult.cancelled()

            while True:
                run, selected = self._load_execution(payload.run_id, fence)
                if run.checkpoint_artifact_ordinal >= run.artifact_count:
                    return JobHandlerResult.succeeded(_result(run))
                if context.cancel_requested():
                    return JobHandlerResult.cancelled()
                current = selected[run.checkpoint_artifact_ordinal]
                artifact = self._load_artifact(current, fence=fence)
                iterator = cast(
                    Generator[CanonicalContentV1],
                    self._reader.read(artifact),
                )
                try:
                    for _ in islice(iterator, run.checkpoint_row_number):
                        pass
                    batch = tuple(islice(iterator, run.batch_size))
                finally:
                    iterator.close()

                if not batch:
                    run = self._advance_empty_artifact(run, current, fence=fence)
                else:
                    run = self._ingest_batch(
                        run,
                        current,
                        artifact,
                        batch,
                        fence=fence,
                    )
                context.heartbeat(progress=_progress(run))
        except LeaseLostError:
            raise
        except CanonicalArtifactIntegrityError:
            return JobHandlerResult.failed("canonical_replay_artifact_invalid")
        except LookupError, ValueError:
            return JobHandlerResult.failed("canonical_replay_input_invalid")
        except OSError, SQLAlchemyError:
            return JobHandlerResult.retry("canonical_replay_transient_error")

    def _load_execution(
        self,
        run_id: UUID,
        fence: JobExecutionFence,
    ) -> tuple[CanonicalReplayRunRecord, tuple[CanonicalReplayArtifactRecord, ...]]:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                run = repository.get(run_id)
                if run is None or run.job_id != fence.job_id:
                    raise LookupError("Canonical Replay Run 不属于当前 Job")
                selected = repository.list_artifacts(run_id)
                if len(selected) != run.artifact_count or tuple(
                    item.ordinal for item in selected
                ) != tuple(range(run.artifact_count)):
                    raise ValueError("Canonical Replay 输入顺序不完整")
                return run, selected
        finally:
            session.close()

    def _load_artifact(
        self,
        selected: CanonicalReplayArtifactRecord,
        *,
        fence: JobExecutionFence,
    ) -> ArtifactRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                if repository.classify_artifact(selected.artifact_id) != selected.source_kind:
                    raise ValueError("Canonical Replay 输入来源类型发生漂移")
                artifact = repository.load_artifact(selected.artifact_id)
                if artifact is None:
                    raise LookupError("Canonical Replay Artifact 不存在")
                return artifact
        finally:
            session.close()

    def _preflight_all(
        self,
        selected: tuple[CanonicalReplayArtifactRecord, ...],
        *,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> bool:
        """在首个 Content 写入前验证全部字节、Contract 与逐行来源。"""

        for item in selected:
            artifact = self._load_artifact(item, fence=fence)
            iterator = cast(
                Generator[CanonicalContentV1],
                self._reader.read(artifact),
            )
            try:
                while True:
                    batch = tuple(islice(iterator, _PREFLIGHT_BATCH_SIZE))
                    if not batch:
                        break
                    self._validate_source_rows(item, batch, fence=fence)
                    if context.cancel_requested():
                        return False
            finally:
                iterator.close()
        return True

    def _validate_source_rows(
        self,
        selected: CanonicalReplayArtifactRecord,
        contents: tuple[CanonicalContentV1, ...],
        *,
        fence: JobExecutionFence,
    ) -> None:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).validate_current_execution(fence)
                if selected.source_kind in {
                    "excel_import_v2",
                    "data_import_canonical_chunk_v2",
                }:
                    for content in contents:
                        source = content.source
                        if (
                            source.provider_name != "imports"
                            or source.operation != "excel_import"
                            or source.provider_request_id is not None
                            or source.provider_attempt_id is not None
                            or source.raw_artifact_id is not None
                        ):
                            raise ValueError("Import Canonical Source 不符合当前持久格式")
                    return

                parent_run_id = session.scalar(
                    select(collection_scopes_table.c.run_id)
                    .select_from(
                        canonical_artifact_links_table.join(
                            provider_request_attempts_table,
                            canonical_artifact_links_table.c.provider_attempt_id
                            == provider_request_attempts_table.c.id,
                        )
                        .join(
                            provider_requests_table,
                            provider_request_attempts_table.c.provider_request_id
                            == provider_requests_table.c.id,
                        )
                        .join(
                            collection_scopes_table,
                            provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                        )
                    )
                    .where(canonical_artifact_links_table.c.artifact_id == selected.artifact_id)
                )
                if parent_run_id is None:
                    raise ValueError("TikHub Canonical 缺少父级 Collection Run")
                attempt_ids: set[UUID] = set()
                expected_raw: dict[UUID, UUID] = {}
                expected_request: dict[UUID, UUID] = {}
                for content in contents:
                    source = content.source
                    if (
                        source.provider_name != "tikhub"
                        or source.provider_request_id is None
                        or source.provider_attempt_id is None
                        or source.raw_artifact_id is None
                    ):
                        raise ValueError("TikHub Canonical Source 缺少 Request/Attempt/Raw")
                    try:
                        request_id = UUID(source.provider_request_id)
                        attempt_id = UUID(source.provider_attempt_id)
                    except ValueError as exc:
                        raise ValueError("TikHub Canonical Request/Attempt 不是 UUID") from exc
                    previous_raw = expected_raw.setdefault(attempt_id, source.raw_artifact_id)
                    if previous_raw != source.raw_artifact_id:
                        raise ValueError("同一 TikHub Attempt 指向多个 Raw")
                    previous_request = expected_request.setdefault(attempt_id, request_id)
                    if previous_request != request_id:
                        raise ValueError("同一 TikHub Attempt 指向多个 Request")
                    attempt_ids.add(attempt_id)
                rows = session.execute(
                    select(
                        provider_request_attempts_table.c.id,
                        provider_request_attempts_table.c.provider_request_id,
                        provider_request_attempts_table.c.raw_artifact_id,
                        collection_scopes_table.c.run_id,
                    )
                    .join(
                        provider_requests_table,
                        provider_request_attempts_table.c.provider_request_id
                        == provider_requests_table.c.id,
                    )
                    .join(
                        collection_scopes_table,
                        provider_requests_table.c.scope_id == collection_scopes_table.c.id,
                    )
                    .where(
                        provider_request_attempts_table.c.id.in_(attempt_ids),
                        provider_requests_table.c.provider == "tikhub",
                    )
                )
                actual = {
                    cast(UUID, row.id): (
                        cast(UUID, row.provider_request_id),
                        cast(UUID | None, row.raw_artifact_id),
                        row.run_id,
                    )
                    for row in rows
                }
                if set(actual) != attempt_ids or any(
                    actual[item] != (expected_request[item], expected_raw[item], parent_run_id)
                    for item in attempt_ids
                ):
                    raise ValueError(
                        "TikHub Canonical Request/Attempt/Raw 不属于同一 Collection Run"
                    )
        finally:
            session.close()

    def _advance_empty_artifact(
        self,
        run: CanonicalReplayRunRecord,
        selected: CanonicalReplayArtifactRecord,
        *,
        fence: JobExecutionFence,
    ) -> CanonicalReplayRunRecord:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                return PostgresCanonicalReplayRepository(session).advance(
                    run_id=run.id,
                    expected_artifact_ordinal=selected.ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=selected.ordinal + 1,
                    next_row_number=0,
                    counters=_zero_counters(),
                    fence=fence,
                )
        finally:
            session.close()

    def _ingest_batch(
        self,
        run: CanonicalReplayRunRecord,
        selected: CanonicalReplayArtifactRecord,
        artifact: ArtifactRecord,
        contents: tuple[CanonicalContentV1, ...],
        *,
        fence: JobExecutionFence,
    ) -> CanonicalReplayRunRecord:
        resolved = tuple(
            (content, resolve_canonical_brand_vehicle(run.filter_snapshot, content))
            for content in contents
        )
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                repository = PostgresCanonicalReplayRepository(session)
                current = repository.get(run.id, for_update=True)
                if (
                    current is None
                    or current.job_id != fence.job_id
                    or current.checkpoint_artifact_ordinal != selected.ordinal
                    or current.checkpoint_row_number != run.checkpoint_row_number
                ):
                    raise LeaseLostError("Canonical Replay checkpoint 已不属于当前执行")
                lineage = self._load_import_lineage_context(session, selected, artifact)
                content_owner = ContentIngestionService(PostgresCompleteContentRepository(session))
                vehicle_repository = PostgresVehicleCatalogRepository(session)
                brand_repository = PostgresBrandVehicleRepository(session)
                matched = 0
                duplicates = 0
                inserted = 0
                existing = 0
                lineage_by_platform: dict[str, tuple[UUID, UUID]] = {}
                for content, resolution in resolved:
                    if not resolution.matched:
                        continue
                    matched += 1
                    if not repository.claim_content_identity(
                        run_id=run.id,
                        platform=content.platform,
                        external_content_id=content.external_content_id,
                    ):
                        duplicates += 1
                        continue
                    observation = self._content_with_lineage(
                        session,
                        content,
                        selected=selected,
                        lineage=lineage,
                        lineage_by_platform=lineage_by_platform,
                    )
                    result = content_owner.ingest_content(observation)
                    if result.version_created and result.version_no == 1:
                        inserted += 1
                    else:
                        existing += 1
                    self._write_evidence(
                        vehicle_repository=vehicle_repository,
                        brand_repository=brand_repository,
                        content_id=result.target_id,
                        content_version=result.version_no,
                        resolution=resolution,
                        run=run,
                    )
                counters = CanonicalReplayCounters(
                    rows_seen=len(contents),
                    rows_matched=matched,
                    rows_filtered_out=len(contents) - matched,
                    duplicates_removed=duplicates,
                    rows_ingested=inserted,
                    existing_convergence=existing,
                )
                return repository.advance(
                    run_id=run.id,
                    expected_artifact_ordinal=selected.ordinal,
                    expected_row_number=run.checkpoint_row_number,
                    next_artifact_ordinal=selected.ordinal,
                    next_row_number=run.checkpoint_row_number + len(contents),
                    counters=counters,
                    fence=fence,
                )
        finally:
            session.close()

    def _load_import_lineage_context(
        self,
        session: Session,
        selected: CanonicalReplayArtifactRecord,
        artifact: ArtifactRecord,
    ) -> _ImportLineageContext | None:
        if selected.source_kind == "tikhub_search_attempt_v1":
            return None
        if selected.source_kind == "excel_import_v2":
            row = session.execute(
                select(
                    processing_import_batches_table.c.id,
                    processing_import_batches_table.c.input_artifact_id,
                )
                .join(
                    canonical_artifact_links_table,
                    canonical_artifact_links_table.c.processing_import_batch_id
                    == processing_import_batches_table.c.id,
                )
                .where(canonical_artifact_links_table.c.artifact_id == artifact.id)
            ).one_or_none()
            if row is None:
                raise ValueError("Excel Canonical 缺少 Import Batch")
            raw = PostgresArtifactMetadataRepository(session).get(cast(UUID, row.input_artifact_id))
            if raw is None or raw.storage_status != "linked":
                raise ValueError("Excel Input Artifact 不可用")
            return _ImportLineageContext(cast(UUID, row.id), raw, "excel_import")

        row = session.execute(
            select(
                processing_import_batches_table.c.id,
                processing_import_batches_table.c.historical_policy_version,
            )
            .select_from(
                canonical_artifact_links_table.join(
                    historical_import_campaign_items_table,
                    canonical_artifact_links_table.c.historical_import_campaign_item_id
                    == historical_import_campaign_items_table.c.id,
                ).join(
                    processing_import_batches_table,
                    processing_import_batches_table.c.historical_campaign_item_id
                    == historical_import_campaign_items_table.c.parent_item_id,
                )
            )
            .where(canonical_artifact_links_table.c.artifact_id == artifact.id)
        ).one_or_none()
        if row is None:
            raise ValueError("Data Import Canonical 缺少当前 Processing Batch")
        policy = cast(str | None, row.historical_policy_version)
        if policy == "historical-fill-only.v1":
            operation = "historical_excel_import"
        elif policy == "standard-observation.v1":
            operation = "excel_import"
        else:
            raise ValueError("Data Import Canonical 的写入策略已淘汰")
        return _ImportLineageContext(cast(UUID, row.id), artifact, operation)

    @staticmethod
    def _content_with_lineage(
        session: Session,
        content: CanonicalContentV1,
        *,
        selected: CanonicalReplayArtifactRecord,
        lineage: _ImportLineageContext | None,
        lineage_by_platform: dict[str, tuple[UUID, UUID]],
    ) -> CanonicalContentV1:
        if selected.source_kind == "tikhub_search_attempt_v1":
            return content
        if lineage is None:
            raise ValueError("Import Replay 缺少 lineage context")
        identifiers = lineage_by_platform.get(content.platform)
        if identifiers is None:
            if selected.source_kind == "excel_import_v2":
                identifiers = ensure_single_import_lineage(
                    session=session,
                    batch_id=lineage.batch_id,
                    platform=content.platform,
                    input_artifact=lineage.raw_artifact,
                    profile=content.source.source_type or "unknown",
                )
            else:
                identifiers = ensure_campaign_import_lineage(
                    session=session,
                    batch_id=lineage.batch_id,
                    platform=content.platform,
                    canonical_artifact=lineage.raw_artifact,
                    operation=lineage.operation,
                )
            lineage_by_platform[content.platform] = identifiers
        request_id, attempt_id = identifiers
        source = content.source.model_copy(
            update={
                "provider_name": "imports",
                "operation": lineage.operation,
                "provider_request_id": str(request_id),
                "provider_attempt_id": str(attempt_id),
                "raw_artifact_id": lineage.raw_artifact.id,
            }
        )
        return content.model_copy(update={"source": source})

    @staticmethod
    def _write_evidence(
        *,
        vehicle_repository: PostgresVehicleCatalogRepository,
        brand_repository: PostgresBrandVehicleRepository,
        content_id: UUID,
        content_version: int,
        resolution: BrandVehicleResolution,
        run: CanonicalReplayRunRecord,
    ) -> None:
        for item in resolution.vehicle_evidence:
            if item.source != "alias_match":
                raise ValueError("Replay 自动 Vehicle Evidence 只接受 alias_match")
            vehicle_repository.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=content_version,
                    vehicle_model_id=item.entity_id,
                    source="alias_match",
                    matched_text=item.matched_text,
                    source_field=item.source_field,
                    catalog_version=resolution.catalog_version,
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )
        brand_repository.replace_automatic_brand_evidence(
            content_id=content_id,
            content_version=content_version,
            evidence=resolution.brand_evidence,
            catalog_version=resolution.catalog_version,
            catalog_snapshot=run.filter_snapshot.catalog,
        )


def _zero_counters() -> CanonicalReplayCounters:
    return CanonicalReplayCounters(0, 0, 0, 0, 0, 0)


def _progress(run: CanonicalReplayRunRecord) -> int:
    if run.checkpoint_artifact_ordinal >= run.artifact_count:
        return 100
    return min(99, int(run.checkpoint_artifact_ordinal * 100 / run.artifact_count))


def _result(run: CanonicalReplayRunRecord) -> dict[str, object]:
    return {
        "run_id": str(run.id),
        "artifact_count": run.artifact_count,
        "rows_seen": run.rows_seen,
        "rows_matched": run.rows_matched,
        "rows_filtered_out": run.rows_filtered_out,
        "duplicates_removed": run.duplicates_removed,
        "rows_ingested": run.rows_ingested,
        "existing_convergence": run.existing_convergence,
        "invalid_artifact_rows": 0,
    }


__all__ = ["PostgresCanonicalReplayJobExecutor"]
