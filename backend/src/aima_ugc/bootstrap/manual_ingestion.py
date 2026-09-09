"""Stage 3 File Import 数据库覆盖层：统一 Brand/Vehicle Evidence 与 Content 同事务协调。"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4, uuid5

from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.modules.ingestion.brand_vehicle_filter import (
    BrandVehicleFilterSnapshot,
    resolve_canonical_brand_vehicle,
)
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence, normalize_vehicle_text
from aima_ugc.platform.storage import ArtifactRecord
from aima_ugc.platform.time import beijing_now

from . import _manual_ingestion_base as _base
from ._manual_ingestion_base import *  # noqa: F403


def ingest_unified_content_batch(
    *,
    session: Session,
    batch_id: UUID,
    input_artifact: ArtifactRecord,
    unified_content_path: Path,
    rows_seen: int,
    rows_rejected: int,
    source_value_filter: str | None = None,
    vehicle_catalog_version: int | None = None,
    vehicle_alias_bindings: tuple[tuple[UUID, str], ...] = (),
    brand_vehicle_filter_snapshot: BrandVehicleFilterSnapshot | None = None,
) -> _base.FileImportWriteSummary:
    """在一个调用方事务中写 Content，并按冻结 Snapshot 协调 Brand/Vehicle Evidence。"""

    if input_artifact.sha256 is None:
        raise RuntimeError("File Import 输入 Artifact 缺少 SHA-256")
    if brand_vehicle_filter_snapshot is not None and (
        vehicle_catalog_version is not None or vehicle_alias_bindings
    ):
        raise ValueError("Stage 3 Brand/Vehicle Filter 与 legacy Vehicle Evidence 参数不能混用")

    provider_repository = _base.PostgresProviderRepository(session)
    provider_service = _base.ProviderPersistenceService(provider_repository)
    content_service = _base.ContentIngestionService(_base.PostgresCompleteContentRepository(session))
    lineage_by_platform: dict[str, tuple[UUID, UUID]] = {}
    rows_ingested = 0
    request_count = 0
    vehicle_by_alias = {
        normalize_vehicle_text(alias): model_id for model_id, alias in vehicle_alias_bindings
    }
    vehicle_repository = PostgresVehicleCatalogRepository(session)
    brand_repository = PostgresBrandVehicleRepository(session)

    with unified_content_path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                record = UnifiedContentRecordV1.model_validate_json(raw_line)
            except Exception as exc:
                raise ValueError(f"Unified Content JSONL 第 {line_number} 行无法解析") from exc
            content = record.content
            if source_value_filter is not None and content.source.source_value != source_value_filter:
                continue
            lineage = lineage_by_platform.get(content.platform)
            if lineage is None:
                request_id = uuid5(batch_id, f"provider-request:{content.platform}")
                attempt_id = uuid5(batch_id, f"provider-attempt:{content.platform}")
                request = _base.ProviderRequestV1.create_for_import(
                    request_id=request_id,
                    import_batch_id=batch_id,
                    provider="imports",
                    platform=content.platform,
                    operation="excel_import",
                    request_params={
                        "input_artifact_sha256": input_artifact.sha256,
                        "profile": content.source.source_type or "unknown",
                    },
                    pagination_input={},
                )
                prepared = provider_service.prepare_non_billable_attempt(
                    request=request,
                    attempt_id=attempt_id,
                )
                dispatching = provider_repository.mark_dispatching(prepared.attempt.id)
                if dispatching.dispatch_started_at is None:
                    raise RuntimeError("File Import Attempt 未进入 dispatching")
                terminal = _base.ProviderAttemptV1(
                    attempt_id=dispatching.id,
                    provider_request_id=prepared.request.id,
                    attempt_no=dispatching.attempt_no,
                    dispatch_status="completed",
                    dispatch_started_at=dispatching.dispatch_started_at,
                    completed_at=beijing_now(),
                    raw_artifact_id=input_artifact.id,
                    billing=_base.ProviderBillingV1(status="not_billable"),
                    created_at=dispatching.created_at,
                )
                provider_repository.finalize_dispatch(
                    attempt=terminal,
                    raw_artifact_id=input_artifact.id,
                )
                lineage = (prepared.request.id, dispatching.id)
                lineage_by_platform[content.platform] = lineage
                request_count += 1

            request_id, attempt_id = lineage
            source = content.source.model_copy(
                update={
                    "provider_name": "imports",
                    "operation": "excel_import",
                    "provider_request_id": str(request_id),
                    "provider_attempt_id": str(attempt_id),
                    "raw_artifact_id": input_artifact.id,
                }
            )
            result = content_service.ingest_content(content.model_copy(update={"source": source}))
            if result.target_id is not None and brand_vehicle_filter_snapshot is not None:
                resolution = resolve_canonical_brand_vehicle(brand_vehicle_filter_snapshot, content)
                if not resolution.matched:
                    raise ValueError("过滤后 Content 与冻结 Brand/Vehicle Snapshot 发生解释漂移")
                for evidence in resolution.vehicle_evidence:
                    vehicle_repository.append_evidence(
                        ContentVehicleEvidence(
                            id=uuid4(),
                            content_id=result.target_id,
                            content_version=result.version_no,
                            vehicle_model_id=evidence.entity_id,
                            source="import",
                            matched_text=evidence.matched_text,
                            source_field=evidence.source_field,
                            catalog_version=brand_vehicle_filter_snapshot.catalog.catalog_version,
                            confidence=1.0,
                            is_manual_locked=False,
                            is_active=True,
                            created_at=beijing_now(),
                        )
                    )
                brand_repository.replace_automatic_brand_evidence(
                    content_id=result.target_id,
                    content_version=result.version_no,
                    evidence=resolution.brand_evidence,
                    catalog_version=brand_vehicle_filter_snapshot.catalog.catalog_version,
                )
            elif result.target_id is not None and vehicle_catalog_version is not None:
                for alias in record.matched_vehicle_aliases:
                    model_id = vehicle_by_alias.get(normalize_vehicle_text(alias))
                    if model_id is None:
                        continue
                    vehicle_repository.append_evidence(
                        ContentVehicleEvidence(
                            id=uuid4(),
                            content_id=result.target_id,
                            content_version=result.version_no,
                            vehicle_model_id=model_id,
                            source="import",
                            matched_text=alias,
                            source_field="title_text",
                            catalog_version=vehicle_catalog_version,
                            confidence=1.0,
                            is_manual_locked=False,
                            is_active=True,
                            created_at=beijing_now(),
                        )
                    )
            rows_ingested += 1

    _base.PostgresProcessingImportBatchRepository(session).mark_succeeded(
        batch_id,
        rows_seen=rows_seen,
        rows_ingested=rows_ingested,
        rows_rejected=rows_rejected,
    )
    return _base.FileImportWriteSummary(
        rows_ingested=rows_ingested,
        provider_request_count=request_count,
    )


__all__ = [
    *getattr(_base, "__all__", ()),
    "ingest_unified_content_batch",
]
