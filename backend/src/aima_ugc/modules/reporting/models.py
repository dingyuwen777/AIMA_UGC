"""Durable 数据导出的领域模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DataExportRecord:
    id: UUID
    job_id: UUID
    artifact_id: UUID | None
    request_snapshot: dict[str, object]
    stats: dict[str, object] | None
    created_at: datetime
    completed_at: datetime | None


__all__ = ["DataExportRecord"]
