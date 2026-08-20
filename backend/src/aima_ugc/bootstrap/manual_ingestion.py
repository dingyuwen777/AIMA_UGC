"""Stage 8A File Import 的正式 PostgreSQL 组合入口。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.manual_ingestion import (
    PostgresProcessingImportBatchRepository,
)
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.provider import ProviderAttemptV1, ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactRecord, ArtifactService

from .runtime import PlatformRuntime, create_platform_runtime

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_REQUIRED_BATCH_COLUMNS = {
    "id",
    "input_artifact_id",
    "job_id",
    "status",
    "stats",
    "error_summary",
    "created_at",
    "started_at",
    "finished_at",
}


@dataclass(frozen=True, slots=True)
class FileImportDatabaseSummary:
    """一次 File Import 数据库阶段的可展示摘要。"""

    batch_id: UUID
    input_artifact_id: UUID
    rows_seen: int
    rows_ingested: int
    rows_rejected: int
    provider_request_count: int


@dataclass(frozen=True, slots=True)
class MultiFileImportDatabaseSummary:
    """一次多 Excel 数据库阶段的按源 Batch 汇总。"""

    batches: tuple[FileImportDatabaseSummary, ...]
    rows_seen: int
    rows_ingested: int
    rows_rejected: int
    provider_request_count: int


@dataclass(frozen=True, slots=True)
class FileImportWriteSummary:
    """Stage 8A/8B 共用数据库写入内核的事务内结果。"""

    rows_ingested: int
    provider_request_count: int


def require_stage8a_schema(database: DatabaseRuntime) -> None:
    """确认数据库可连接且已经显式迁移到 Stage 8A；本函数绝不运行 Migration。"""
    if not database.ping():
        raise RuntimeError("PostgreSQL 不可用")

    inspector = inspect(database.engine)
    if not inspector.has_table("processing_import_batches"):
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：缺少 processing_import_batches；"
            "请先显式执行 Migration"
        )
    batch_columns = {item["name"] for item in inspector.get_columns("processing_import_batches")}
    if not _REQUIRED_BATCH_COLUMNS.issubset(batch_columns):
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：processing_import_batches 字段不完整；"
            "请先显式执行 Migration"
        )

    provider_columns = {item["name"]: item for item in inspector.get_columns("provider_requests")}
    scope_column = provider_columns.get("scope_id")
    import_column = provider_columns.get("import_batch_id")
    if (
        scope_column is None
        or import_column is None
        or not bool(scope_column.get("nullable"))
        or not bool(import_column.get("nullable"))
    ):
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：provider_requests 来源父级尚未升级；"
            "请先显式执行 Migration"
        )

    unique_columns = {
        tuple(constraint.get("column_names") or ())
        for constraint in inspector.get_unique_constraints("provider_requests")
    }
    if ("import_batch_id", "request_fingerprint") not in unique_columns:
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：缺少 Import Batch Provider Request 幂等约束；"
            "请先显式执行 Migration"
        )
    source_parent_checks = [
        constraint
        for constraint in inspector.get_check_constraints("provider_requests")
        if str(constraint.get("name") or "").endswith("source_parent_exactly_one")
    ]
    if not source_parent_checks:
        raise RuntimeError(
            "PostgreSQL Schema 未满足 Stage 8A：缺少 Provider Request 单一来源父级约束；"
            "请先显式执行 Migration"
        )


def ingest_excel_run_to_postgres(
    *,
    input_path: Path,
    unified_content_path: Path,
    rows_seen: int,
    rows_rejected: int = 0,
    job_id: UUID | None = None,
) -> FileImportDatabaseSummary:
    """使用仓库正式配置连接既有 PostgreSQL，并执行一次 File Import 数据库阶段。"""
    runtime = create_platform_runtime("manual-ingestion")
    try:
        return _ingest_excel_run(
            input_path=Path(input_path),
            unified_content_path=Path(unified_content_path),
            rows_seen=rows_seen,
            rows_rejected=rows_rejected,
            job_id=job_id,
            runtime=runtime,
        )
    finally:
        runtime.close()


def ingest_excel_files_run_to_postgres(
    *,
    source_rows: Sequence[tuple[Path, int]],
    unified_content_path: Path,
    rows_rejected: int = 0,
) -> MultiFileImportDatabaseSummary:
    """把全局去重结果按原 Excel 来源写入独立 Artifact/Import Batch。"""

    sources = tuple((Path(path), rows_seen) for path, rows_seen in source_rows)
    if not sources:
        raise ValueError("多 Excel 数据库入库至少需要一个源文件")
    if rows_rejected != 0:
        raise ValueError("多 Excel fail-closed 转换不得携带被拒绝行进入数据库阶段")
    names: set[str] = set()
    for input_path, rows_seen in sources:
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        if isinstance(rows_seen, bool) or not isinstance(rows_seen, int) or rows_seen < 0:
            raise ValueError("File Import 行计数不能为负数")
        normalized = input_path.name.casefold()
        if normalized in names:
            raise ValueError(f"多 Excel 文件名重复，无法唯一分配数据库来源: {input_path.name}")
        names.add(normalized)

    unified_path = Path(unified_content_path)
    _require_known_excel_sources(unified_path, {path.name for path, _ in sources})
    runtime = create_platform_runtime("manual-ingestion")
    try:
        batches = tuple(
            _ingest_excel_run(
                input_path=input_path,
                unified_content_path=unified_path,
                rows_seen=rows_seen,
                rows_rejected=0,
                job_id=None,
                runtime=runtime,
                source_value_filter=input_path.name,
            )
            for input_path, rows_seen in sources
        )
    finally:
        runtime.close()
    return MultiFileImportDatabaseSummary(
        batches=batches,
        rows_seen=sum(item.rows_seen for item in batches),
        rows_ingested=sum(item.rows_ingested for item in batches),
        rows_rejected=sum(item.rows_rejected for item in batches),
        provider_request_count=sum(item.provider_request_count for item in batches),
    )


def _ingest_excel_run(
    *,
    input_path: Path,
    unified_content_path: Path,
    rows_seen: int,
    rows_rejected: int,
    job_id: UUID | None,
    runtime: PlatformRuntime,
    source_value_filter: str | None = None,
) -> FileImportDatabaseSummary:
    require_stage8a_schema(runtime.database)
    if rows_seen < 0 or rows_rejected < 0:
        raise ValueError("File Import 行计数不能为负数")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if not unified_content_path.is_file():
        raise FileNotFoundError(unified_content_path)

    artifacts = ArtifactService(
        metadata=PostgresArtifactMetadataGateway(runtime.database.new_session),
        store=runtime.artifact_store,
    )
    input_artifact = artifacts.store_bytes(
        kind="file-import.raw",
        content_type=_XLSX_CONTENT_TYPE,
        retention_class="raw",
        data=input_path.read_bytes(),
    )
    if input_artifact.sha256 is None:
        raise RuntimeError("File Import 输入 Artifact 未完成 SHA-256 确认")

    # 每次显式数据库执行都是一个独立 Batch；业务幂等由 Content 稳定身份与数据库唯一约束保证。
    batch_id = uuid4()
    session = runtime.database.new_session()
    try:
        with session.begin():
            PostgresProcessingImportBatchRepository(session).create(
                batch_id=batch_id,
                input_artifact_id=input_artifact.id,
                job_id=job_id,
            )
    finally:
        session.close()

    rows_ingested = 0
    request_count = 0
    try:
        # Batch 已经建立对输入 Artifact 的真实 FK 引用，此时才推进 Artifact stored → linked。
        # 从 Batch 创建后的所有失败都必须进入同一失败收敛路径，避免留下 processing 僵尸批次。
        artifacts.link(input_artifact.id)

        session = runtime.database.new_session()
        try:
            with session.begin():
                write_summary = ingest_unified_content_batch(
                    session=session,
                    batch_id=batch_id,
                    input_artifact=input_artifact,
                    unified_content_path=unified_content_path,
                    rows_seen=rows_seen,
                    rows_rejected=rows_rejected,
                    source_value_filter=source_value_filter,
                )
                rows_ingested = write_summary.rows_ingested
                request_count = write_summary.provider_request_count
        finally:
            session.close()
    except Exception as exc:
        failed = runtime.database.new_session()
        try:
            with failed.begin():
                batch = PostgresProcessingImportBatchRepository(failed).get(batch_id)
                if batch is not None and batch.status == "processing":
                    PostgresProcessingImportBatchRepository(failed).mark_failed(
                        batch_id,
                        rows_seen=rows_seen,
                        rows_ingested=0,
                        rows_rejected=rows_rejected,
                        error_summary=_safe_error_summary(exc),
                    )
        finally:
            failed.close()
        raise

    return FileImportDatabaseSummary(
        batch_id=batch_id,
        input_artifact_id=input_artifact.id,
        rows_seen=rows_seen,
        rows_ingested=rows_ingested,
        rows_rejected=rows_rejected,
        provider_request_count=request_count,
    )


def ingest_unified_content_batch(
    *,
    session: Session,
    batch_id: UUID,
    input_artifact: ArtifactRecord,
    unified_content_path: Path,
    rows_seen: int,
    rows_rejected: int,
    source_value_filter: str | None = None,
) -> FileImportWriteSummary:
    """在调用方事务中复用 Stage 8A 正式来源链与 Content Ingestion。"""

    if input_artifact.sha256 is None:
        raise RuntimeError("File Import 输入 Artifact 缺少 SHA-256")
    provider_repository = PostgresProviderRepository(session)
    provider_service = ProviderPersistenceService(provider_repository)
    content_service = ContentIngestionService(PostgresCompleteContentRepository(session))
    lineage_by_platform: dict[str, tuple[UUID, UUID]] = {}
    rows_ingested = 0
    request_count = 0

    with unified_content_path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                record = UnifiedContentRecordV1.model_validate_json(raw_line)
            except Exception as exc:
                raise ValueError(f"Unified Content JSONL 第 {line_number} 行无法解析") from exc
            content = record.content
            if (
                source_value_filter is not None
                and content.source.source_value != source_value_filter
            ):
                continue
            lineage = lineage_by_platform.get(content.platform)
            if lineage is None:
                request_id = uuid5(batch_id, f"provider-request:{content.platform}")
                attempt_id = uuid5(batch_id, f"provider-attempt:{content.platform}")
                request = ProviderRequestV1.create_for_import(
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
                terminal = ProviderAttemptV1(
                    attempt_id=dispatching.id,
                    provider_request_id=prepared.request.id,
                    attempt_no=dispatching.attempt_no,
                    dispatch_status="completed",
                    dispatch_started_at=dispatching.dispatch_started_at,
                    completed_at=datetime.now(UTC),
                    raw_artifact_id=input_artifact.id,
                    billing=ProviderBillingV1(status="not_billable"),
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
            content_service.ingest_content(content.model_copy(update={"source": source}))
            rows_ingested += 1

    PostgresProcessingImportBatchRepository(session).mark_succeeded(
        batch_id,
        rows_seen=rows_seen,
        rows_ingested=rows_ingested,
        rows_rejected=rows_rejected,
    )
    return FileImportWriteSummary(
        rows_ingested=rows_ingested,
        provider_request_count=request_count,
    )


def _safe_error_summary(error: Exception) -> str:
    message = str(error).strip().replace("\n", " ")
    return f"{type(error).__name__}: {message}"[:2000] if message else type(error).__name__


def _require_known_excel_sources(path: Path, expected_source_values: set[str]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                record = UnifiedContentRecordV1.model_validate_json(raw_line)
            except Exception as exc:
                raise ValueError(f"Unified Content JSONL 第 {line_number} 行无法解析") from exc
            source_value = record.content.source.source_value
            if source_value not in expected_source_values:
                raise ValueError(
                    f"Unified Content JSONL 第 {line_number} 行来源不属于本次 Excel 输入: "
                    f"{source_value}"
                )


__all__ = [
    "FileImportDatabaseSummary",
    "FileImportWriteSummary",
    "MultiFileImportDatabaseSummary",
    "ingest_excel_files_run_to_postgres",
    "ingest_excel_run_to_postgres",
    "ingest_unified_content_batch",
    "require_stage8a_schema",
]
