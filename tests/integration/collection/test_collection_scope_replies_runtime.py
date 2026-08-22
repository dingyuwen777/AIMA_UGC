"""Stage 7 Scope Runtime 二级回复正式链的 PostgreSQL/Fake Transport 纵切。"""

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
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse, RawArtifactService
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
)
from aima_ugc.modules.content.extended_tables import (
    comment_thread_coverage_observations_table,
)
from aima_ugc.modules.content.tables import comments_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xiaohongshu")
_OBSERVED_AT = datetime(2026, 8, 17, 5, 0, tzinfo=UTC)


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


def _sub_comments_response(
    *,
    has_more: bool = False,
    note_id: str = "note-fixture-1",
    empty: bool = False,
) -> dict[str, object]:
    body = _fixture("sub_comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    replies = page["comments"]
    assert isinstance(replies, list) and replies
    reply = replies[0]
    assert isinstance(reply, dict)
    reply["note_id"] = note_id
    page["comments"] = [] if empty else [reply]
    page["has_more"] = has_more
    page["cursor"] = "cursor-next" if has_more else "cursor-end"
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


def _execute_reply_case(
    *,
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    sub_comments: dict[str, object],
    decision_policy: dict[str, object] | None = None,
):
    session = database_runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Scope Replies Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref=f"providers/tikhub/test/scope-replies-runtime-{uuid4()}",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"scope-replies-runtime:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            snapshot: dict[str, object] = {
                "schema_version": "collection-run-config.v1",
                "relevance": {
                    "schema_version": "relevance-snapshot.v1",
                    "keyword_pack_id": str(uuid4()),
                    "keyword_pack_version": 1,
                    "config_version": 1,
                    "effective_keywords": ["脱敏"],
                },
                "detail_policy": "on_change",
                "comment_policy": "adaptive",
                "platforms": [
                    {
                        "platform": "xiaohongshu",
                        "provider_config_id": str(provider_config.id),
                        "config": {
                            "sort_mode": "latest",
                            "published_within": "1d",
                            "content_type": "all",
                        },
                    }
                ],
            }
            if decision_policy is not None:
                snapshot["decision_policy"] = decision_policy
            CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot=snapshot,
                scopes=(
                    CollectionScopeDefinition(
                        platform="xiaohongshu",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id=f"scope-replies-runtime-worker-{uuid4()}",
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
            ProviderTransportResponse(status_code=200, body=sub_comments),
        )
    )
    fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=database_runtime.new_session,
            raw_artifacts=_raw_service(database_runtime, tmp_path / f"artifacts-{uuid4()}"),
            transport_factory=lambda _config: transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=fence, context=_Context(fence))
    return result, transport, job.id


def test_scope_runtime_reply_target_is_partial_when_provider_has_more(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    result, transport, job_id = _execute_reply_case(
        database_runtime=database_runtime,
        tmp_path=tmp_path,
        sub_comments=_sub_comments_response(has_more=True),
        decision_policy={"reply_target_per_root": 1},
    )
    assert result.outcome == "succeeded"
    assert transport.call_count == 4
    assert all(request.credential is None for request in transport.seen_requests)
    session = database_runtime.new_session()
    try:
        with session.begin():
            comments = {
                row["external_comment_id"]: row
                for row in session.execute(select(comments_table)).mappings().all()
            }
            run_comment_count = session.scalar(
                select(collection_runs_table.c.comment_count).where(
                    collection_runs_table.c.job_id == job_id
                )
            )
            coverage = (
                session.execute(select(comment_thread_coverage_observations_table)).mappings().one()
            )
        assert set(comments) == {"xiaohongshu-comment-root-1", "xiaohongshu-comment-reply-2"}
        assert run_comment_count == 2
        assert coverage["coverage"] == "partial"
        assert coverage["reported_total"] == 1
        assert coverage["captured_count"] == 1
        assert coverage["stop_reason"] == "target_reached"
    finally:
        session.close()


def test_sub_comments_empty_page_overrides_stale_root_reply_count(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    result, transport, _job_id = _execute_reply_case(
        database_runtime=database_runtime,
        tmp_path=tmp_path,
        sub_comments=_sub_comments_response(empty=True),
    )
    assert result.outcome == "succeeded"
    assert transport.call_count == 4
    session = database_runtime.new_session()
    try:
        with session.begin():
            coverage = (
                session.execute(select(comment_thread_coverage_observations_table)).mappings().one()
            )
            comment_ids = set(session.scalars(select(comments_table.c.external_comment_id)))
        assert comment_ids == {"xiaohongshu-comment-root-1"}
        assert coverage["coverage"] == "complete"
        assert coverage["reported_total"] == 0
        assert coverage["captured_count"] == 0
        assert coverage["stop_reason"] == "empty_page"
    finally:
        session.close()


def test_reply_content_identity_mismatch_records_invalid_candidate(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    result, transport, _job_id = _execute_reply_case(
        database_runtime=database_runtime,
        tmp_path=tmp_path,
        sub_comments=_sub_comments_response(note_id="different-note"),
    )
    assert result.outcome == "failed"
    assert transport.call_count == 4
    session = database_runtime.new_session()
    try:
        with session.begin():
            rows = session.execute(
                select(
                    collection_candidate_ingestions_table.c.result,
                    collection_candidate_ingestions_table.c.error_code,
                )
                .select_from(
                    collection_candidate_ingestions_table.join(
                        collection_candidates_table,
                        collection_candidate_ingestions_table.c.candidate_id
                        == collection_candidates_table.c.id,
                    )
                )
                .where(collection_candidates_table.c.item_kind == "comment")
            ).all()
        assert any(
            row.result == "invalid" and row.error_code == "reply_content_identity_mismatch"
            for row in rows
        )
    finally:
        session.close()
