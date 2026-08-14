from __future__ import annotations

from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionRunTrigger,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.tables import collection_runs_table, collection_scopes_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.execute(delete(collection_scopes_table))
        connection.execute(delete(collection_runs_table))
        connection.execute(delete(job_attempt_events_table))
        connection.execute(delete(jobs_table))
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.execute(delete(collection_scopes_table))
            connection.execute(delete(collection_runs_table))
            connection.execute(delete(job_attempt_events_table))
            connection.execute(delete(jobs_table))
        runtime.dispose()


def _enqueue_job(repository: PostgresJobRepository, *, key: str):
    return repository.enqueue(
        job_type="collection.run.v1",
        payload_version="collection.run.v1",
        payload={"schema_version": "collection.run.v1"},
        internal_idempotency_key=key,
        request_id=None,
        priority=10,
        max_attempts=2,
        timeout_seconds=300,
    )


def test_service_persists_run_and_scopes_bound_to_real_job(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    job_repository = PostgresJobRepository(session)
    collection_repository = PostgresCollectionRepository(session)
    service = CollectionExecutionService(collection_repository)
    try:
        with session.begin():
            job = _enqueue_job(job_repository, key="run-and-scopes")
            created = service.create_run(
                job_id=job.id,
                trigger_type="backfill",
                config_snapshot={
                    "schema_version": "collection-run-config.v1",
                    "platforms": ["xhs", "dy"],
                },
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                    CollectionScopeDefinition(
                        platform="dy",
                        source_type="keyword_search",
                        source_value="爱玛电动车",
                        operation_group="content_discovery",
                    ),
                ),
            )

        assert created.run.job_id == job.id
        assert created.run.trigger_type == "backfill"
        assert created.run.status == "queued"
        assert created.run.config_snapshot["platforms"] == ["xhs", "dy"]
        assert created.run.requested_count == 0
        assert {scope.status for scope in created.scopes} == {"queued"}
        assert {scope.progress for scope in created.scopes} == {0}
        assert all(scope.pagination_state == {} for scope in created.scopes)
        assert all(scope.stats == {} for scope in created.scopes)

        with session.begin():
            stored_run = collection_repository.get_run_by_job_id(job.id)
            stored_scopes = collection_repository.list_scopes(created.run.id)

        assert stored_run == created.run
        assert {scope.identity for scope in stored_scopes} == {
            ("xhs", "keyword_search", "爱玛", "content_discovery"),
            ("dy", "keyword_search", "爱玛电动车", "content_discovery"),
        }
    finally:
        session.close()


def test_database_rejects_missing_job_and_duplicate_scope_identity(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    repository = PostgresCollectionRepository(session)
    duplicate = CollectionScopeDefinition(
        platform="xhs",
        source_type="keyword_search",
        source_value="爱玛",
        operation_group="content_discovery",
    )
    try:
        with pytest.raises(IntegrityError), session.begin():
            repository.create_queued_run(
                job_id=uuid4(),
                trigger_type="manual",
                config_snapshot={},
                scopes=(),
            )

        job_repository = PostgresJobRepository(session)
        with session.begin():
            job = _enqueue_job(job_repository, key="duplicate-scope")

        with pytest.raises(IntegrityError), session.begin():
            repository.create_queued_run(
                job_id=job.id,
                trigger_type="manual",
                config_snapshot={},
                scopes=(duplicate, duplicate),
            )

        with session.begin():
            assert repository.get_run_by_job_id(job.id) is None
    finally:
        session.close()


def test_database_enforces_one_run_per_job_and_stage5b_trigger_set(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    job_repository = PostgresJobRepository(session)
    repository = PostgresCollectionRepository(session)
    try:
        with session.begin():
            unique_job = _enqueue_job(job_repository, key="unique-run")
            unsupported_trigger_job = _enqueue_job(job_repository, key="unsupported-trigger")
            first = repository.create_queued_run(
                job_id=unique_job.id,
                trigger_type="manual",
                config_snapshot={},
                scopes=(),
            )

        with pytest.raises(IntegrityError), session.begin():
            repository.create_queued_run(
                job_id=unique_job.id,
                trigger_type="api",
                config_snapshot={},
                scopes=(),
            )

        with pytest.raises(IntegrityError), session.begin():
            repository.create_queued_run(
                job_id=unsupported_trigger_job.id,
                trigger_type=cast(CollectionRunTrigger, "scheduled"),
                config_snapshot={},
                scopes=(),
            )

        with session.begin():
            assert repository.get_run_by_job_id(unique_job.id) == first.run
            assert repository.get_run_by_job_id(unsupported_trigger_job.id) is None
    finally:
        session.close()


def test_repository_never_commits_caller_transaction(database_runtime: DatabaseRuntime) -> None:
    session = database_runtime.new_session()
    job_repository = PostgresJobRepository(session)
    collection_repository = PostgresCollectionRepository(session)
    service = CollectionExecutionService(collection_repository)
    try:
        with session.begin():
            job = _enqueue_job(job_repository, key="caller-rollback")

        with pytest.raises(RuntimeError, match="force rollback"), session.begin():
            service.create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={},
                scopes=(),
            )
            raise RuntimeError("force rollback")

        with session.begin():
            assert collection_repository.get_run_by_job_id(job.id) is None
    finally:
        session.close()
