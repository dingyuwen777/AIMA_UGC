"""Stage 7 concrete Collection Scope Runtime 的 PostgreSQL/Fake Transport 纵切。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataGateway,
)
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse, RawArtifactService
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactService
from aima_ugc.platform.storage.tables import artifacts_table
from pydantic import SecretStr
from sqlalchemy import func, select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xhs")
_OBSERVED_AT = datetime(2026, 8, 17, 4, 0, tzinfo=UTC)


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
    provider = body["data"]
    assert isinstance(provider, dict)
    page = provider["data"]
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


def test_scope_runtime_dispatches_search_and_detail_then_ingests_canonical_content(
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
                    display_name="TikHub Scope Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/scope-runtime",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"scope-runtime:{uuid4()}",
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
                    "platforms": [
                        {
                            "operations": "xhs",
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
                worker_id="scope-runtime-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
    finally:
        session.close()

    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=_search_response()),
            ProviderTransportResponse(status_code=200, body=_detail_response()),
        )
    )
    fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    scope_executor = TikHubCollectionScopeExecutor(
        session_factory=database_runtime.new_session,
        raw_artifacts=_raw_service(database_runtime, tmp_path / "artifacts"),
        transport_factory=lambda _config: transport,
        secret_resolver=lambda secret_ref: (
            SecretStr("fixture-secret")
            if secret_ref == provider_config.secret_ref
            else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
        ),
        observed_at=lambda: _OBSERVED_AT,
    )
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=scope_executor,
    ).execute(fence=fence, context=_Context(fence))

    assert result.outcome == "succeeded"
    assert transport.call_count == 2
    assert [request.path for request in transport.seen_requests] == [
        "/api/v1/xiaohongshu/app_v2/search_notes",
        "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
    ]
    assert all(request.credential is None for request in transport.seen_requests)

    session = database_runtime.new_session()
    try:
        with session.begin():
            assert session.scalar(select(func.count()).select_from(provider_requests_table)) == 2
            assert (
                session.scalar(select(func.count()).select_from(provider_request_attempts_table))
                == 2
            )
            assert session.scalar(select(func.count()).select_from(artifacts_table)) == 2
            content = session.execute(select(contents_table)).mappings().one()
        assert content["operations"] == "xhs"
        assert content["external_content_id"] == "note-fixture-1"
        assert content["title"] == "脱敏图文标题"
        assert content["current_comment_count"] == 0
    finally:
        session.close()
