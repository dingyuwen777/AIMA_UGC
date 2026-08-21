"""Stage 8E Import/Collection 统一运行只读模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .runtime_cursor import CollectionRuntimeCursorPosition, RuntimeRecordType


@dataclass(frozen=True, slots=True)
class CollectionRuntimeReadQuery:
    search: str | None
    record_types: tuple[RuntimeRecordType, ...]
    status: str | None
    stage: str | None
    created_from: datetime | None
    created_to: datetime | None
    position: CollectionRuntimeCursorPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class CollectionRuntimeReadRecord:
    record_id: UUID
    job_id: UUID
    record_type: RuntimeRecordType
    status: str
    progress: int
    stage: str
    import_batch_id: UUID | None
    collection_run_id: UUID | None
    source_filename: str | None
    import_stats: dict[str, object] | None
    requested_count: int
    succeeded_count: int
    failed_count: int
    content_count: int
    comment_count: int
    filtered_count: int
    config_snapshot: dict[str, object] | None
    error_summary: str | None
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class CollectionRuntimeSummary:
    processing_count: int
    completed_today_count: int
    contents_ingested_today: int


__all__ = [
    "CollectionRuntimeReadQuery",
    "CollectionRuntimeReadRecord",
    "CollectionRuntimeSummary",
]
