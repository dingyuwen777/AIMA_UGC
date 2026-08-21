"""Stage 8E Import Batch 与 Collection Run 的统一只读 UNION Query。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import BigInteger, Text, and_, case, func, literal, or_, select, union_all
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.collection_run_job import COLLECTION_RUN_JOB_TYPE
from aima_ugc.modules.collection.runtime_cursor import RuntimeRecordType
from aima_ugc.modules.collection.runtime_query import (
    CollectionRuntimeReadQuery,
    CollectionRuntimeReadRecord,
    CollectionRuntimeSummary,
)
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.jobs.tables import jobs_table

_IMPORT_ACTIVE_STAGES = (
    "queued",
    "reading",
    "mapping",
    "filtering",
    "deduplicating",
    "ingesting",
)


class PostgresCollectionRuntimeQueryRepository:
    """跨 Owner 只读聚合，不写 Batch、Run 或 Job。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_runs(
        self,
        query: CollectionRuntimeReadQuery,
    ) -> tuple[CollectionRuntimeReadRecord, ...]:
        statement = self._union().subquery("collection_runtime_union")
        selected = select(statement)
        if query.record_types:
            selected = selected.where(statement.c.record_type.in_(query.record_types))
        if query.status is not None:
            selected = selected.where(statement.c.public_status == query.status)
        if query.stage is not None:
            selected = selected.where(statement.c.public_stage == query.stage)
        if query.created_from is not None:
            selected = selected.where(statement.c.created_at >= query.created_from)
        if query.created_to is not None:
            selected = selected.where(statement.c.created_at <= query.created_to)
        if query.search is not None:
            pattern = f"%{_escape_like(query.search)}%"
            selected = selected.where(
                or_(
                    sql_cast(statement.c.record_id, Text) == query.search,
                    sql_cast(statement.c.job_id, Text) == query.search,
                    statement.c.search_text.ilike(pattern, escape="\\"),
                )
            )
        if query.position is not None:
            selected = selected.where(
                or_(
                    statement.c.created_at < query.position.created_at,
                    and_(
                        statement.c.created_at == query.position.created_at,
                        statement.c.record_id < query.position.record_id,
                    ),
                    and_(
                        statement.c.created_at == query.position.created_at,
                        statement.c.record_id == query.position.record_id,
                        statement.c.record_type < query.position.record_type,
                    ),
                )
            )
        rows = self._session.execute(
            selected.order_by(
                statement.c.created_at.desc(),
                statement.c.record_id.desc(),
                statement.c.record_type.desc(),
            ).limit(query.limit)
        ).mappings()
        return tuple(_row_to_record(row) for row in rows)

    def summary(
        self,
        *,
        today_start_utc: datetime,
        tomorrow_start_utc: datetime,
    ) -> CollectionRuntimeSummary:
        import_batch = processing_import_batches_table
        collection_run = collection_runs_table
        job = jobs_table

        import_rows_text = import_batch.c.stats["rows_ingested"].astext
        safe_import_rows = case(
            (
                import_rows_text.op("~")(r"^[0-9]{1,18}$"),
                sql_cast(import_rows_text, BigInteger),
            ),
            else_=0,
        )
        import_finished_today = and_(
            job.c.status == "succeeded",
            job.c.finished_at >= today_start_utc,
            job.c.finished_at < tomorrow_start_utc,
        )
        import_summary = (
            self._session.execute(
                select(
                    func.count()
                    .filter(job.c.status.in_(("queued", "running")))
                    .label("processing"),
                    func.count().filter(import_finished_today).label("completed"),
                    func.coalesce(
                        func.sum(safe_import_rows).filter(import_finished_today), 0
                    ).label("contents"),
                )
                .select_from(import_batch.join(job, import_batch.c.job_id == job.c.id))
                .where(job.c.job_type == IMPORT_JOB_TYPE)
            )
            .mappings()
            .one()
        )

        collection_finished_today = and_(
            job.c.status == "succeeded",
            job.c.finished_at >= today_start_utc,
            job.c.finished_at < tomorrow_start_utc,
        )
        collection_summary = (
            self._session.execute(
                select(
                    func.count()
                    .filter(job.c.status.in_(("queued", "running")))
                    .label("processing"),
                    func.count().filter(collection_finished_today).label("completed"),
                    func.coalesce(
                        func.sum(collection_run.c.content_count).filter(collection_finished_today),
                        0,
                    ).label("contents"),
                )
                .select_from(collection_run.join(job, collection_run.c.job_id == job.c.id))
                .where(job.c.job_type == COLLECTION_RUN_JOB_TYPE)
            )
            .mappings()
            .one()
        )
        return CollectionRuntimeSummary(
            processing_count=cast(int, import_summary["processing"])
            + cast(int, collection_summary["processing"]),
            completed_today_count=cast(int, import_summary["completed"])
            + cast(int, collection_summary["completed"]),
            contents_ingested_today=cast(int, import_summary["contents"])
            + cast(int, collection_summary["contents"]),
        )

    @staticmethod
    def _union() -> Any:
        batch = processing_import_batches_table
        run = collection_runs_table
        job = jobs_table
        scope_filtered = _scope_filtered_subquery()

        import_stage_value = batch.c.stats["stage"].astext
        import_stage = case(
            (job.c.status == "succeeded", "succeeded"),
            (job.c.status == "failed", "failed"),
            (job.c.status == "cancelled", "cancelled"),
            (import_stage_value.in_(_IMPORT_ACTIVE_STAGES), import_stage_value),
            else_="queued",
        )
        import_select = (
            select(
                batch.c.id.label("record_id"),
                job.c.id.label("job_id"),
                literal("excel_import").label("record_type"),
                job.c.status.label("public_status"),
                job.c.progress,
                import_stage.label("public_stage"),
                batch.c.id.label("import_batch_id"),
                literal(None).cast(run.c.id.type).label("collection_run_id"),
                batch.c.stats["source_filename"].astext.label("source_filename"),
                batch.c.stats.label("import_stats"),
                literal(0).label("requested_count"),
                literal(0).label("succeeded_count"),
                literal(0).label("failed_count"),
                literal(0).label("content_count"),
                literal(0).label("comment_count"),
                literal(0).label("filtered_count"),
                literal(None).cast(JSONB).label("config_snapshot"),
                batch.c.error_summary,
                job.c.error_code,
                batch.c.created_at,
                func.coalesce(batch.c.started_at, job.c.started_at).label("started_at"),
                func.coalesce(batch.c.finished_at, job.c.finished_at).label("finished_at"),
                func.concat_ws(
                    " ",
                    batch.c.stats["source_filename"].astext,
                    sql_cast(batch.c.id, Text),
                    sql_cast(job.c.id, Text),
                ).label("search_text"),
            )
            .select_from(batch.join(job, batch.c.job_id == job.c.id))
            .where(job.c.job_type == IMPORT_JOB_TYPE)
        )

        collection_status = case(
            (job.c.status == "failed", "failed"),
            (job.c.status == "cancelled", "cancelled"),
            else_=run.c.status,
        )
        running_stage = case(
            (run.c.config_snapshot["mode"].astext == "batch_supplement", "content_enrichment"),
            else_="content_discovery",
        )
        collection_stage = case(
            (collection_status == "running", running_stage),
            else_=collection_status,
        )
        collection_select = (
            select(
                run.c.id.label("record_id"),
                job.c.id.label("job_id"),
                case(
                    (
                        run.c.config_snapshot["mode"].astext == "batch_supplement",
                        "tikhub_batch_supplement",
                    ),
                    else_="tikhub_discovery",
                ).label("record_type"),
                collection_status.label("public_status"),
                job.c.progress,
                collection_stage.label("public_stage"),
                run.c.import_batch_id,
                run.c.id.label("collection_run_id"),
                batch.c.stats["source_filename"].astext.label("source_filename"),
                literal(None).cast(JSONB).label("import_stats"),
                run.c.requested_count,
                run.c.succeeded_count,
                run.c.failed_count,
                run.c.content_count,
                run.c.comment_count,
                func.coalesce(scope_filtered.c.filtered_count, 0).label("filtered_count"),
                run.c.config_snapshot,
                run.c.error_summary,
                job.c.error_code,
                run.c.created_at,
                func.coalesce(run.c.started_at, job.c.started_at).label("started_at"),
                func.coalesce(run.c.finished_at, job.c.finished_at).label("finished_at"),
                func.concat_ws(
                    " ",
                    batch.c.stats["source_filename"].astext,
                    run.c.config_snapshot["keywords"].astext,
                    sql_cast(run.c.id, Text),
                    sql_cast(job.c.id, Text),
                ).label("search_text"),
            )
            .select_from(
                run.join(job, run.c.job_id == job.c.id)
                .outerjoin(batch, batch.c.id == run.c.import_batch_id)
                .outerjoin(scope_filtered, scope_filtered.c.run_id == run.c.id)
            )
            .where(job.c.job_type == COLLECTION_RUN_JOB_TYPE)
        )
        return union_all(import_select, collection_select)


def _scope_filtered_subquery() -> Any:
    filtered_text = collection_scopes_table.c.stats["filtered_content_count"].astext
    safe_filtered = case(
        (
            filtered_text.op("~")(r"^[0-9]{1,18}$"),
            sql_cast(filtered_text, BigInteger),
        ),
        else_=0,
    )
    return (
        select(
            collection_scopes_table.c.run_id,
            func.coalesce(func.sum(safe_filtered), 0).label("filtered_count"),
        )
        .group_by(collection_scopes_table.c.run_id)
        .subquery("collection_scope_filtered")
    )


def _row_to_record(row: RowMapping) -> CollectionRuntimeReadRecord:
    return CollectionRuntimeReadRecord(
        record_id=cast(UUID, row["record_id"]),
        job_id=cast(UUID, row["job_id"]),
        record_type=cast(RuntimeRecordType, row["record_type"]),
        status=cast(str, row["public_status"]),
        progress=cast(int, row["progress"]),
        stage=cast(str, row["public_stage"]),
        import_batch_id=cast(UUID | None, row["import_batch_id"]),
        collection_run_id=cast(UUID | None, row["collection_run_id"]),
        source_filename=cast(str | None, row["source_filename"]),
        import_stats=cast(dict[str, object] | None, row["import_stats"]),
        requested_count=cast(int, row["requested_count"]),
        succeeded_count=cast(int, row["succeeded_count"]),
        failed_count=cast(int, row["failed_count"]),
        content_count=cast(int, row["content_count"]),
        comment_count=cast(int, row["comment_count"]),
        filtered_count=cast(int, row["filtered_count"]),
        config_snapshot=cast(dict[str, object] | None, row["config_snapshot"]),
        error_summary=cast(str | None, row["error_summary"]),
        error_code=cast(str | None, row["error_code"]),
        created_at=cast(datetime, row["created_at"]),
        started_at=cast(datetime | None, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = ["PostgresCollectionRuntimeQueryRepository"]
