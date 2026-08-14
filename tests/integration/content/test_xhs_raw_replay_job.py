"""Stage 6 已存 Raw → Job → Candidate/Canonical/Ingestion 端到端测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert, select

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.xhs_replay import (
    PostgresXhsReplayIngestionWriter,
    PostgresXhsReplaySourceReader,
)
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.contracts.provider import ProviderBillingV1, ProviderRequestV1
from aima_ugc.modules.collection.providers import ProviderClient, RawArtifactService
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.collection.xhs_replay import (
    XhsRawReplayHandler,
    register_xhs_raw_replay_job,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobRegistry, JobWorker
from aima_ugc.platform.storage import ArtifactService

_FIXTURE = Path("tests/fixtures/providers/tikhub/xhs/search_notes_page1.sanitized.json")
_NOW = datetime(2026, 8, 5, 10, 0, 12, tzinfo=UTC)


def test_job_replays_linked_raw_without_second_provider_call(tmp_path: Path) -> None:
    runtime = DatabaseRuntime(load_settings())
    store = LocalArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    artifact_service = ArtifactService(
        metadata=PostgresArtifactMetadataGateway(runtime.new_session),
        store=store,
    )
    raw_service = RawArtifactService(artifacts=artifact_service, store=store)
    fake = FakeProviderTransport(
        [
            ProviderTransportResponse(
                status_code=200,
                external_request_id="fixture-provider-request",
                body=json.loads(_FIXTURE.read_text(encoding="utf-8")),
                billing=ProviderBillingV1(status="not_billable"),
            )
        ]
    )
    client = ProviderClient(transport=fake, clock=lambda: _NOW)
    session = runtime.new_session()
    try:
        with session.begin():
            jobs = PostgresJobRepository(session)
            source_job = jobs.enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"stage6-source:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            run_id = uuid4()
            scope_id = uuid4()
            request_id = uuid4()
            attempt_id = uuid4()
            session.execute(
                insert(collection_runs_table).values(
                    id=run_id,
                    job_id=source_job.id,
                    trigger_type="backfill",
                    config_snapshot={"platforms": ["xhs"]},
                    status="running",
                    created_at=_NOW,
                )
            )
            session.execute(
                insert(collection_scopes_table).values(
                    id=scope_id,
                    run_id=run_id,
                    platform="xhs",
                    source_type="keyword_search",
                    source_value="爱玛",
                    operation_group="content_discovery",
                    status="running",
                )
            )
            request = ProviderRequestV1.create(
                request_id=request_id,
                run_id=run_id,
                scope_id=scope_id,
                provider="tikhub",
                platform="xhs",
                operation="search_notes",
                request_params={"keyword": "爱玛"},
            )
            session.execute(
                insert(provider_requests_table).values(
                    id=request_id,
                    scope_id=scope_id,
                    provider="tikhub",
                    operation="search_notes",
                    request_fingerprint=request.request_fingerprint,
                    request_params=request.request_params,
                    pagination_input=request.pagination_input,
                    status="dispatching",
                    attempt_count=1,
                    created_at=_NOW,
                )
            )

        dispatch = client.dispatch(
            request=request,
            attempt_id=attempt_id,
            attempt_no=1,
            transport_request=ProviderTransportRequest(
                transport_kind="http",
                method="GET",
                path="/api/v1/xiaohongshu/app_v2/search_notes",
                params={"keyword": "爱玛"},
            ),
            dispatch_started_at=_NOW,
        )
        captured = raw_service.capture(request=request, dispatch=dispatch)
        assert fake.call_count == 1

        with session.begin():
            session.execute(
                insert(provider_request_attempts_table).values(
                    id=attempt_id,
                    provider_request_id=request_id,
                    attempt_no=1,
                    dispatch_status="completed",
                    dispatch_started_at=_NOW,
                    completed_at=_NOW,
                    http_status=200,
                    external_request_id="fixture-provider-request",
                    raw_artifact_id=captured.artifact.id,
                    billing_status="not_billable",
                    created_at=_NOW,
                )
            )
            session.execute(
                provider_requests_table.update()
                .where(provider_requests_table.c.id == request_id)
                .values(status="completed", completed_at=_NOW)
            )
        artifact_service.link(captured.artifact.id)

        with session.begin():
            replay_job = PostgresJobRepository(session).enqueue(
                job_type="collection.xhs.raw-replay.v1",
                payload_version="collection.xhs.raw-replay.v1",
                payload={
                    "schema_version": "collection.xhs.raw-replay.v1",
                    "provider_attempt_id": str(attempt_id),
                },
                internal_idempotency_key=f"stage6-replay:{attempt_id}",
                request_id=None,
                priority=20,
                max_attempts=2,
                timeout_seconds=300,
            )

        registry = JobRegistry()
        register_xhs_raw_replay_job(
            registry,
            XhsRawReplayHandler(
                raw_artifacts=raw_service,
                source_reader=PostgresXhsReplaySourceReader(runtime.new_session),
                ingestion_writer=PostgresXhsReplayIngestionWriter(runtime.new_session),
            ),
        )
        worker = JobWorker(
            session_factory=runtime.new_session,
            registry=registry,
            worker_id="stage6-test-worker",
            lease_seconds=30,
            retry_delay_seconds=0,
        )
        assert worker.run_once() is True
        assert fake.call_count == 1

        with session.begin():
            stored_job = PostgresJobRepository(session).get(replay_job.id)
            content_ids = (
                session.execute(
                    select(contents_table.c.id).where(
                        contents_table.c.platform == "xhs",
                        contents_table.c.external_content_id.in_(
                            ["note-fixture-1", "note-fixture-2"]
                        ),
                    )
                )
                .scalars()
                .all()
            )
        assert stored_job is not None
        assert stored_job.status == "succeeded"
        assert len(content_ids) == 2
    finally:
        session.rollback()
        session.close()
        runtime.dispose()
