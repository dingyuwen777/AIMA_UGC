"""Stage 8C Import Batch 只读查询模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aima_ugc.modules.ingestion.import_batch_cursor import ImportBatchCursorPosition


@dataclass(frozen=True, slots=True)
class ImportBatchReadQuery:
    identifier: UUID | None
    status: str | None
    stage: str | None
    created_from: datetime | None
    created_to: datetime | None
    position: ImportBatchCursorPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class ImportBatchReadRecord:
    batch_id: UUID
    input_artifact_id: UUID
    source_filename: str | None
    status: str
    stage: str
    stats: dict[str, object]
    error_summary: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    job_id: UUID
    job_type: str
    attempt: int
    max_attempts: int
    progress: int
    job_error_code: str | None
    job_result: object | None
    job_created_at: datetime
    job_started_at: datetime | None
    job_finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ImportBatchSummary:
    processing_count: int
    completed_today_count: int
    rows_ingested_today: int


__all__ = ["ImportBatchReadQuery", "ImportBatchReadRecord", "ImportBatchSummary"]
