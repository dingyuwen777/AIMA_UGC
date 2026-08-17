"""PostgreSQL Collection Run/Scope Repository。"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
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

_RUN_TERMINAL_STATUSES = frozenset({"partial_success", "succeeded", "failed", "cancelled"})
_SCOPE_TERMINAL_STATUSES = frozenset({"partial_success", "succeeded", "failed", "cancelled"})


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
        manual_plan_id: UUID | None = None,
        occurrence_id: UUID | None = None,
    ) -> CollectionExecution:
        """在当前事务创建一个 queued Run 及其 queued Scopes。"""
        run_id = uuid4()
        run_row = (
            self._session.execute(
                insert(collection_runs_table)
                .values(
                    id=run_id,
                    job_id=job_id,
                    manual_plan_id=manual_plan_id,
                    occurrence_id=occurrence_id,
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

    def start_run(self, run_id: UUID) -> CollectionRunRecord:
        """把 queued Run 推进到 running；同一 running Run 可安全重入。"""
        current = self._lock_run(run_id)
        if current["status"] == "running":
            return _row_to_run(current)
        if current["status"] in _RUN_TERMINAL_STATUSES:
            raise ValueError("collection run is already terminal")
        if current["status"] != "queued":
            raise ValueError(f"unsupported collection run status: {current['status']}")

        row = (
            self._session.execute(
                update(collection_runs_table)
                .where(collection_runs_table.c.id == run_id)
                .values(status="running", started_at=func.clock_timestamp())
                .returning(*collection_runs_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_run(row)

    def start_scope(self, scope_id: UUID) -> CollectionScopeRecord:
        """把 queued Scope 推进到 running；同一 running Scope 可安全重入。"""
        current = self._lock_scope(scope_id)
        if current["status"] == "running":
            return _row_to_scope(current)
        if current["status"] in _SCOPE_TERMINAL_STATUSES:
            raise ValueError("collection scope is already terminal")
        if current["status"] != "queued":
            raise ValueError(f"unsupported collection scope status: {current['status']}")

        row = (
            self._session.execute(
                update(collection_scopes_table)
                .where(collection_scopes_table.c.id == scope_id)
                .values(status="running", started_at=func.clock_timestamp())
                .returning(*collection_scopes_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_scope(row)

    def checkpoint_scope(
        self,
        scope_id: UUID,
        *,
        pagination_state: dict[str, object],
        progress: int,
        stats: dict[str, object],
    ) -> CollectionScopeRecord:
        """保存 running Scope 的分页、进度和统计；进度只能单调前进。"""
        current = self._lock_scope(scope_id)
        if current["status"] in _SCOPE_TERMINAL_STATUSES:
            raise ValueError("collection scope is already terminal")
        if current["status"] != "running":
            raise ValueError("collection scope must be running before checkpoint")
        current_progress = cast(int, current["progress"])
        if progress < current_progress:
            raise ValueError("collection scope progress cannot move backwards")
        if progress < 0 or progress > 99:
            raise ValueError("collection scope progress must be between 0 and 99 while running")

        row = (
            self._session.execute(
                update(collection_scopes_table)
                .where(collection_scopes_table.c.id == scope_id)
                .values(
                    pagination_state=dict(pagination_state),
                    progress=progress,
                    stats=dict(stats),
                )
                .returning(*collection_scopes_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_scope(row)

    def finish_scope(
        self,
        scope_id: UUID,
        *,
        status: str,
        stop_reason: str | None,
        pagination_state: dict[str, object],
        stats: dict[str, object],
    ) -> CollectionScopeRecord:
        """把 running Scope 推进到显式终态并固定最终状态。"""
        if status not in _SCOPE_TERMINAL_STATUSES:
            raise ValueError(f"unsupported collection scope terminal status: {status}")
        current = self._lock_scope(scope_id)
        if current["status"] in _SCOPE_TERMINAL_STATUSES:
            raise ValueError("collection scope is already terminal")
        if current["status"] != "running":
            raise ValueError("collection scope must be running before finish")

        row = (
            self._session.execute(
                update(collection_scopes_table)
                .where(collection_scopes_table.c.id == scope_id)
                .values(
                    status=status,
                    progress=100,
                    stop_reason=stop_reason,
                    pagination_state=dict(pagination_state),
                    stats=dict(stats),
                    finished_at=func.clock_timestamp(),
                )
                .returning(*collection_scopes_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_scope(row)

    def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        requested_count: int,
        succeeded_count: int,
        failed_count: int,
        content_count: int,
        comment_count: int,
        error_summary: str | None,
    ) -> CollectionRunRecord:
        """把 running Run 推进到显式终态并保存最终聚合统计。"""
        if status not in _RUN_TERMINAL_STATUSES:
            raise ValueError(f"unsupported collection run terminal status: {status}")
        counts = (requested_count, succeeded_count, failed_count, content_count, comment_count)
        if any(value < 0 for value in counts):
            raise ValueError("collection run counts must be nonnegative")

        current = self._lock_run(run_id)
        if current["status"] in _RUN_TERMINAL_STATUSES:
            raise ValueError("collection run is already terminal")
        if current["status"] != "running":
            raise ValueError("collection run must be running before finish")

        row = (
            self._session.execute(
                update(collection_runs_table)
                .where(collection_runs_table.c.id == run_id)
                .values(
                    status=status,
                    requested_count=requested_count,
                    succeeded_count=succeeded_count,
                    failed_count=failed_count,
                    content_count=content_count,
                    comment_count=comment_count,
                    error_summary=error_summary,
                    finished_at=func.clock_timestamp(),
                )
                .returning(*collection_runs_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_run(row)

    def _lock_run(self, run_id: UUID) -> RowMapping:
        row = (
            self._session.execute(
                select(collection_runs_table)
                .where(collection_runs_table.c.id == run_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError(f"collection run not found: {run_id}")
        return row

    def _lock_scope(self, scope_id: UUID) -> RowMapping:
        row = (
            self._session.execute(
                select(collection_scopes_table)
                .where(collection_scopes_table.c.id == scope_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError(f"collection scope not found: {scope_id}")
        return row


def _row_to_run(row: RowMapping) -> CollectionRunRecord:
    return CollectionRunRecord(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        manual_plan_id=cast(UUID | None, row["manual_plan_id"]),
        occurrence_id=cast(UUID | None, row["occurrence_id"]),
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
