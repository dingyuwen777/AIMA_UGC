"""Stage 8E Import Batch 与 Collection Run 的统一只读 UNION Query。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import BigInteger, Integer, Text, and_, case, func, literal, or_, select, union_all
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
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
)
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
_CAMPAIGN_ACTIVE_STATUSES = (
    "uploading",
    "discovering",
    "snapshotting",
    "ready",
    "queued",
    "running",
    "cancelling",
)
_CAMPAIGN_COMPLETED_STATUSES = ("succeeded", "partial_failed")


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
        campaign = historical_import_campaigns_table
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

        campaign_rows_ingested = _campaign_rows_ingested(campaign.c.stats)
        campaign_finished_today = and_(
            campaign.c.status.in_(_CAMPAIGN_COMPLETED_STATUSES),
            campaign.c.finished_at >= today_start_utc,
            campaign.c.finished_at < tomorrow_start_utc,
        )
        campaign_summary = (
            self._session.execute(
                select(
                    func.count()
                    .filter(campaign.c.status.in_(_CAMPAIGN_ACTIVE_STATUSES))
                    .label("processing"),
                    func.count().filter(campaign_finished_today).label("completed"),
                    func.coalesce(
                        func.sum(campaign_rows_ingested).filter(campaign_finished_today),
                        0,
                    ).label("contents"),
                ).select_from(campaign)
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
            + cast(int, campaign_summary["processing"])
            + cast(int, collection_summary["processing"]),
            completed_today_count=cast(int, import_summary["completed"])
            + cast(int, campaign_summary["completed"])
            + cast(int, collection_summary["completed"]),
            contents_ingested_today=cast(int, import_summary["contents"])
            + cast(int, campaign_summary["contents"])
            + cast(int, collection_summary["contents"]),
        )

    @staticmethod
    def _union() -> Any:
        batch = processing_import_batches_table
        campaign = historical_import_campaigns_table
        run = collection_runs_table
        job = jobs_table
        scope_filtered = _scope_filtered_subquery()
        campaign_source_totals, campaign_chunk_totals = _campaign_progress_subqueries()

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
                literal(None).cast(campaign.c.id.type).label("data_import_campaign_id"),
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

        campaign_preflight_percent = case(
            (campaign.c.status == "ready", 100),
            (
                campaign.c.discovered_file_count > 0,
                func.least(
                    100,
                    sql_cast(
                        func.coalesce(campaign_source_totals.c.progress_points, 0)
                        * 100
                        / campaign.c.discovered_file_count,
                        Integer,
                    ),
                ),
            ),
            else_=0,
        )
        campaign_migration_percent = case(
            (
                campaign.c.total_rows > 0,
                func.least(
                    100,
                    sql_cast(
                        func.coalesce(campaign_chunk_totals.c.completed_row_count, 0)
                        * 100
                        / campaign.c.total_rows,
                        Integer,
                    ),
                ),
            ),
            (campaign.c.status.in_(_CAMPAIGN_COMPLETED_STATUSES), 100),
            else_=0,
        )
        campaign_progress = case(
            (
                campaign.c.status.in_(("uploading", "discovering", "snapshotting", "ready")),
                campaign_preflight_percent,
            ),
            else_=campaign_migration_percent,
        )
        campaign_status = case(
            (campaign.c.status.in_(("uploading", "discovering", "snapshotting")), "running"),
            (campaign.c.status.in_(("ready", "queued")), "queued"),
            (campaign.c.status.in_(("running", "cancelling")), "running"),
            (campaign.c.status == "partial_failed", "partial_success"),
            else_=campaign.c.status,
        )
        campaign_import_stats = func.jsonb_build_object(
            "rows_seen",
            campaign.c.total_rows,
            "rows_matched",
            _campaign_rows_matched(campaign.c.stats),
            "rows_filtered_out",
            _safe_json_count(campaign.c.stats, "filtered"),
            "duplicates_removed",
            _safe_json_count(campaign.c.stats, "duplicate"),
            "rows_ingested",
            _campaign_rows_ingested(campaign.c.stats),
            "rows_rejected",
            _campaign_rows_rejected(campaign.c.stats),
        )
        campaign_select = select(
            campaign.c.id.label("record_id"),
            literal(None).cast(job.c.id.type).label("job_id"),
            literal("data_import_campaign").label("record_type"),
            campaign_status.label("public_status"),
            campaign_progress.label("progress"),
            campaign.c.status.label("public_stage"),
            literal(None).cast(batch.c.id.type).label("import_batch_id"),
            campaign.c.id.label("data_import_campaign_id"),
            literal(None).cast(run.c.id.type).label("collection_run_id"),
            campaign.c.root_relative_path.label("source_filename"),
            campaign_import_stats.label("import_stats"),
            literal(0).label("requested_count"),
            literal(0).label("succeeded_count"),
            literal(0).label("failed_count"),
            literal(0).label("content_count"),
            literal(0).label("comment_count"),
            literal(0).label("filtered_count"),
            literal(None).cast(JSONB).label("config_snapshot"),
            campaign.c.error_summary,
            literal(None).cast(Text).label("error_code"),
            campaign.c.created_at,
            campaign.c.started_at,
            campaign.c.finished_at,
            func.concat_ws(
                " ",
                campaign.c.root_relative_path,
                campaign.c.source_kind,
                campaign.c.ingestion_policy,
                sql_cast(campaign.c.id, Text),
            ).label("search_text"),
        ).select_from(
            campaign.outerjoin(
                campaign_source_totals,
                campaign_source_totals.c.campaign_id == campaign.c.id,
            ).outerjoin(
                campaign_chunk_totals,
                campaign_chunk_totals.c.campaign_id == campaign.c.id,
            )
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
                run.c.data_import_campaign_id,
                run.c.id.label("collection_run_id"),
                func.coalesce(
                    batch.c.stats["source_filename"].astext,
                    campaign.c.root_relative_path,
                ).label("source_filename"),
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
                    campaign.c.root_relative_path,
                    run.c.config_snapshot["keywords"].astext,
                    sql_cast(run.c.id, Text),
                    sql_cast(job.c.id, Text),
                ).label("search_text"),
            )
            .select_from(
                run.join(job, run.c.job_id == job.c.id)
                .outerjoin(batch, batch.c.id == run.c.import_batch_id)
                .outerjoin(campaign, campaign.c.id == run.c.data_import_campaign_id)
                .outerjoin(scope_filtered, scope_filtered.c.run_id == run.c.id)
            )
            .where(job.c.job_type == COLLECTION_RUN_JOB_TYPE)
        )
        return union_all(import_select, campaign_select, collection_select)


def _safe_json_count(column: Any, key: str) -> Any:
    value = column[key].astext
    return case(
        (value.op("~")(r"^[0-9]{1,18}$"), sql_cast(value, BigInteger)),
        else_=0,
    )


def _campaign_rows_matched(stats: Any) -> Any:
    return sum(
        (
            _safe_json_count(stats, key)
            for key in ("created", "filled", "updated", "unchanged", "conflict")
        ),
        literal(0),
    )


def _campaign_rows_ingested(stats: Any) -> Any:
    return sum(
        (_safe_json_count(stats, key) for key in ("created", "filled", "updated")),
        literal(0),
    )


def _campaign_rows_rejected(stats: Any) -> Any:
    return sum(
        (_safe_json_count(stats, key) for key in ("conflict", "invalid", "failed")),
        literal(0),
    )


def _campaign_progress_subqueries() -> tuple[Any, Any]:
    item = historical_import_campaign_items_table
    source_progress = case(
        (item.c.status == "discovered", 0),
        (item.c.status == "snapshotting", func.coalesce(jobs_table.c.progress, 0)),
        else_=100,
    )
    source_totals = (
        select(
            item.c.campaign_id.label("campaign_id"),
            func.coalesce(func.sum(source_progress), 0).label("progress_points"),
        )
        .select_from(item.outerjoin(jobs_table, jobs_table.c.id == item.c.job_id))
        .where(item.c.item_kind == "source_file")
        .group_by(item.c.campaign_id)
        .subquery("runtime_campaign_source_progress")
    )
    chunk_totals = (
        select(
            item.c.campaign_id.label("campaign_id"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            item.c.status.in_(("succeeded", "failed", "cancelled")),
                            item.c.row_count,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("completed_row_count"),
        )
        .where(item.c.item_kind == "chunk")
        .group_by(item.c.campaign_id)
        .subquery("runtime_campaign_chunk_progress")
    )
    return source_totals, chunk_totals


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
        job_id=cast(UUID | None, row["job_id"]),
        record_type=cast(RuntimeRecordType, row["record_type"]),
        status=cast(str, row["public_status"]),
        progress=cast(int, row["progress"]),
        stage=cast(str, row["public_stage"]),
        import_batch_id=cast(UUID | None, row["import_batch_id"]),
        data_import_campaign_id=cast(UUID | None, row["data_import_campaign_id"]),
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
