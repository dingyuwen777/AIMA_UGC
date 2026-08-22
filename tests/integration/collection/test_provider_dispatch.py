"""Stage 5D Provider Dispatch 的 PostgreSQL/Artifact 纵切验证。"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
    PostgresProviderRecoveryPersistence,
)
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_dispatch import (
    ProviderAttemptStateConflict,
    ProviderDispatchService,
)
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.collection.provider_recovery import ProviderAttemptReconciler
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportFailure,
    ProviderTransportRequest,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import delete, func, select, update


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
    connection.execute(delete(provider_request_attempts_table))
    connection.execute(delete(provider_requests_table))
    connection.execute(delete(collection_scopes_table))
    connection.execute(delete(collection_runs_table))
    connection.execute(delete(job_attempt_events_table))
    connection.execute(delete(jobs_table))
    connection.execute(delete(artifacts_table))


def _prepare_claimed_attempt(runtime: DatabaseRuntime):
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
            request = ProviderRequestV1.create(
                request_id=uuid4(),
                run_id=execution.run.id,
                scope_id=execution.scopes[0].id,
                provider="fake_provider",
                platform="xiaohongshu",
                operation="keyword_search",
                request_params={"keyword": "爱玛"},
            )
            prepared = ProviderPersistenceService(
                PostgresProviderRepository(session)
            ).prepare_non_billable_attempt(request=request, attempt_id=uuid4())
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="stage5d-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        return (
            request,
            prepared.attempt,
            JobExecutionFence(job_id=claimed.id, lease_token=claimed.lease_token),
        )
    finally:
        session.close()


def _service(
    runtime: DatabaseRuntime,
    *,
    artifact_root: Path,
    transport: FakeProviderTransport,
) -> ProviderDispatchService:
    raw_artifacts = _raw_service(runtime, artifact_root=artifact_root)
    return ProviderDispatchService(
        persistence=PostgresProviderDispatchPersistence(runtime.new_session),
        client=ProviderClient(transport=transport),
        raw_artifacts=raw_artifacts,
    )


def _raw_service(
    runtime: DatabaseRuntime,
    *,
    artifact_root: Path,
) -> RawArtifactService:
    store = LocalArtifactStore(artifact_root)
    return RawArtifactService(
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.new_session),
            store=store,
        ),
        store=store,
    )


def _expire_lease(runtime: DatabaseRuntime, job_id) -> None:
    session = runtime.new_session()
    try:
        with session.begin():
            session.execute(
                update(jobs_table)
                .where(jobs_table.c.id == job_id)
                .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
            )
    finally:
        session.close()


def test_dispatch_fences_calls_and_atomically_links_raw(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _, prepared_attempt, fence = _prepare_claimed_attempt(database_runtime)
    transport = FakeProviderTransport(
        [ProviderTransportResponse(status_code=200, body={"items": []})]
    )
    service = _service(database_runtime, artifact_root=tmp_path, transport=transport)

    outcome = service.dispatch(
        attempt_id=prepared_attempt.id,
        fence=fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    assert transport.call_count == 1
    assert outcome.attempt.dispatch_status == "completed"
    assert outcome.artifact is not None
    session = database_runtime.new_session()
    try:
        with session.begin():
            stored_attempt = PostgresProviderRepository(session).list_attempts(
                outcome.attempt.provider_request_id
            )[0]
            request_status = session.scalar(
                select(provider_requests_table.c.status).where(
                    provider_requests_table.c.id == outcome.attempt.provider_request_id
                )
            )
            artifact_status = session.scalar(
                select(artifacts_table.c.storage_status).where(
                    artifacts_table.c.id == outcome.artifact.id
                )
            )
        assert stored_attempt.raw_artifact_id == outcome.artifact.id
        assert request_status == "completed"
        assert artifact_status == "linked"
    finally:
        session.close()


def test_stale_fence_cannot_call_transport(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _, prepared_attempt, fence = _prepare_claimed_attempt(database_runtime)
    transport = FakeProviderTransport(
        [ProviderTransportResponse(status_code=200, body={"items": []})]
    )
    service = _service(database_runtime, artifact_root=tmp_path, transport=transport)

    with pytest.raises(LeaseLostError):
        service.dispatch(
            attempt_id=prepared_attempt.id,
            fence=JobExecutionFence(job_id=fence.job_id, lease_token="stale-token"),
            transport_request=ProviderTransportRequest(
                transport_kind="http",
                method="GET",
                path="/fake/search",
            ),
        )

    assert transport.call_count == 0


def test_concurrent_dispatch_cas_has_one_winner(
    database_runtime: DatabaseRuntime,
) -> None:
    _, prepared_attempt, fence = _prepare_claimed_attempt(database_runtime)
    persistence = PostgresProviderDispatchPersistence(database_runtime.new_session)
    barrier = Barrier(2)

    def start() -> str:
        barrier.wait()
        try:
            return persistence.start_dispatch(
                attempt_id=prepared_attempt.id,
                fence=fence,
            ).attempt.dispatch_status
        except ProviderAttemptStateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result() for future in (executor.submit(start), executor.submit(start))]

    assert sorted(results) == ["conflict", "dispatching"]


def test_definitive_not_sent_is_persisted_without_raw(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    request, prepared_attempt, fence = _prepare_claimed_attempt(database_runtime)
    transport = FakeProviderTransport(
        [
            ProviderTransportFailure.not_sent(
                code="connect_failed",
                safe_summary="连接建立前失败",
            )
        ]
    )

    outcome = _service(
        database_runtime,
        artifact_root=tmp_path,
        transport=transport,
    ).dispatch(
        attempt_id=prepared_attempt.id,
        fence=fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    assert transport.call_count == 1
    assert outcome.attempt.dispatch_status == "not_sent"
    assert outcome.attempt.dispatch_started_at is None
    assert outcome.artifact is None
    session = database_runtime.new_session()
    try:
        with session.begin():
            request_status = session.scalar(
                select(provider_requests_table.c.status).where(
                    provider_requests_table.c.id == request.request_id
                )
            )
            artifact_count = session.scalar(select(func.count()).select_from(artifacts_table))
        assert request_status == "not_sent"
        assert artifact_count == 0
    finally:
        session.close()


def test_unknown_delivery_persists_linked_raw_and_unknown_billing(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _, prepared_attempt, fence = _prepare_claimed_attempt(database_runtime)
    transport = FakeProviderTransport(
        [
            ProviderTransportFailure.unknown(
                code="socket_reset",
                safe_summary="发送后连接中断",
            )
        ]
    )

    outcome = _service(
        database_runtime,
        artifact_root=tmp_path,
        transport=transport,
    ).dispatch(
        attempt_id=prepared_attempt.id,
        fence=fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    assert transport.call_count == 1
    assert outcome.attempt.dispatch_status == "unknown"
    assert outcome.attempt.billing_status == "unknown"
    assert outcome.attempt.potential_duplicate_charge is True
    assert outcome.artifact is not None
    session = database_runtime.new_session()
    try:
        with session.begin():
            artifact_status = session.scalar(
                select(artifacts_table.c.storage_status).where(
                    artifacts_table.c.id == outcome.artifact.id
                )
            )
        assert artifact_status == "linked"
    finally:
        session.close()


def test_older_attempt_does_not_overwrite_latest_request_status(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    request, first_attempt, fence = _prepare_claimed_attempt(database_runtime)
    session = database_runtime.new_session()
    try:
        with session.begin():
            second = ProviderPersistenceService(
                PostgresProviderRepository(session)
            ).prepare_non_billable_attempt(request=request, attempt_id=uuid4())
        assert second.attempt.attempt_no == 2
    finally:
        session.close()

    service = _service(
        database_runtime,
        artifact_root=tmp_path,
        transport=FakeProviderTransport(
            [ProviderTransportResponse(status_code=200, body={"items": []})]
        ),
    )
    service.dispatch(
        attempt_id=first_attempt.id,
        fence=fence,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            request_status = session.scalar(
                select(provider_requests_table.c.status).where(
                    provider_requests_table.c.id == request.request_id
                )
            )
            statuses = session.execute(
                select(
                    provider_request_attempts_table.c.attempt_no,
                    provider_request_attempts_table.c.dispatch_status,
                )
                .where(provider_request_attempts_table.c.provider_request_id == request.request_id)
                .order_by(provider_request_attempts_table.c.attempt_no)
            ).all()
        assert request_status == "pending"
        assert statuses == [(1, "completed"), (2, "reserved")]
    finally:
        session.close()


def test_takeover_recovers_verified_stored_raw_without_resending(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    request, prepared_attempt, old_fence = _prepare_claimed_attempt(database_runtime)
    persistence = PostgresProviderDispatchPersistence(database_runtime.new_session)
    dispatching = persistence.start_dispatch(
        attempt_id=prepared_attempt.id,
        fence=old_fence,
    )
    transport = FakeProviderTransport(
        [ProviderTransportResponse(status_code=200, body={"items": []})]
    )
    client_result = ProviderClient(transport=transport).dispatch(
        request=request,
        attempt_id=prepared_attempt.id,
        attempt_no=prepared_attempt.attempt_no,
        transport_request=ProviderTransportRequest(
            transport_kind="http",
            method="GET",
            path="/fake/search",
        ),
        dispatch_started_at=dispatching.attempt.dispatch_started_at,
    )
    raw_artifacts = _raw_service(database_runtime, artifact_root=tmp_path)
    captured = raw_artifacts.capture(request=request, dispatch=client_result)
    assert captured.artifact.storage_status == "stored"

    _expire_lease(database_runtime, old_fence.job_id)
    with pytest.raises(LeaseLostError):
        persistence.finalize_dispatch(
            attempt=captured.attempt,
            raw_artifact_id=captured.artifact.id,
            fence=old_fence,
        )
    session = database_runtime.new_session()
    try:
        with session.begin():
            before_recovery = PostgresProviderRepository(session).list_attempts(
                prepared_attempt.provider_request_id
            )[0]
            before_artifact_status = session.scalar(
                select(artifacts_table.c.storage_status).where(
                    artifacts_table.c.id == captured.artifact.id
                )
            )
        assert before_recovery.dispatch_status == "dispatching"
        assert before_recovery.raw_artifact_id is None
        assert before_artifact_status == "stored"
    finally:
        session.close()

    session = database_runtime.new_session()
    try:
        with session.begin():
            takeover = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="stage5d-takeover",
                lease_seconds=120,
            )
        assert takeover is not None and takeover.lease_token is not None
    finally:
        session.close()

    reconciler = ProviderAttemptReconciler(
        persistence=PostgresProviderRecoveryPersistence(database_runtime.new_session),
        raw_artifacts=raw_artifacts,
    )
    recovered = reconciler.recover_inherited(
        JobExecutionFence(job_id=takeover.id, lease_token=takeover.lease_token)
    )

    assert recovered == 1
    assert transport.call_count == 1
    session = database_runtime.new_session()
    try:
        with session.begin():
            attempt = PostgresProviderRepository(session).list_attempts(
                prepared_attempt.provider_request_id
            )[0]
            artifact_status = session.scalar(
                select(artifacts_table.c.storage_status).where(
                    artifacts_table.c.id == captured.artifact.id
                )
            )
        assert attempt.dispatch_status == "completed"
        assert attempt.raw_artifact_id == captured.artifact.id
        assert artifact_status == "linked"
    finally:
        session.close()


def test_expired_dispatch_without_raw_is_reconciled_to_unknown(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _, prepared_attempt, fence = _prepare_claimed_attempt(database_runtime)
    PostgresProviderDispatchPersistence(database_runtime.new_session).start_dispatch(
        attempt_id=prepared_attempt.id,
        fence=fence,
    )
    _expire_lease(database_runtime, fence.job_id)
    reconciler = ProviderAttemptReconciler(
        persistence=PostgresProviderRecoveryPersistence(database_runtime.new_session),
        raw_artifacts=_raw_service(database_runtime, artifact_root=tmp_path),
    )

    assert reconciler.reap_once() is True
    assert reconciler.reap_once() is False
    session = database_runtime.new_session()
    try:
        with session.begin():
            attempt = PostgresProviderRepository(session).list_attempts(
                prepared_attempt.provider_request_id
            )[0]
        assert attempt.dispatch_status == "unknown"
        assert attempt.raw_artifact_id is None
        assert attempt.billing_status == "unknown"
        assert attempt.potential_duplicate_charge is True
        assert attempt.error_code == "dispatch_recovery_unknown"
    finally:
        session.close()
