"""Processing / Import Batch PostgreSQL Owner Repository。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.ingestion import ProcessingImportBatchRecord
from aima_ugc.modules.ingestion.tables import processing_import_batches_table


class PostgresProcessingImportBatchRepository:
    """只负责 Processing / Import Batch 父事实，不写 Content/Comment。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        batch_id: UUID,
        input_artifact_id: UUID,
        job_id: UUID | None = None,
    ) -> ProcessingImportBatchRecord:
        row = (
            self._session.execute(
                insert(processing_import_batches_table)
                .values(
                    id=batch_id,
                    input_artifact_id=input_artifact_id,
                    job_id=job_id,
                    status="processing",
                    stats={},
                    created_at=func.clock_timestamp(),
                    started_at=func.clock_timestamp(),
                )
                .returning(*processing_import_batches_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_batch(row)

    def mark_succeeded(
        self,
        batch_id: UUID,
        *,
        rows_seen: int,
        rows_ingested: int,
        rows_rejected: int,
    ) -> ProcessingImportBatchRecord:
        return self._finish(
            batch_id,
            status="succeeded",
            stats={
                "rows_seen": rows_seen,
                "rows_ingested": rows_ingested,
                "rows_rejected": rows_rejected,
            },
            error_summary=None,
        )

    def mark_failed(
        self,
        batch_id: UUID,
        *,
        rows_seen: int,
        rows_ingested: int,
        rows_rejected: int,
        error_summary: str,
    ) -> ProcessingImportBatchRecord:
        if not error_summary or len(error_summary) > 2000:
            raise ValueError("error_summary 必须为 1..2000 字符的安全摘要")
        return self._finish(
            batch_id,
            status="failed",
            stats={
                "rows_seen": rows_seen,
                "rows_ingested": rows_ingested,
                "rows_rejected": rows_rejected,
            },
            error_summary=error_summary,
        )

    def get(self, batch_id: UUID) -> ProcessingImportBatchRecord | None:
        row = (
            self._session.execute(
                select(processing_import_batches_table).where(
                    processing_import_batches_table.c.id == batch_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return _row_to_batch(row) if row is not None else None

    def _finish(
        self,
        batch_id: UUID,
        *,
        status: str,
        stats: dict[str, int],
        error_summary: str | None,
    ) -> ProcessingImportBatchRecord:
        if any(value < 0 for value in stats.values()):
            raise ValueError("Import Batch 计数不能为负数")
        row = (
            self._session.execute(
                update(processing_import_batches_table)
                .where(
                    processing_import_batches_table.c.id == batch_id,
                    processing_import_batches_table.c.status == "processing",
                )
                .values(
                    status=status,
                    stats=stats,
                    error_summary=error_summary,
                    finished_at=func.clock_timestamp(),
                )
                .returning(*processing_import_batches_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RuntimeError(f"Processing / Import Batch 不存在或已结束: {batch_id}")
        return _row_to_batch(row)


def _row_to_batch(row: RowMapping) -> ProcessingImportBatchRecord:
    return ProcessingImportBatchRecord(
        id=cast(UUID, row["id"]),
        input_artifact_id=cast(UUID, row["input_artifact_id"]),
        job_id=cast(UUID | None, row["job_id"]),
        status=cast(str, row["status"]),
        stats=cast(dict[str, object], row["stats"]),
        error_summary=cast(str | None, row["error_summary"]),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


__all__ = ["PostgresProcessingImportBatchRepository"]
