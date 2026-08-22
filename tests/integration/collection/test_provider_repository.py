from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Lock
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_persistence import (
    ProviderPersistenceConflictError,
    ProviderPersistenceService,
    ProviderRequestLineageMismatchError,
    ProviderScopeNotFoundError,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from sqlalchemy import delete, event, func, insert, select, update
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        _clear_collection_data(connection)
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            _clear_collection_data(connection)
        runtime.dispose()


def _clear_collection_data(connection) -> None:
    connection.execute(delete(provider_request_attempts_table))
    connection.execute(delete(provider_requests_table))
    connection.execute(delete(collection_scopes_table))
    connection.execute(delete(collection_runs_table))
    connection.execute(delete(job_attempt_events_table))
    connection.execute(delete(jobs_table))


def _create_scope(runtime: DatabaseRuntime, *, key: str, platform: str = "xiaohongshu"):
    session = runtime.new_session()
    try:
        with session.begin():
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=key,
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
                        platform=platform,
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        return execution.run, execution.scopes[0]
    finally:
        session.close()


def _request(*, request_id: UUID, run_id: UUID, scope_id: UUID, provider: str = "fake"):
    return ProviderRequestV1.create(
        request_id=request_id,
        run_id=run_id,
        scope_id=scope_id,
        provider=provider,
        platform="xiaohongshu",
        operation="search_notes",
        request_params={"keyword": "爱玛"},
        pagination_input={"page": 1},
    )


def test_service_idempotently_persists_request_and_attempt(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-idempotency")
    request = _request(request_id=uuid4(), run_id=run.id, scope_id=scope.id)
    attempt_id = uuid4()
    session = database_runtime.new_session()
    service = ProviderPersistenceService(PostgresProviderRepository(session))
    try:
        with session.begin():
            first = service.prepare_non_billable_attempt(
                request=request,
                attempt_id=attempt_id,
            )
        with session.begin():
            replay = service.prepare_non_billable_attempt(
                request=request.model_copy(update={"request_id": uuid4()}),
                attempt_id=attempt_id,
            )
            second_attempt = service.prepare_non_billable_attempt(
                request=request,
                attempt_id=uuid4(),
            )
            stored_attempts = PostgresProviderRepository(session).list_attempts(first.request.id)

        assert replay == first
        assert first.request.status == "pending"
        assert first.request.scope_id == scope.id
        assert first.request.attempt_count == 1
        assert first.attempt.dispatch_status == "reserved"
        assert first.attempt.billing_status == "not_billable"
        assert first.attempt.estimated_cost == 0
        assert first.attempt.actual_cost == 0
        assert first.attempt.raw_artifact_id is None
        assert second_attempt.request.id == first.request.id
        assert second_attempt.attempt.attempt_no == 2
        assert [attempt.attempt_no for attempt in stored_attempts] == [1, 2]
    finally:
        session.close()


def test_repository_rejects_missing_or_mismatched_scope_lineage(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-lineage")
    session = database_runtime.new_session()
    repository = PostgresProviderRepository(session)
    try:
        with pytest.raises(ProviderScopeNotFoundError), session.begin():
            repository.create_or_get_request(
                _request(request_id=uuid4(), run_id=run.id, scope_id=uuid4())
            )

        with pytest.raises(ProviderRequestLineageMismatchError), session.begin():
            repository.create_or_get_request(
                _request(request_id=uuid4(), run_id=uuid4(), scope_id=scope.id)
            )

        mismatched_platform = _request(
            request_id=uuid4(),
            run_id=run.id,
            scope_id=scope.id,
        ).model_copy(update={"platform": "douyin"})
        with pytest.raises(ProviderRequestLineageMismatchError), session.begin():
            repository.create_or_get_request(mismatched_platform)
    finally:
        session.close()


def test_repository_closes_failed_on_id_or_logical_request_conflicts(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-conflicts")
    request = _request(request_id=uuid4(), run_id=run.id, scope_id=scope.id)
    session = database_runtime.new_session()
    repository = PostgresProviderRepository(session)
    try:
        with session.begin():
            stored = repository.create_or_get_request(request)

        provider_conflict = request.model_copy(
            update={"request_id": uuid4(), "provider": "another"}
        )
        with pytest.raises(ProviderPersistenceConflictError), session.begin():
            repository.create_or_get_request(provider_conflict)

        different_request = ProviderRequestV1.create(
            request_id=stored.id,
            run_id=run.id,
            scope_id=scope.id,
            provider="fake",
            platform="xiaohongshu",
            operation="search_notes",
            request_params={"keyword": "爱玛电动车"},
            pagination_input={"page": 1},
        )
        with pytest.raises(ProviderPersistenceConflictError), session.begin():
            repository.create_or_get_request(different_request)
    finally:
        session.close()


def test_database_freezes_established_provider_lineage(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-lineage-freeze")
    session = database_runtime.new_session()
    service = ProviderPersistenceService(PostgresProviderRepository(session))
    try:
        with session.begin():
            prepared = service.prepare_non_billable_attempt(
                request=_request(request_id=uuid4(), run_id=run.id, scope_id=scope.id),
                attempt_id=uuid4(),
            )

        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                update(collection_scopes_table)
                .where(collection_scopes_table.c.id == scope.id)
                .values(source_value="另一个关键词")
            )

        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                update(provider_requests_table)
                .where(provider_requests_table.c.id == prepared.request.id)
                .values(provider="another")
            )

        with session.begin():
            session.execute(
                update(provider_request_attempts_table)
                .where(provider_request_attempts_table.c.id == prepared.attempt.id)
                .values(
                    dispatch_status="dispatching",
                    dispatch_started_at=prepared.attempt.created_at,
                )
            )

        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                update(provider_request_attempts_table)
                .where(provider_request_attempts_table.c.id == prepared.attempt.id)
                .values(provider_request_id=uuid4())
            )
    finally:
        session.close()


def test_database_enforces_provider_foreign_keys_checks_and_attempt_uniqueness(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-database-constraints")
    request = _request(request_id=uuid4(), run_id=run.id, scope_id=scope.id)
    session = database_runtime.new_session()
    repository = PostgresProviderRepository(session)
    try:
        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                insert(provider_requests_table).values(
                    id=uuid4(),
                    scope_id=uuid4(),
                    provider="fake",
                    operation="search_notes",
                    request_fingerprint="a" * 64,
                    request_params={},
                    pagination_input={},
                    status="pending",
                    created_at=func.clock_timestamp(),
                )
            )

        with session.begin():
            stored = repository.create_or_get_request(request)

        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                insert(provider_request_attempts_table).values(
                    id=uuid4(),
                    provider_request_id=stored.id,
                    attempt_no=1,
                    dispatch_status="reserved",
                    dispatch_started_at=func.clock_timestamp(),
                    billing_status="not_billable",
                    unit_price_snapshot=0,
                    created_at=func.clock_timestamp(),
                )
            )

        now = datetime.now(UTC)
        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                insert(provider_request_attempts_table).values(
                    id=uuid4(),
                    provider_request_id=stored.id,
                    attempt_no=1,
                    dispatch_status="completed",
                    dispatch_started_at=now,
                    completed_at=now,
                    raw_artifact_id=uuid4(),
                    billing_status="not_billable",
                    unit_price_snapshot=0,
                    created_at=now,
                )
            )

        with session.begin():
            first = repository.create_or_get_non_billable_attempt(
                provider_request_id=stored.id,
                attempt_id=uuid4(),
            )

        with pytest.raises(IntegrityError), session.begin():
            session.execute(
                insert(provider_request_attempts_table).values(
                    id=uuid4(),
                    provider_request_id=stored.id,
                    attempt_no=first.attempt_no,
                    dispatch_status="reserved",
                    billing_status="not_billable",
                    unit_price_snapshot=0,
                    created_at=func.clock_timestamp(),
                )
            )
    finally:
        session.close()


def test_repository_serializes_attempt_numbers_across_sessions(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-attempt-concurrency")
    request = _request(request_id=uuid4(), run_id=run.id, scope_id=scope.id)
    session = database_runtime.new_session()
    try:
        with session.begin():
            stored = PostgresProviderRepository(session).create_or_get_request(request)
    finally:
        session.close()

    def create_attempt(attempt_id: UUID) -> int:
        thread_session = database_runtime.new_session()
        try:
            with thread_session.begin():
                attempt = PostgresProviderRepository(
                    thread_session
                ).create_or_get_non_billable_attempt(
                    provider_request_id=stored.id,
                    attempt_id=attempt_id,
                )
            return attempt.attempt_no
        finally:
            thread_session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        numbers = set(executor.map(create_attempt, (uuid4(), uuid4())))

    verify_session = database_runtime.new_session()
    try:
        with verify_session.begin():
            persisted_count = verify_session.execute(
                select(provider_requests_table.c.attempt_count).where(
                    provider_requests_table.c.id == stored.id
                )
            ).scalar_one()
        assert numbers == {1, 2}
        assert persisted_count == 2
    finally:
        verify_session.close()


def test_repository_returns_stable_conflict_for_concurrent_attempt_id_collision(
    database_runtime: DatabaseRuntime,
) -> None:
    first_run, first_scope = _create_scope(database_runtime, key="provider-attempt-id-first")
    second_run, second_scope = _create_scope(database_runtime, key="provider-attempt-id-second")
    setup_session = database_runtime.new_session()
    try:
        with setup_session.begin():
            first_request = PostgresProviderRepository(setup_session).create_or_get_request(
                _request(request_id=uuid4(), run_id=first_run.id, scope_id=first_scope.id)
            )
            second_request = PostgresProviderRepository(setup_session).create_or_get_request(
                _request(request_id=uuid4(), run_id=second_run.id, scope_id=second_scope.id)
            )
    finally:
        setup_session.close()

    select_barrier = Barrier(2)
    synchronization_lock = Lock()
    synchronized_lookups = 0

    def synchronize_attempt_lookup(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal synchronized_lookups
        normalized = statement.lower()
        if (
            "from provider_request_attempts" in normalized
            and "where provider_request_attempts.id" in normalized
        ):
            with synchronization_lock:
                if synchronized_lookups >= 2:
                    return
                synchronized_lookups += 1
            select_barrier.wait(timeout=10)

    event.listen(database_runtime.engine, "before_cursor_execute", synchronize_attempt_lookup)
    shared_attempt_id = uuid4()

    def create_attempt(provider_request_id: UUID) -> str:
        thread_session = database_runtime.new_session()
        try:
            try:
                with thread_session.begin():
                    PostgresProviderRepository(thread_session).create_or_get_non_billable_attempt(
                        provider_request_id=provider_request_id,
                        attempt_id=shared_attempt_id,
                    )
            except ProviderPersistenceConflictError:
                return "conflict"
            return "created"
        finally:
            thread_session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create_attempt, (first_request.id, second_request.id)))
    finally:
        event.remove(
            database_runtime.engine,
            "before_cursor_execute",
            synchronize_attempt_lookup,
        )

    verify_session = database_runtime.new_session()
    try:
        with verify_session.begin():
            attempt_counts = list(
                verify_session.execute(
                    select(provider_requests_table.c.attempt_count).where(
                        provider_requests_table.c.id.in_((first_request.id, second_request.id))
                    )
                ).scalars()
            )
        assert sorted(results) == ["conflict", "created"]
        assert sorted(attempt_counts) == [0, 1]
    finally:
        verify_session.close()


def test_repository_never_commits_caller_transaction(
    database_runtime: DatabaseRuntime,
) -> None:
    run, scope = _create_scope(database_runtime, key="provider-caller-rollback")
    request = _request(request_id=uuid4(), run_id=run.id, scope_id=scope.id)
    session = database_runtime.new_session()
    repository = PostgresProviderRepository(session)
    service = ProviderPersistenceService(repository)
    try:
        with pytest.raises(RuntimeError, match="force rollback"), session.begin():
            service.prepare_non_billable_attempt(request=request, attempt_id=uuid4())
            raise RuntimeError("force rollback")

        with session.begin():
            assert repository.get_request(request.request_id) is None
    finally:
        session.close()
