"""JobWorker 稳定结构化生命周期事件回归。"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Literal
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobHandlerResult, JobRegistry, JobWorker
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from pydantic import BaseModel
from sqlalchemy import delete


class _PayloadV1(BaseModel):
    schema_version: Literal["audit.logging.v1"] = "audit.logging.v1"


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.execute(delete(job_attempt_events_table))
        connection.execute(delete(jobs_table))
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.execute(delete(job_attempt_events_table))
            connection.execute(delete(jobs_table))
        runtime.dispose()


def _enqueue(runtime: DatabaseRuntime, *, key: str) -> None:
    session = runtime.new_session()
    try:
        with session.begin():
            PostgresJobRepository(session).enqueue(
                job_type="audit.logging.v1",
                payload_version="audit.logging.v1",
                payload={"schema_version": "audit.logging.v1"},
                internal_idempotency_key=key,
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=30,
            )
    finally:
        session.close()


def _worker(runtime: DatabaseRuntime, outcome: str) -> JobWorker:
    registry = JobRegistry()

    def handler(payload: BaseModel, context) -> JobHandlerResult:
        assert isinstance(payload, _PayloadV1)
        if outcome == "succeeded":
            return JobHandlerResult.succeeded({"ok": True})
        if outcome == "retry":
            return JobHandlerResult.retry("temporary_provider_error")
        if outcome == "failed":
            return JobHandlerResult.failed("permanent_error")
        if outcome == "cancelled":
            session = runtime.new_session()
            try:
                with session.begin():
                    PostgresJobRepository(session).request_cancel(context.fence.job_id)
            finally:
                session.close()
            return JobHandlerResult.cancelled()
        raise AssertionError(outcome)

    registry.register(
        job_type="audit.logging.v1",
        payload_version="audit.logging.v1",
        payload_model=_PayloadV1,
        handler=handler,
        retry_on_timeout=True,
    )
    return JobWorker(
        session_factory=runtime.new_session,
        registry=registry,
        worker_id="audit-worker",
        lease_seconds=10,
        retry_delay_seconds=0,
    )


@pytest.mark.parametrize(
    ("outcome", "terminal_event"),
    [
        ("succeeded", "job.completed"),
        ("retry", "job.retry_scheduled"),
        ("failed", "job.failed"),
        ("cancelled", "job.cancelled"),
    ],
)
def test_job_worker_emits_stable_lifecycle_events(
    database_runtime: DatabaseRuntime,
    caplog: pytest.LogCaptureFixture,
    outcome: str,
    terminal_event: str,
) -> None:
    _enqueue(database_runtime, key=f"job-log-{outcome}-{uuid4()}")
    worker = _worker(database_runtime, outcome)

    with caplog.at_level(logging.INFO, logger="aima_ugc.operations.jobs.worker"):
        assert worker.run_once() is True

    records = [record for record in caplog.records if hasattr(record, "event")]
    events = [record.event for record in records]
    assert events == ["job.started", terminal_event]
    assert records[0].job_type == "audit.logging.v1"
    assert records[0].worker_id == "audit-worker"
    assert records[0].attempt == 1
    assert records[-1].job_id == records[0].job_id
    assert "lease_token" not in records[0].__dict__
    assert "payload" not in records[0].__dict__
