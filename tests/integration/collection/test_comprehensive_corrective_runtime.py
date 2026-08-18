"""Stage 1-7 全面整改的 PostgreSQL/Fake Transport 生产纵切。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
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
from aima_ugc.modules.collection.corrective_tables import collection_content_actions_table
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse, RawArtifactService
from aima_ugc.modules.content.extended_tables import (
    comment_thread_coverage_observations_table,
    content_locations_table,
    content_media_table,
    content_topics_table,
)
from aima_ugc.modules.content.tables import comment_coverage_observations_table, comments_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import func, select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xhs")


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
    page["items"] = [items[0]]
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
    note["comments_count"] = 1
    note["topics"] = [{"id": "topic-aima", "name": "爱玛"}]
    note["ip_location"] = "北京"
    note["images_list"] = [
        {
            "id": "image-aima-1",
            "url": "https://example.invalid/image-aima-1.jpg",
            "width": 1080,
            "height": 720,
            "index": 0,
        }
    ]
    return body


def _comments_response() -> dict[str, object]:
    body = _fixture("comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    comments = page["comments"]
    assert isinstance(comments, list) and comments
    root = comments[0]
    assert isinstance(root, dict)
    root["note_id"] = "note-fixture-1"
    root["sub_comment_count"] = 1
    root["sub_comments"] = []
    page["comments"] = [root]
    page["has_more"] = False
    return body


def _sub_comments_response() -> dict[str, object]:
    body = _fixture("sub_comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    replies = page["comments"]
    assert isinstance(replies, list) and replies
    reply = replies[0]
    assert isinstance(reply, dict)
    reply["note_id"] = "note-fixture-1"
    page["comments"] = [reply]
    page["has_more"] = False
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


def test_scope_persists_durable_actions_extensions_and_thread_coverage(
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
                    display_name="TikHub comprehensive corrective runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/comprehensive-corrective",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"comprehensive-corrective:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=3600,
            )
            CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={
                    "schema_version": "collection-run-config.v1",
                    "detail_policy": "on_change",
                    "comment_policy": "adaptive",
                    "decision_policy": {
                        "comments_enabled": True,
                        "full_fetch_threshold": 50,
                        "sample_target": 50,
                        "reply_target_per_root": 5,
                    },
                    "platforms": [
                        {
                            "platform": "xhs",
                            "provider_config_id": str(provider_config.id),
                            "config": {
                                "sort_mode": "latest",
                                "published_within": "1d",
                                "content_type": "image",
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
                worker_id="comprehensive-corrective-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
    finally:
        session.close()

    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=_search_response()),
            ProviderTransportResponse(status_code=200, body=_detail_response()),
            ProviderTransportResponse(status_code=200, body=_comments_response()),
            ProviderTransportResponse(status_code=200, body=_sub_comments_response()),
        )
    )
    fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=database_runtime.new_session,
            raw_artifacts=_raw_service(database_runtime, tmp_path / "artifacts"),
            transport_factory=lambda _config: transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
        ),
    ).execute(fence=fence, context=_Context(fence))

    assert result.outcome == "succeeded"
    assert transport.call_count == 4

    session = database_runtime.new_session()
    try:
        with session.begin():
            action = session.execute(select(collection_content_actions_table)).mappings().one()
            assert action["detail_completed"] is True
            assert action["comments_completed"] is True
            assert session.scalar(select(func.count()).select_from(content_media_table)) == 1
            assert session.scalar(select(func.count()).select_from(content_topics_table)) == 1
            assert session.scalar(select(func.count()).select_from(content_locations_table)) == 1

            comments = session.execute(select(comments_table)).mappings().all()
            assert {row["external_comment_id"] for row in comments} == {
                "xhs-comment-root-1",
                "xhs-comment-reply-2",
            }

            root_coverage = (
                session.execute(select(comment_coverage_observations_table)).mappings().one()
            )
            assert root_coverage["coverage"] == "complete"
            assert root_coverage["reported_total"] == 1
            # 内容级 Coverage 使用一级评论口径；二级回复由线程 Coverage 单独解释。
            assert root_coverage["collected_count"] == 1

            thread_coverage = (
                session.execute(select(comment_thread_coverage_observations_table)).mappings().one()
            )
            assert thread_coverage["root_comment_id"] == "xhs-comment-root-1"
            assert thread_coverage["coverage"] == "complete"
            assert thread_coverage["reported_total"] == 1
            assert thread_coverage["captured_count"] == 1
    finally:
        session.close()
