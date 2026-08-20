"""正式 Collection Worker 对 Provider 可重试失败的跨 Attempt 回归。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.scheduler import create_scheduler_runtime
from aima_ugc.contracts.analysis import RelevanceSnapshotV1
from aima_ugc.entrypoints.worker_main import create_collection_job_registry, create_job_worker
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs.tables import jobs_table
from pydantic import SecretStr
from sqlalchemy import func, select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xhs")


@pytest.fixture
def platform_runtime() -> Iterator[PlatformRuntime]:
    runtime = create_scheduler_runtime()
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()


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


def test_http_500_retries_same_logical_request_with_new_provider_attempt(
    platform_runtime: PlatformRuntime,
) -> None:
    session = platform_runtime.database.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Retry Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/retry-runtime",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"retry-runtime:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={
                    "schema_version": "collection-run-config.v1",
                    "detail_policy": "on_change",
                    "comment_policy": "adaptive",
                    "relevance": RelevanceSnapshotV1(
                        keyword_pack_id=uuid4(),
                        keyword_pack_version=1,
                        config_version=1,
                        effective_keywords=("爱玛",),
                    ).model_dump(mode="json"),
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
    finally:
        session.close()

    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=500, body={"error": "fixture"}),
            ProviderTransportResponse(status_code=200, body=_search_response()),
            ProviderTransportResponse(status_code=200, body=_detail_response()),
        )
    )
    registry = create_collection_job_registry(
        runtime=platform_runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=lambda secret_ref: (
            SecretStr("fixture-secret")
            if secret_ref == provider_config.secret_ref
            else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
        ),
    )
    worker = create_job_worker(
        runtime=platform_runtime,
        registry=registry,
        worker_id="collection-retry-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True
    session = platform_runtime.database.new_session()
    try:
        after_first = (
            session.execute(select(jobs_table).where(jobs_table.c.id == job.id)).mappings().one()
        )
        run_after_first = session.execute(select(collection_runs_table)).mappings().one()
        scope_after_first = session.execute(select(collection_scopes_table)).mappings().one()
    finally:
        session.close()
    assert after_first["status"] == "queued"
    assert after_first["attempt"] == 1
    assert after_first["error_code"] == "http_500"
    assert run_after_first["status"] == "running"
    assert scope_after_first["status"] == "running"

    assert worker.run_once() is True
    assert worker.run_once() is False
    assert transport.call_count == 3

    session = platform_runtime.database.new_session()
    try:
        final_job = (
            session.execute(select(jobs_table).where(jobs_table.c.id == job.id)).mappings().one()
        )
        final_run = session.execute(select(collection_runs_table)).mappings().one()
        final_scope = session.execute(select(collection_scopes_table)).mappings().one()
        search_request = (
            session.execute(
                select(provider_requests_table).where(
                    provider_requests_table.c.operation == "search_notes"
                )
            )
            .mappings()
            .one()
        )
        attempts = (
            session.execute(
                select(provider_request_attempts_table)
                .where(
                    provider_request_attempts_table.c.provider_request_id == search_request["id"]
                )
                .order_by(provider_request_attempts_table.c.attempt_no)
            )
            .mappings()
            .all()
        )
        request_count = session.scalar(select(func.count()).select_from(provider_requests_table))
    finally:
        session.close()

    assert final_job["status"] == "succeeded"
    assert final_job["attempt"] == 2
    assert final_run["status"] == "succeeded"
    assert final_scope["status"] == "succeeded"
    assert request_count == 2
    assert len(attempts) == 2
    assert attempts[0]["attempt_no"] == 1
    assert attempts[0]["dispatch_status"] == "completed"
    assert attempts[0]["http_status"] == 500
    assert attempts[0]["error_code"] == "http_500"
    assert attempts[0]["raw_artifact_id"] is not None
    assert attempts[1]["attempt_no"] == 2
    assert attempts[1]["dispatch_status"] == "completed"
    assert attempts[1]["http_status"] == 200
    assert attempts[1]["error_code"] is None
    assert attempts[1]["raw_artifact_id"] is not None
