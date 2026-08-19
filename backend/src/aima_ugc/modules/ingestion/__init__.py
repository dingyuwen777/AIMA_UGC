"""Stage 8A Processing / Import Batch 领域边界。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProcessingImportBatchRecord:
    """一次手工数据处理的最小业务父事实。"""

    id: UUID
    input_artifact_id: UUID
    job_id: UUID | None
    status: str
    stats: dict[str, object]
    error_summary: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


__all__ = ["ProcessingImportBatchRecord"]
