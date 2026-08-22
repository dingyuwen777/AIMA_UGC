"""Collection Run PostgreSQL Fencing Gateway 集成测试。"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete, select


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        _clear_data(connection)
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            _clear_data(connection)
        runtime.dispose()


def _clear_data(connection) -> None:
    connection.execute(delete(collection_scopes_table))
    connection.execute(delete(collection_runs_table))
    connection.execute(delete(job_attempt_events_table))
    connection.execute(delete(jobs_table))


def _prepare_claimed_execution(
    runtime: DatabaseRuntime,
) -> tuple[CollectionExecution, JobExecutionFence]:
    session = runtime.new_session()
    try:
        with session.begin():
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=uuid4().hex,
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            execution = CollectionExecutionService(
                PostgresCollectionRepository(session)
            ).create_run(
                job_id=job.id,
                trigger_type="manual",
                config_snapshot={},
                scopes=(
                    CollectionScopeDefinition(
                        platform="xiaohongshu",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="collection-run-gateway-test",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        return execution, JobExecutionFence(job_id=claimed.id, lease_token=claimed.lease_token)
    finally:
        session.close()


def test_gateway_applies_current_fence_to_run_and_scope_transitions(
    database_runtime: DatabaseRuntime,
) -> None:
    execution, fence = _prepare_claimed_execution(database_runtime)
    gateway = PostgresCollectionRunExecutionGateway(database_runtime.new_session)

    loaded = gateway.load(fence)
    assert loaded is not None
    assert loaded.run.id == execution.run.id
    assert [scope.id for scope in loaded.scopes] == [execution.scopes[0].id]

    running_run = gateway.start_run(execution.run.id, fence=fence)
    running_scope = gateway.start_scope(execution.scopes[0].id, fence=fence)
    finished_scope = gateway.finish_scope(
        execution.scopes[0].id,
        fence=fence,
        status="succeeded",
        stop_reason="provider_exhausted",
        pagination_state={"page": 1},
        stats={"requests": 1, "contents": 2},
    )
    finished_run = gateway.finish_run(
        execution.run.id,
        fence=fence,
        status="succeeded",
        requested_count=1,
        succeeded_count=1,
        failed_count=0,
        content_count=2,
        comment_count=0,
        error_summary=None,
    )

    assert running_run.status == "running"
    assert running_scope.status == "running"
    assert finished_scope.status == "succeeded"
    assert finished_scope.progress == 100
    assert finished_run.status == "succeeded"
    assert finished_run.requested_count == 1
    assert finished_run.content_count == 2


def test_stale_fence_cannot_mutate_collection_run(
    database_runtime: DatabaseRuntime,
) -> None:
    execution, fence = _prepare_claimed_execution(database_runtime)
    gateway = PostgresCollectionRunExecutionGateway(database_runtime.new_session)
    stale_fence = JobExecutionFence(job_id=fence.job_id, lease_token="stale-token")

    with pytest.raises(LeaseLostError):
        gateway.start_run(execution.run.id, fence=stale_fence)

    session = database_runtime.new_session()
    try:
        with session.begin():
            status = session.scalar(
                select(collection_runs_table.c.status).where(
                    collection_runs_table.c.id == execution.run.id
                )
            )
        assert status == "queued"
    finally:
        session.close()
