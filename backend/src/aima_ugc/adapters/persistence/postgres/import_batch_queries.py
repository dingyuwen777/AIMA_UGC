"""Stage 8C Import Batch PostgreSQL 只读 Query Adapter。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import BigInteger, case, func, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.query import (
    ImportBatchReadQuery,
    ImportBatchReadRecord,
    ImportBatchSummary,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.jobs.tables import jobs_table

_ACTIVE_STAGES = ("queued", "reading", "mapping", "filtering", "deduplicating", "ingesting")


class PostgresImportBatchQueryRepository:
    """一次 Join 查询返回列表所需 Batch/Job 事实，不写任何业务表。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_batches(self, query: ImportBatchReadQuery) -> tuple[ImportBatchReadRecord, ...]:
        batch = processing_import_batches_table
        job = jobs_table
        stage_value = batch.c.stats["stage"].astext
        public_stage = case(
            (job.c.status == "succeeded", "succeeded"),
            (job.c.status == "failed", "failed"),
            (job.c.status == "cancelled", "cancelled"),
            (stage_value.in_(_ACTIVE_STAGES), stage_value),
            else_="queued",
        )
        statement = (
            select(
                batch.c.id.label("batch_id"),
                batch.c.input_artifact_id,
                batch.c.stats["source_filename"].astext.label("source_filename"),
                job.c.status.label("public_status"),
                public_stage.label("public_stage"),
                batch.c.stats,
                batch.c.error_summary,
                batch.c.created_at,
                batch.c.started_at,
                batch.c.finished_at,
                job.c.id.label("job_id"),
                job.c.job_type,
                job.c.attempt,
                job.c.max_attempts,
                job.c.progress,
                job.c.error_code.label("job_error_code"),
                job.c.result.label("job_result"),
                job.c.created_at.label("job_created_at"),
                job.c.started_at.label("job_started_at"),
                job.c.finished_at.label("job_finished_at"),
            )
            .select_from(batch.join(job, batch.c.job_id == job.c.id))
            .where(job.c.job_type == IMPORT_JOB_TYPE)
        )
        if query.identifier is not None:
            statement = statement.where(
                or_(batch.c.id == query.identifier, job.c.id == query.identifier)
            )
        if query.status is not None:
            statement = statement.where(job.c.status == query.status)
        if query.stage is not None:
            statement = statement.where(public_stage == query.stage)
        if query.created_from is not None:
            statement = statement.where(batch.c.created_at >= query.created_from)
        if query.created_to is not None:
            statement = statement.where(batch.c.created_at <= query.created_to)
        if query.position is not None:
            statement = statement.where(
                or_(
                    batch.c.created_at < query.position.created_at,
                    (
                        (batch.c.created_at == query.position.created_at)
                        & (batch.c.id < query.position.batch_id)
                    ),
                )
            )
        rows = self._session.execute(
            statement.order_by(batch.c.created_at.desc(), batch.c.id.desc()).limit(query.limit)
        ).mappings()
        return tuple(_row_to_record(row) for row in rows)

    def summary(
        self,
        *,
        today_start_utc: datetime,
        tomorrow_start_utc: datetime,
    ) -> ImportBatchSummary:
        batch = processing_import_batches_table
        job = jobs_table
        ingested_text = batch.c.stats["rows_ingested"].astext
        safe_rows_ingested = case(
            (ingested_text.op("~")(r"^[0-9]{1,18}$"), sql_cast(ingested_text, BigInteger)),
            else_=0,
        )
        today_succeeded = (
            (job.c.status == "succeeded")
            & (job.c.finished_at >= today_start_utc)
            & (job.c.finished_at < tomorrow_start_utc)
        )
        row = (
            self._session.execute(
                select(
                    func.count()
                    .filter(job.c.status.in_(("queued", "running")))
                    .label("processing"),
                    func.count().filter(today_succeeded).label("completed_today"),
                    func.coalesce(func.sum(safe_rows_ingested).filter(today_succeeded), 0).label(
                        "rows_ingested_today"
                    ),
                )
                .select_from(batch.join(job, batch.c.job_id == job.c.id))
                .where(job.c.job_type == IMPORT_JOB_TYPE)
            )
            .mappings()
            .one()
        )
        return ImportBatchSummary(
            processing_count=cast(int, row["processing"]),
            completed_today_count=cast(int, row["completed_today"]),
            rows_ingested_today=cast(int, row["rows_ingested_today"]),
        )


def _row_to_record(row: RowMapping) -> ImportBatchReadRecord:
    return ImportBatchReadRecord(
        batch_id=cast(UUID, row["batch_id"]),
        input_artifact_id=cast(UUID, row["input_artifact_id"]),
        source_filename=cast(str | None, row["source_filename"]),
        status=cast(str, row["public_status"]),
        stage=cast(str, row["public_stage"]),
        stats=cast(dict[str, object], row["stats"]),
        error_summary=cast(str | None, row["error_summary"]),
        created_at=cast(datetime, row["created_at"]),
        started_at=cast(datetime | None, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
        job_id=cast(UUID, row["job_id"]),
        job_type=cast(str, row["job_type"]),
        attempt=cast(int, row["attempt"]),
        max_attempts=cast(int, row["max_attempts"]),
        progress=cast(int, row["progress"]),
        job_error_code=cast(str | None, row["job_error_code"]),
        job_result=row["job_result"],
        job_created_at=cast(datetime, row["job_created_at"]),
        job_started_at=cast(datetime | None, row["job_started_at"]),
        job_finished_at=cast(datetime | None, row["job_finished_at"]),
    )


__all__ = ["PostgresImportBatchQueryRepository"]
