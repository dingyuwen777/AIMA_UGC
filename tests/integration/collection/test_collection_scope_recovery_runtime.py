"""正式 Collection Scope 在 Worker takeover 后复用已校验 Raw 的纵切回归。"""

from __future__ import annotations

import json
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
from aima_ugc.modules.collection.providers import (
    ProviderClient,
    ProviderTransportResponse,
    RawArtifactService,
)
from aima_ugc.modules.collection.tables import provider_requests_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import func, select, update

_FIXTURES = Path("tests/fixtures/providers/tikhub/xhs")
_OBSERVED_AT = datetime(2026, 8, 17, 6, 0, tzinfo=UTC)


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


def _fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _search_response() -> dict[str, object]:
    body = _fixture("search_notes_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    items = page["items"]
    assert isinstance(items, list) and items
    first = items[0]
    assert isinstance(first, dict)
    note = first["note"]
    assert isinstance(note, dict)
    note["comments_count"] = 0
    page["items"] = [first]
    page["has_more"] = False
    return body


def _detail_response() -> dict[str, object]:
    body = _fixture("image_detail.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    rows = outer["data"]
    assert isinstance(rows, list) and rows
    wrapper = rows[0]
    assert isinstance(wrapper, dict)
    notes = wrapper["note_list"]
    assert isinstance(notes, list) and notes
    note = notes[0]
    assert isinstance(note, dict)
    note["id"] = "note-fixture-1"
    note["comments_count"] = 0
    return body


def _raw_service(runtime: DatabaseRuntime, root: Path) -> RawArtifactService:
    store = LocalArtifactStore(root)
    return RawArtifactService(
        artifacts=ArtifactService(
            metadata=PostgresArtifactMetadataGateway(runtime.new_session),
            store=store,
        ),
        store=store,
    )


def test_takeover_reconciles_search_raw_then_formal_scope_replays_without_resend(
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
                    display_name="TikHub Recovery Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/recovery-runtime",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"scope-recovery:{uuid4()}",
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
            old_job = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id="recovery-old-worker",
                lease_seconds=120,
            )
        assert old_job is not None and old_job.lease_token is not None
    finally:
        session.close()

    old_fence = JobExecutionFence(job_id=job.id, lease_token=old_job.lease_token)
    scope = execution.scopes[0]
    platform_config = {
        "sort_mode": "latest",
        "published_within": "1d",
        "content_type": "all",
    }
    call = build_search_call(
        platform="xhs",
        keyword=scope.source_value,
        config=platform_config,
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
    persistence = PostgresProviderDispatchPersistence(database_runtime.new_session)
    dispatching = persistence.start_dispatch(attempt_id=prepared.attempt.id, fence=old_fence)

    first_transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=_search_response()),)
    )
    first_dispatch = ProviderClient(transport=first_transport).dispatch(
        request=dispatching.request,
        attempt_id=prepared.attempt.id,
        attempt_no=prepared.attempt.attempt_no,
        transport_request=call.transport_request(SecretStr("fixture-secret")),
        dispatch_started_at=dispatching.attempt.dispatch_started_at,
        planned_billing=billing,
    )
    raw_artifacts = _raw_service(database_runtime, tmp_path / "artifacts")
    captured = raw_artifacts.capture(request=dispatching.request, dispatch=first_dispatch)
    assert first_transport.call_count == 1
    assert captured.artifact.storage_status == "stored"

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
                worker_id="recovery-new-worker",
                lease_seconds=120,
            )
        assert takeover is not None and takeover.lease_token is not None
    finally:
        session.close()

    takeover_fence = JobExecutionFence(job_id=job.id, lease_token=takeover.lease_token)
    resumed_transport = FakeProviderTransport(
        (ProviderTransportResponse(status_code=200, body=_detail_response()),)
    )
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=database_runtime.new_session,
            raw_artifacts=raw_artifacts,
            transport_factory=lambda _config: resumed_transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=takeover_fence, context=_Context(takeover_fence))

    assert result.outcome == "succeeded"
    assert resumed_transport.call_count == 1
    assert [item.path for item in resumed_transport.seen_requests] == [
        "/api/v1/xiaohongshu/app_v2/get_image_note_detail"
    ]

    session = database_runtime.new_session()
    try:
        with session.begin():
            attempts = PostgresProviderRepository(session).list_attempts(prepared.request.id)
            search_attempt = attempts[0]
            request_count = session.scalar(
                select(func.count()).select_from(provider_requests_table)
            )
    finally:
        session.close()
    assert search_attempt.dispatch_status == "completed"
    assert search_attempt.raw_artifact_id == captured.artifact.id
    assert request_count == 2
