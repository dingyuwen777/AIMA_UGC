"""非重试 Provider 4xx 在 Worker takeover 后不得再次发送。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_provider_execution import (
    PostgresFencedProviderAttemptPreparer,
)
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.provider import PostgresProviderRepository
from aima_ugc.adapters.persistence.postgres.provider_dispatch import (
    PostgresProviderDispatchPersistence,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.providers.tikhub.pricing import load_tikhub_pricing
from aima_ugc.adapters.providers.tikhub.runtime import build_search_call
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.provider_dispatch import ProviderDispatchService
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.modules.collection.tables import collection_scopes_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import func, select, update

_OBSERVED_AT = datetime(2026, 8, 17, 7, 0, tzinfo=UTC)


@dataclass
class _Context:
    fence: JobExecutionFence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _raw_service(runtime: DatabaseRuntime, root: Path) -> RawArtifactService:
    store = LocalArtifactStore(root)
    return RawArtifactService(
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.new_session),
            store=store,
        ),
        store=store,
    )


def test_completed_http_400_is_not_resent_after_worker_takeover(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Nonretryable Recovery",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/nonretryable-recovery",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"nonretryable-recovery:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            execution = CollectionExecutionService(
                PostgresCollectionRepository(session)
            ).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={
                    "schema_version": "collection-run-config.v1",
                    "detail_policy": "on_change",
                    "comment_policy": "adaptive",
                    "platforms": [
                        {
                            "platform": "xhs",
                            "provider_config_id": str(provider_config.id),
                            "config": {
                                "sort_mode": "latest",
                                "published_within": "1d",
                                "content_type": "all",
                            },
                        }
                    ],
                },
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="nonretryable-old-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
    finally:
        session.close()

    old_fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    scope = execution.scopes[0]
    call = build_search_call(
        platform="xhs",
        keyword=scope.source_value,
        config={
            "sort_mode": "latest",
            "published_within": "1d",
            "content_type": "all",
        },
        state={},
    )
    request_params = {
        "method": call.method,
        "path": call.path,
        "params": dict(call.params),
    }
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=execution.run.id,
        scope_id=scope.id,
        provider="tikhub",
        platform="xhs",
        operation=call.operation,
        request_params=request_params,
        pagination_input=dict(call.pagination_input or {}),
    )
    billing = load_tikhub_pricing().billing_for_endpoint(call.path)
    prepared = PostgresFencedProviderAttemptPreparer(
        database_runtime.new_session
    ).resolve_or_prepare_billable_attempt(
        request=request,
        provider_config_id=provider_config.id,
        attempt_id=uuid4(),
        billing=billing,
        fence=old_fence,
    )
    raw_artifacts = _raw_service(database_runtime, tmp_path / "artifacts")
    first_transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=400, body={"error": "fixture-bad-request"}),)
    )
    first_outcome = ProviderDispatchService(
        persistence=PostgresProviderDispatchPersistence(database_runtime.new_session),
        client=ProviderClient(transport=first_transport),
        raw_artifacts=raw_artifacts,
    ).dispatch(
        attempt_id=prepared.attempt.id,
        fence=old_fence,
        transport_request=call.transport_request(SecretStr("fixture-secret")),
    )
    assert first_transport.call_count == 1
    assert first_outcome.attempt.dispatch_status == "completed"
    assert first_outcome.attempt.http_status == 400
    assert first_outcome.attempt.error_code == "http_400"
    assert first_outcome.artifact is not None

    with database_runtime.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == job.id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    session = database_runtime.new_session()
    try:
        with session.begin():
            takeover = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="nonretryable-new-worker",
                lease_seconds=120,
            )
        assert takeover is not None and takeover.lease_token is not None
    finally:
        session.close()

    takeover_fence = JobExecutionFence(job_id=job.id, lease_token=takeover.lease_token)
    resumed_transport = FakeProviderTransport(())
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=database_runtime.new_session,
            raw_artifacts=raw_artifacts,
            transport_factory=lambda _config: resumed_transport,
            secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=takeover_fence, context=_Context(takeover_fence))

    assert result.outcome == "failed"
    assert resumed_transport.call_count == 0

    session = database_runtime.new_session()
    try:
        with session.begin():
            attempts = PostgresProviderRepository(session).list_attempts(prepared.request.id)
            stored_scope = (
                session.execute(
                    select(collection_scopes_table).where(collection_scopes_table.c.id == scope.id)
                )
                .mappings()
                .one()
            )
    finally:
        session.close()
    assert len(attempts) == 1
    assert attempts[0].id == first_outcome.attempt.id
    assert attempts[0].http_status == 400
    assert attempts[0].error_code == "http_400"
    assert attempts[0].raw_artifact_id == first_outcome.artifact.id
    assert stored_scope["status"] == "failed"
    assert stored_scope["stop_reason"] == "http_400"
