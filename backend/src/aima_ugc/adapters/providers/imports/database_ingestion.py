"""Excel/File Import 的正式 PostgreSQL 摄取编排。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import inspect

from aima_ugc.adapters.persistence.postgres.content import PostgresContentRepository
from aima_ugc.adapters.persistence.postgres.manual_ingestion import (
    PostgresProcessingImportBatchRepository,
)
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactService

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True, slots=True)
class FileImportIngestionSummary:
    batch_id: UUID
    input_artifact_id: UUID
    rows_seen: int
    rows_ingested: int
    rows_rejected: int
    provider_request_count: int


def require_stage8a_schema(runtime: DatabaseRuntime) -> None:
    """只检查当前代码需要的 Schema；绝不自动运行 Migration。"""
    if not runtime.ping():
        raise RuntimeError("PostgreSQL 不可用")
    inspector = inspect(runtime.engine)
    if not inspector.has_table("processing_import_batches"):
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：缺少 processing_import_batches；请显式执行 Migration"
        )
    provider_columns = {item["name"]: item for item in inspector.get_columns("provider_requests")}
    import_column = provider_columns.get("import_batch_id")
    scope_column = provider_columns.get("scope_id")
    if import_column is None or scope_column is None or not scope_column.get("nullable", False):
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：provider_requests 来源父级尚未升级；请显式执行 Migration"
        )


def ingest_canonical_file_to_postgres(
    *,
    input_path: Path,
    canonical_path: Path,
    runtime: DatabaseRuntime,
    artifact_service: ArtifactService,
    rows_seen: int,
    rows_rejected: int,
    job_id: UUID | None = None,
) -> FileImportIngestionSummary:
    """保存原始 Excel 来源，并把合法 Canonical 统一交给正式 Content Ingestion。"""
    require_stage8a_schema(runtime)
    source_path = Path(input_path)
    canonical_file = Path(canonical_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not canonical_file.is_file():
        raise FileNotFoundError(canonical_file)

    artifact = artifact_service.store_bytes(
        kind="file-import.raw",
        content_type=_XLSX_CONTENT_TYPE,
        retention_class="raw",
        data=source_path.read_bytes(),
    )
    if artifact.sha256 is None:
        raise RuntimeError("Input Artifact 未完成 SHA-256 确认")

    batch_id = uuid4()
    session = runtime.new_session()
    try:
        with session.begin():
            PostgresProcessingImportBatchRepository(session).create(
                batch_id=batch_id,
                input_artifact_id=artifact.id,
                job_id=job_id,
            )
    finally:
        session.close()
    artifact_service.link(artifact.id)

    rows_ingested = 0
    request_count = 0
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                provider_repository = PostgresProviderRepository(session)
                content_service = ContentIngestionService(PostgresContentRepository(session))
                lineage_by_platform: dict[str, tuple[UUID, UUID]] = {}
                with canonical_file.open("r", encoding="utf-8") as handle:
                    for line_number, raw_line in enumerate(handle, start=1):
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            content = CanonicalContentV1.model_validate_json(line)
                        except Exception as exc:
                            raise ValueError(
                                f"Canonical JSONL 第 {line_number} 行无法解析"
                            ) from exc
                        lineage = lineage_by_platform.get(content.platform)
                        if lineage is None:
                            request = ProviderRequestV1.create_for_import(
                                request_id=uuid4(),
                                import_batch_id=batch_id,
                                provider="imports",
                                platform=content.platform,
                                operation="excel_import",
                                request_params={
                                    "input_artifact_sha256": artifact.sha256,
                                    "profile": content.source.source_type or "unknown",
                                },
                                pagination_input={},
                            )
                            request_record = provider_repository.create_or_get_request(request)
                            reserved = provider_repository.create_or_get_non_billable_attempt(
                                provider_request_id=request_record.id,
                                attempt_id=uuid4(),
                            )
                            dispatching = provider_repository.mark_dispatching(reserved.id)
                            if dispatching.dispatch_started_at is None:
                                raise RuntimeError("File Import Attempt 未进入 dispatching")
                            completed_at = datetime.now(UTC)
                            terminal = ProviderAttemptV1(
                                attempt_id=dispatching.id,
                                provider_request_id=request_record.id,
                                attempt_no=dispatching.attempt_no,
                                dispatch_status="completed",
                                dispatch_started_at=dispatching.dispatch_started_at,
                                completed_at=completed_at,
                                raw_artifact_id=artifact.id,
                                billing=ProviderBillingV1(status="not_billable"),
                                created_at=dispatching.created_at,
                            )
                            provider_repository.finalize_dispatch(
                                attempt=terminal,
                                raw_artifact_id=artifact.id,
                            )
                            lineage = (request_record.id, dispatching.id)
                            lineage_by_platform[content.platform] = lineage
                            request_count += 1

                        request_id, attempt_id = lineage
                        source = content.source.model_copy(
                            update={
                                "provider_name": "imports",
                                "operation": "excel_import",
                                "provider_request_id": str(request_id),
                                "provider_attempt_id": str(attempt_id),
                                "raw_artifact_id": artifact.id,
                            }
                        )
                        content_service.ingest_content(content.model_copy(update={"source": source}))
                        rows_ingested += 1

                PostgresProcessingImportBatchRepository(session).mark_succeeded(
                    batch_id,
                    rows_seen=rows_seen,
                    rows_ingested=rows_ingested,
                    rows_rejected=rows_rejected,
                )
        finally:
            session.close()
    except Exception as exc:
        failed = runtime.new_session()
        try:
            with failed.begin():
                PostgresProcessingImportBatchRepository(failed).mark_failed(
                    batch_id,
                    rows_seen=rows_seen,
                    rows_ingested=0,
                    rows_rejected=rows_rejected,
                    error_summary=f"{type(exc).__name__}: {str(exc)[:1800]}",
                )
        finally:
            failed.close()
        raise

    return FileImportIngestionSummary(
        batch_id=batch_id,
        input_artifact_id=artifact.id,
        rows_seen=rows_seen,
        rows_ingested=rows_ingested,
        rows_rejected=rows_rejected,
        provider_request_count=request_count,
    )


__all__ = [
    "FileImportIngestionSummary",
    "ingest_canonical_file_to_postgres",
    "require_stage8a_schema",
]
