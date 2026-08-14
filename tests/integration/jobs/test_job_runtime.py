from __future__ import annotations

from collections.abc import Iterator
from hashlib import sha256
from typing import Literal

import pytest
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import (
    JobHandlerResult,
    JobIdempotencyConflict,
    JobReaper,
    JobRegistry,
    JobWorker,
    LeaseLostError,
)
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from pydantic import BaseModel
from sqlalchemy import delete, text


class EchoPayloadV1(BaseModel):
    schema_version: Literal["echo.v1"] = "echo.v1"
    value: str


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


def _enqueue(
    repository: PostgresJobRepository,
    *,
    key: str,
    value: str = "payload",
    job_type: str = "test.echo.v1",
    max_attempts: int = 2,
    timeout_seconds: int = 30,
):
    return repository.enqueue(
        job_type=job_type,
        payload_version="echo.v1",
        payload={"schema_version": "echo.v1", "value": value},
        internal_idempotency_key=key,
        request_id=None,
        priority=10,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
    )


def _expire_lease(session, job_id) -> None:
    session.execute(
        text(
            "UPDATE jobs "
            "SET lease_expires_at = clock_timestamp() - interval '1 second' "
            "WHERE id = :job_id"
        ),
        {"job_id": job_id},
    )


def _expire_deadline(session, job_id) -> None:
    session.execute(
        text(
            "UPDATE jobs "
            "SET lease_expires_at = clock_timestamp() - interval '2 seconds', "
            "attempt_deadline_at = clock_timestamp() - interval '1 second' "
            "WHERE id = :job_id"
        ),
        {"job_id": job_id},
    )


def test_enqueue_is_idempotent_and_rejects_conflicting_payload(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    repository = PostgresJobRepository(session)
    try:
        with session.begin():
            first = _enqueue(repository, key="same-key")
            second = _enqueue(repository, key="same-key")
        assert second.id == first.id

        with session.begin():
            with pytest.raises(JobIdempotencyConflict):
                _enqueue(repository, key="same-key", value="different")
    finally:
        session.close()


def test_claim_is_atomic_takeover_keeps_attempt_and_stale_token_is_fenced(
    database_runtime: DatabaseRuntime,
) -> None:
    session_a = database_runtime.new_session()
    session_b = database_runtime.new_session()
    repository_a = PostgresJobRepository(session_a)
    repository_b = PostgresJobRepository(session_b)
    try:
        with session_a.begin():
            job = _enqueue(repository_a, key="claim")

        transaction_a = session_a.begin()
        first_claim = repository_a.claim_next(
            supported_job_types=("test.echo.v1",),
            worker_id="worker-a",
            lease_seconds=10,
        )
        assert first_claim is not None
        assert first_claim.id == job.id
        assert first_claim.attempt == 1
        assert first_claim.lease_takeover_count == 0
        assert first_claim.lease_token is not None

        with session_b.begin():
            assert (
                repository_b.claim_next(
                    supported_job_types=("test.echo.v1",),
                    worker_id="worker-b",
                    lease_seconds=10,
                )
                is None
            )
        transaction_a.commit()

        original_token = first_claim.lease_token
        original_deadline = first_claim.attempt_deadline_at
        with session_b.begin():
            _expire_lease(session_b, job.id)
        with session_b.begin():
            takeover = repository_b.claim_next(
                supported_job_types=("test.echo.v1",),
                worker_id="worker-b",
                lease_seconds=10,
            )
        assert takeover is not None
        assert takeover.attempt == 1
        assert takeover.lease_takeover_count == 1
        assert takeover.attempt_deadline_at == original_deadline
        assert takeover.lease_token != original_token

        with session_a.begin():
            with pytest.raises(LeaseLostError):
                repository_a.heartbeat(
                    job_id=job.id,
                    lease_token=original_token,
                    lease_seconds=10,
                    progress=20,
                )

        with session_b.begin():
            events = repository_b.list_events(job.id)
        assert [event.event_type for event in events] == ["claimed", "lease_taken_over"]
        assert events[0].lease_token_fingerprint == sha256(original_token.encode()).hexdigest()
        assert events[0].lease_token_fingerprint != original_token
    finally:
        session_a.close()
        session_b.close()


def test_heartbeat_is_capped_by_deadline_and_cancel_blocks_renewal(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    repository = PostgresJobRepository(session)
    try:
        with session.begin():
            job = _enqueue(repository, key="heartbeat", timeout_seconds=30)
        with session.begin():
            claimed = repository.claim_next(
                supported_job_types=("test.echo.v1",),
                worker_id="worker-a",
                lease_seconds=2,
            )
        assert claimed is not None
        assert claimed.lease_token is not None
        deadline = claimed.attempt_deadline_at

        with session.begin():
            renewed = repository.heartbeat(
                job_id=job.id,
                lease_token=claimed.lease_token,
                lease_seconds=120,
                progress=40,
            )
        assert renewed.progress == 40
        assert renewed.attempt_deadline_at == deadline
        assert renewed.lease_expires_at is not None
        assert deadline is not None
        assert renewed.lease_expires_at <= deadline

        with session.begin():
            repository.request_cancel(job.id)
        with session.begin():
            with pytest.raises(LeaseLostError):
                repository.heartbeat(
                    job_id=job.id,
                    lease_token=claimed.lease_token,
                    lease_seconds=5,
                    progress=50,
                )
    finally:
        session.close()


def test_reaper_retries_timeout_then_fails_at_max_attempts(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    repository = PostgresJobRepository(session)
    try:
        with session.begin():
            job = _enqueue(repository, key="timeout", max_attempts=2)
        with session.begin():
            first = repository.claim_next(
                supported_job_types=("test.echo.v1",),
                worker_id="worker-a",
                lease_seconds=10,
            )
        assert first is not None

        with session.begin():
            _expire_deadline(session, job.id)
        with session.begin():
            retried = repository.reap_next(
                timeout_retry_job_types=("test.echo.v1",),
                retry_delay_seconds=0,
            )
        assert retried is not None
        assert retried.status == "queued"
        assert retried.attempt == 1
        assert retried.attempt_started_at is None
        assert retried.attempt_deadline_at is None

        with session.begin():
            second = repository.claim_next(
                supported_job_types=("test.echo.v1",),
                worker_id="worker-b",
                lease_seconds=10,
            )
        assert second is not None
        assert second.attempt == 2

        with session.begin():
            _expire_deadline(session, job.id)
        with session.begin():
            failed = repository.reap_next(
                timeout_retry_job_types=("test.echo.v1",),
                retry_delay_seconds=0,
            )
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_code == "attempt_timeout"
        assert failed.finished_at is not None

        with session.begin():
            events = repository.list_events(job.id)
        assert [event.event_type for event in events] == [
            "claimed",
            "retry_scheduled",
            "claimed",
            "timed_out",
        ]
    finally:
        session.close()


def test_queued_and_running_cancellation_converge(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    repository = PostgresJobRepository(session)
    try:
        with session.begin():
            queued = _enqueue(repository, key="cancel-queued")
            cancelled_queued = repository.request_cancel(queued.id)
        assert cancelled_queued.status == "cancelled"
        assert cancelled_queued.finished_at is not None

        with session.begin():
            running = _enqueue(repository, key="cancel-running")
        with session.begin():
            claimed = repository.claim_next(
                supported_job_types=("test.echo.v1",),
                worker_id="worker-a",
                lease_seconds=10,
            )
        assert claimed is not None
        with session.begin():
            requested = repository.request_cancel(running.id)
        assert requested.status == "running"
        assert requested.cancel_requested_at is not None

        with session.begin():
            _expire_lease(session, running.id)
        with session.begin():
            cancelled_running = repository.reap_next(
                timeout_retry_job_types=("test.echo.v1",),
                retry_delay_seconds=0,
            )
        assert cancelled_running is not None
        assert cancelled_running.id == running.id
        assert cancelled_running.status == "cancelled"
    finally:
        session.close()


def test_fake_handler_runs_through_production_worker(
    database_runtime: DatabaseRuntime,
) -> None:
    registry = JobRegistry()

    def echo_handler(payload: BaseModel, context) -> JobHandlerResult:
        assert isinstance(payload, EchoPayloadV1)
        context.heartbeat(progress=60)
        assert context.cancel_requested() is False
        return JobHandlerResult.succeeded({"echo": payload.value})

    registry.register(
        job_type="test.echo.v1",
        payload_version="echo.v1",
        payload_model=EchoPayloadV1,
        handler=echo_handler,
        retry_on_timeout=True,
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            job = _enqueue(PostgresJobRepository(session), key="worker")
    finally:
        session.close()

    worker = JobWorker(
        session_factory=database_runtime.new_session,
        registry=registry,
        worker_id="fake-worker",
        lease_seconds=10,
        retry_delay_seconds=0,
    )
    assert worker.run_once() is True

    session = database_runtime.new_session()
    try:
        with session.begin():
            completed = PostgresJobRepository(session).get(job.id)
        assert completed is not None
        assert completed.status == "succeeded"
        assert completed.progress == 100
        assert completed.result == {"echo": "payload"}
    finally:
        session.close()


def test_worker_skips_unknown_job_type_and_reaper_uses_registry_policy(
    database_runtime: DatabaseRuntime,
) -> None:
    registry = JobRegistry()

    def echo_handler(payload: BaseModel, context) -> JobHandlerResult:
        return JobHandlerResult.succeeded({})

    registry.register(
        job_type="test.echo.v1",
        payload_version="echo.v1",
        payload_model=EchoPayloadV1,
        handler=echo_handler,
        retry_on_timeout=True,
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            unknown = _enqueue(
                PostgresJobRepository(session),
                key="unknown",
                job_type="test.unknown.v1",
            )
    finally:
        session.close()

    worker = JobWorker(
        session_factory=database_runtime.new_session,
        registry=registry,
        worker_id="worker",
        lease_seconds=10,
        retry_delay_seconds=0,
    )
    assert worker.run_once() is False

    session = database_runtime.new_session()
    try:
        with session.begin():
            still_queued = PostgresJobRepository(session).get(unknown.id)
        assert still_queued is not None
        assert still_queued.status == "queued"
    finally:
        session.close()

    reaper = JobReaper(
        session_factory=database_runtime.new_session,
        registry=registry,
        retry_delay_seconds=0,
    )
    assert reaper.run_once() is False
