"""Collection Run/Scope 稳定结构化生命周期事件回归。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aima_ugc.modules.collection.collection_run_executor import (
    CollectionRunExecutor,
    CollectionScopeExecutionResult,
)
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
        assert fence.job_id == self.execution.run.job_id
        return self.execution

    def start_run(self, run_id: UUID, *, fence: JobExecutionFence) -> CollectionRunRecord:
        assert run_id == self.execution.run.id
        return self.execution.run

    def start_scope(self, scope_id: UUID, *, fence: JobExecutionFence) -> CollectionScopeRecord:
        return next(scope for scope in self.execution.scopes if scope.id == scope_id)

    def checkpoint_scope(self, *args, **kwargs) -> CollectionScopeRecord:
        raise AssertionError("successful fixture must not checkpoint")

    def finish_scope(
        self,
        scope_id: UUID,
        *,
        fence: JobExecutionFence,
        status: str,
        stop_reason: str | None,
        pagination_state: dict[str, object],
        progress: int | None = None,
        stats: dict[str, object],
    ) -> CollectionScopeRecord:
        return next(scope for scope in self.execution.scopes if scope.id == scope_id)

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
        assert run_id == self.execution.run.id
        return self.execution.run


class _ScopeExecutor:
    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: _Context,
    ) -> CollectionScopeExecutionResult:
        return CollectionScopeExecutionResult(
            status="succeeded",
            stop_reason="provider_exhausted",
            pagination_state={"page": 1},
            stats={
                "requested_count": 1,
                "succeeded_count": 1,
                "failed_count": 0,
                "content_count": 2,
                "comment_count": 3,
            },
            requested_count=1,
            succeeded_count=1,
            failed_count=0,
            content_count=2,
            comment_count=3,
        )


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
                status="queued",
                pagination_state={},
                progress=0,
                stop_reason=None,
                stats={},
                started_at=None,
                finished_at=None,
            ),
        ),
    )


def test_collection_executor_emits_stable_run_and_scope_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    execution = _execution()
    context = _Context(execution.run.job_id)

    with caplog.at_level(logging.INFO, logger="aima_ugc.modules.collection.collection_run_executor"):
        result = CollectionRunExecutor(
            gateway=_Gateway(execution),
            scope_executor=_ScopeExecutor(),
        ).execute(fence=context.fence, context=context)

    assert result.outcome == "succeeded"
    records = [record for record in caplog.records if hasattr(record, "event")]
    assert [record.event for record in records] == [
        "collection.run.started",
        "collection.scope.completed",
        "collection.run.completed",
    ]
    assert records[0].run_id == str(execution.run.id)
    assert records[0].job_id == str(execution.run.job_id)
    assert records[1].scope_id == str(execution.scopes[0].id)
    assert records[1].platform == "xhs"
    assert records[1].status == "succeeded"
    assert records[2].status == "succeeded"
    assert records[2].content_count == 2
    assert records[2].comment_count == 3
