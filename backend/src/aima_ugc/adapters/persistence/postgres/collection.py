"""PostgreSQL Collection Run/Scope Repository。"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionRunRecord,
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionScopeDefinition,
    CollectionScopeRecord,
)
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table


class PostgresCollectionRepository:
    """Run/Scope 表的唯一 Collection 写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_queued_run(
        self,
        *,
        job_id: UUID,
        trigger_type: CollectionRunTrigger,
        config_snapshot: dict[str, object],
        scopes: tuple[CollectionScopeDefinition, ...],
    ) -> CollectionExecution:
        """在当前事务创建一个 queued Run 及其 queued Scopes。"""
        run_id = uuid4()
        run_row = (
            self._session.execute(
                insert(collection_runs_table)
                .values(
                    id=run_id,
                    job_id=job_id,
                    trigger_type=trigger_type,
                    config_snapshot=config_snapshot,
                    status="queued",
                    created_at=func.clock_timestamp(),
                )
                .returning(*collection_runs_table.c)
            )
            .mappings()
            .one()
        )

        scope_records: tuple[CollectionScopeRecord, ...] = ()
        if scopes:
            scope_rows = self._session.execute(
                insert(collection_scopes_table)
                .values(
                    [
                        {
                            "id": uuid4(),
                            "run_id": run_id,
                            "platform": scope.platform,
                            "source_type": scope.source_type,
                            "source_value": scope.source_value,
                            "operation_group": scope.operation_group,
                            "status": "queued",
                        }
                        for scope in scopes
                    ]
                )
                .returning(*collection_scopes_table.c)
            ).mappings()
            scope_records = tuple(_row_to_scope(row) for row in scope_rows)

        return CollectionExecution(run=_row_to_run(run_row), scopes=scope_records)

    def get_run_by_job_id(self, job_id: UUID) -> CollectionRunRecord | None:
        row = (
            self._session.execute(
                select(collection_runs_table).where(collection_runs_table.c.job_id == job_id)
            )
            .mappings()
            .one_or_none()
        )
        return _row_to_run(row) if row is not None else None

    def list_scopes(self, run_id: UUID) -> list[CollectionScopeRecord]:
        rows = self._session.execute(
            select(collection_scopes_table)
            .where(collection_scopes_table.c.run_id == run_id)
            .order_by(
                collection_scopes_table.c.platform,
                collection_scopes_table.c.source_type,
                collection_scopes_table.c.source_value,
                collection_scopes_table.c.operation_group,
            )
        ).mappings()
        return [_row_to_scope(row) for row in rows]


def _row_to_run(row: RowMapping) -> CollectionRunRecord:
    return CollectionRunRecord(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        trigger_type=cast(CollectionRunTrigger, row["trigger_type"]),
        config_snapshot=cast(dict[str, object], row["config_snapshot"]),
        status=cast(CollectionRunStatus, row["status"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        requested_count=cast(int, row["requested_count"]),
        succeeded_count=cast(int, row["succeeded_count"]),
        failed_count=cast(int, row["failed_count"]),
        content_count=cast(int, row["content_count"]),
        comment_count=cast(int, row["comment_count"]),
        error_summary=cast(str | None, row["error_summary"]),
        created_at=row["created_at"],
    )


def _row_to_scope(row: RowMapping) -> CollectionScopeRecord:
    return CollectionScopeRecord(
        id=cast(UUID, row["id"]),
        run_id=cast(UUID, row["run_id"]),
        platform=cast(str, row["platform"]),
        source_type=cast(str, row["source_type"]),
        source_value=cast(str, row["source_value"]),
        operation_group=cast(str, row["operation_group"]),
        status=cast(str, row["status"]),
        pagination_state=cast(dict[str, object], row["pagination_state"]),
        progress=cast(int, row["progress"]),
        stop_reason=cast(str | None, row["stop_reason"]),
        stats=cast(dict[str, object], row["stats"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
