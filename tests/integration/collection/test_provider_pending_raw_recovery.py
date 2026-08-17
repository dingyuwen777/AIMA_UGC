"""Raw 文件已落盘但 Artifact metadata 仍 pending 的崩溃恢复回归。"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
    PostgresProviderRecoveryPersistence,
)
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.provider import ProviderRequestV1, RawEnvelopeV1
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_persistence import ProviderPersistenceService
from aima_ugc.modules.collection.provider_recovery import ProviderAttemptReconciler
from aima_ugc.modules.collection.providers import RawArtifactService, raw_storage_key
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import delete, func, insert, select, update


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


def _prepare_dispatching(runtime: DatabaseRuntime):
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
                        platform="xhs",
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
                platform="xhs",
                operation="keyword_search",
                request_params={"keyword": "爱玛"},
            )
            prepared = ProviderPersistenceService(
                PostgresProviderRepository(session)
            ).prepare_non_billable_attempt(request=request, attempt_id=uuid4())
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="pending-raw-old-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        fence = JobExecutionFence(job_id=claimed.id, lease_token=claimed.lease_token)
        dispatching = PostgresProviderDispatchPersistence(runtime.new_session).start_dispatch(
            attempt_id=prepared.attempt.id,
            fence=fence,
        )
        return request, prepared.attempt, dispatching.attempt.dispatch_started_at, fence
    finally:
        session.close()


def _expire_lease(runtime: DatabaseRuntime, job_id: UUID) -> JobExecutionFence:
    session = runtime.new_session()
    try:
        with session.begin():
            session.execute(
                update(jobs_table)
                .where(jobs_table.c.id == job_id)
                .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
            )
        with session.begin():
            takeover = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="pending-raw-takeover",
                lease_seconds=120,
            )
        assert takeover is not None and takeover.lease_token is not None
        return JobExecutionFence(job_id=takeover.id, lease_token=takeover.lease_token)
    finally:
        session.close()


def _write_pending_raw(
    runtime: DatabaseRuntime,
    *,
    artifact_root: Path,
    request: ProviderRequestV1,
    attempt_id: UUID,
    dispatch_started_at: datetime,
) -> UUID:
    completed_at = dispatch_started_at + timedelta(seconds=1)
    envelope = RawEnvelopeV1(
        provider=request.provider,
        platform=request.platform,
        operation=request.operation,
        request_id=request.request_id,
        attempt_id=attempt_id,
        run_id=request.run_id,
        scope_id=request.scope_id,
        requested_at=dispatch_started_at,
        completed_at=completed_at,
        dispatch_status="completed",
        request={
            "transport_kind": "http",
            "method": "GET",
            "path": "/fake/search",
            "params": {},
            "headers": {},
            "body": None,
        },
        response={
            "status_code": 200,
            "body": {"items": []},
            "external_request_id": None,
        },
        billing={
            "status": "not_billable",
            "unit_price_snapshot": 0,
            "estimated_cost": 0,
            "actual_cost": 0,
        },
        error=None,
    )
    plain = (
        json.dumps(
            envelope.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    compressed = gzip.compress(plain, compresslevel=9, mtime=0)
    storage_key = raw_storage_key(
        request=request,
        dispatch_started_at=dispatch_started_at,
        attempt_id=attempt_id,
    )
    artifact_id = uuid4()
    session = runtime.new_session()
    try:
        with session.begin():
            session.execute(
                insert(artifacts_table).values(
                    id=artifact_id,
                    kind="provider-raw",
                    storage_backend="local",
                    storage_key=storage_key,
                    content_type="application/json",
                    encoding="gzip",
                    sha256=None,
                    byte_size=None,
                    retention_class="raw",
                    storage_status="pending",
                    created_at=dispatch_started_at,
                )
            )
    finally:
        session.close()
    LocalArtifactStore(artifact_root).put(storage_key, compressed)
    assert hashlib.sha256(compressed).hexdigest()
    return artifact_id


def test_takeover_recovers_valid_file_when_metadata_is_still_pending(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    request, attempt, dispatch_started_at, old_fence = _prepare_dispatching(database_runtime)
    assert dispatch_started_at is not None
    artifact_id = _write_pending_raw(
        database_runtime,
        artifact_root=tmp_path,
        request=request,
        attempt_id=attempt.id,
        dispatch_started_at=dispatch_started_at,
    )
    takeover_fence = _expire_lease(database_runtime, old_fence.job_id)
    store = LocalArtifactStore(tmp_path)
    raw_artifacts = RawArtifactService(
        artifacts=ArtifactService(metadata=_NoopMetadata(), store=store),
        store=store,
    )
    reconciler = ProviderAttemptReconciler(
        persistence=PostgresProviderRecoveryPersistence(database_runtime.new_session),
        raw_artifacts=raw_artifacts,
    )

    assert reconciler.recover_inherited(takeover_fence) == 1

    session = database_runtime.new_session()
    try:
        with session.begin():
            persisted = PostgresProviderRepository(session).list_attempts(request.request_id)[0]
            artifact = (
                session.execute(select(artifacts_table).where(artifacts_table.c.id == artifact_id))
                .mappings()
                .one()
            )
        assert persisted.dispatch_status == "completed"
        assert persisted.raw_artifact_id == artifact_id
        assert artifact["storage_status"] == "linked"
        assert artifact["sha256"] is not None
        assert artifact["byte_size"] is not None
        assert artifact["stored_at"] is not None
    finally:
        session.close()


class _NoopMetadata:
    """本测试只使用 Raw replay，不允许测试自己修复 metadata。"""

    def create_pending(self, record) -> None:
        raise AssertionError("unexpected create_pending")

    def mark_stored(self, artifact_id, *, sha256, byte_size, stored_at):
        raise AssertionError("unexpected mark_stored")

    def mark_linked(self, artifact_id, *, linked_at):
        raise AssertionError("unexpected mark_linked")

    def mark_error(self, artifact_id):
        raise AssertionError("unexpected mark_error")
