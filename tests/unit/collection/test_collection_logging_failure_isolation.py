"""Collection 生命周期日志不得破坏既有 Scope 故障隔离。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionRunRecord,
    CollectionScopeRecord,
)
from aima_ugc.platform.jobs import JobExecutionFence

_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class _Context:
    def __init__(self, job_id: UUID) -> None:
        self._fence = JobExecutionFence(job_id=job_id, lease_token="audit-lease")

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


class _Gateway:
    def __init__(self, execution: CollectionExecution) -> None:
        self.execution = execution

    def load(self, fence: JobExecutionFence) -> CollectionExecution | None:
        return self.execution

    def start_run(self, run_id: UUID, *, fence: JobExecutionFence) -> CollectionRunRecord:
        return self.execution.run

    def start_scope(self, scope_id: UUID, *, fence: JobExecutionFence) -> CollectionScopeRecord:
        return self.execution.scopes[0]

    def checkpoint_scope(self, *args, **kwargs) -> CollectionScopeRecord:
        raise AssertionError("unexpected checkpoint")

    def finish_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
        status: str,
        stop_reason: str | None,
        pagination_state: dict[str, object],
        stats: dict[str, object],
    ) -> CollectionScopeRecord:
        assert status == "failed"
        return self.execution.scopes[0]

    def finish_run(
        self,
        run_id: UUID,
        *,
        fence: JobExecutionFence,
        status: str,
        requested_count: int,
        succeeded_count: int,
        failed_count: int,
        content_count: int,
        comment_count: int,
        error_summary: str | None,
    ) -> CollectionRunRecord:
        assert status == "failed"
        return self.execution.run


class _ScopeExecutor:
    def execute(self, **kwargs):
        raise RuntimeError("scope failed before producing a terminal result")


def _execution() -> CollectionExecution:
    run_id = uuid4()
    job_id = uuid4()
    return CollectionExecution(
        run=CollectionRunRecord(
            id=run_id,
            job_id=job_id,
            manual_plan_id=None,
            occurrence_id=None,
            trigger_type="api",
            config_snapshot={},
            status="queued",
            started_at=None,
            finished_at=None,
            requested_count=0,
            succeeded_count=0,
            failed_count=0,
            content_count=0,
            comment_count=0,
            error_summary=None,
            created_at=_NOW,
        ),
        scopes=(
            CollectionScopeRecord(
                id=uuid4(),
                run_id=run_id,
                platform="xhs",
                source_type="keyword_search",
                source_value="爱玛",
                operation_group="content_discovery",
                status="running",
                pagination_state={"page": 1},
                progress=20,
                stop_reason=None,
                stats={"requested_count": "corrupt"},
                started_at=_NOW,
                finished_at=None,
            ),
        ),
    )


def test_logging_does_not_break_scope_exception_isolation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    execution = _execution()
    context = _Context(execution.run.job_id)

    with caplog.at_level(
        logging.INFO, logger="aima_ugc.modules.collection.collection_run_executor"
    ):
        result = CollectionRunExecutor(
            gateway=_Gateway(execution),
            scope_executor=_ScopeExecutor(),
        ).execute(fence=context.fence, context=context)

    assert result.outcome == "failed"
    scope_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "collection.scope.completed"
    )
    assert scope_record.status == "failed"
    assert scope_record.requested_count == 0
