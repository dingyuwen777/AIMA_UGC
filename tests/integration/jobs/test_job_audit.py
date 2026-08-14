from __future__ import annotations

from collections.abc import Iterator

import pytest
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import LeaseLostError
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete, text


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


def _enqueue(repository: PostgresJobRepository, *, key: str):
    return repository.enqueue(
        job_type="test.audit.v1",
        payload_version="audit.v1",
        payload={"schema_version": "audit.v1"},
        internal_idempotency_key=key,
        request_id=None,
        priority=10,
        max_attempts=2,
        timeout_seconds=30,
    )


def test_terminal_event_preserves_worker_identity(database_runtime: DatabaseRuntime) -> None:
    session = database_runtime.new_session()
    repository = PostgresJobRepository(session)
    try:
        with session.begin():
            job = _enqueue(repository, key="terminal-worker")
        with session.begin():
            claimed = repository.claim_next(
                supported_job_types=("test.audit.v1",),
                worker_id="worker-a",
                lease_seconds=10,
            )
        assert claimed is not None
        assert claimed.lease_token is not None

        with session.begin():
            repository.succeed(
                job_id=job.id,
                lease_token=claimed.lease_token,
                result={"ok": True},
            )
        with session.begin():
            events = repository.list_events(job.id)

        assert [event.event_type for event in events] == ["claimed", "succeeded"]
        assert events[-1].worker_id == "worker-a"
    finally:
        session.close()


def test_stale_worker_cannot_commit_terminal_state_after_takeover(
    database_runtime: DatabaseRuntime,
) -> None:
    session_a = database_runtime.new_session()
    session_b = database_runtime.new_session()
    repository_a = PostgresJobRepository(session_a)
    repository_b = PostgresJobRepository(session_b)
    try:
        with session_a.begin():
            job = _enqueue(repository_a, key="stale-terminal")
        with session_a.begin():
            first = repository_a.claim_next(
                supported_job_types=("test.audit.v1",),
                worker_id="worker-a",
                lease_seconds=10,
            )
        assert first is not None
        assert first.lease_token is not None

        with session_b.begin():
            session_b.execute(
                text(
                    "UPDATE jobs "
                    "SET lease_expires_at = clock_timestamp() - interval '1 second' "
                    "WHERE id = :job_id"
                ),
                {"job_id": job.id},
            )
        with session_b.begin():
            takeover = repository_b.claim_next(
                supported_job_types=("test.audit.v1",),
                worker_id="worker-b",
                lease_seconds=10,
            )
        assert takeover is not None

        with session_a.begin():
            with pytest.raises(LeaseLostError):
                repository_a.succeed(
                    job_id=job.id,
                    lease_token=first.lease_token,
                    result={"stale": True},
                )
    finally:
        session_a.close()
        session_b.close()
