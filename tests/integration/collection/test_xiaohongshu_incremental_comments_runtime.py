"""xiaohongshu latest_v2 增量评论历史边界的 PostgreSQL/Fake Transport 纵切。"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

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
from aima_ugc.modules.content.tables import (
    comment_coverage_observations_table,
    comments_table,
    contents_table,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.modules.system.tables import provider_configs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import delete, insert, select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xiaohongshu")
_OBSERVED_AT = datetime(2026, 8, 18, 0, 20, tzinfo=UTC)
_CONTENT_EXTERNAL_ID = "note-fixture-1"
_KNOWN_COMMENT_ID = "xiaohongshu-comment-known-1"
_NEW_COMMENT_ID = "xiaohongshu-comment-new-2"


@dataclass
class _Context:
    fence: JobExecutionFence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


@pytest.fixture
def created_provider_config_ids() -> set[UUID]:
    """记录当前测试创建的 Provider Config，供失败场景的 Fixture teardown 清理。"""

    return set()


@pytest.fixture
def database_runtime(created_provider_config_ids: set[UUID]) -> Iterator[DatabaseRuntime]:
    """提供数据库 Runtime，并只清理当前测试自己创建的 Provider Config。"""

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
            if created_provider_config_ids:
                connection.execute(
                    delete(provider_configs_table).where(
                        provider_configs_table.c.id.in_(created_provider_config_ids)
                    )
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
    note["id"] = _CONTENT_EXTERNAL_ID
    note["comments_count"] = 12
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
    note["id"] = _CONTENT_EXTERNAL_ID
    note["comments_count"] = 12
    return body


def _root_template() -> dict[str, object]:
    body = _fixture("comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    comments = page["comments"]
    assert isinstance(comments, list) and comments
    root = comments[0]
    assert isinstance(root, dict)
    root = copy.deepcopy(root)
    root["note_id"] = _CONTENT_EXTERNAL_ID
    root["sub_comment_count"] = 0
    root["sub_comments"] = []
    return root


def _comments_page1() -> dict[str, object]:
    body = _fixture("comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)

    new_root = _root_template()
    new_root["id"] = _NEW_COMMENT_ID
    new_root["content"] = "本轮新增评论"
    known_root = _root_template()
    known_root["id"] = _KNOWN_COMMENT_ID
    known_root["content"] = "历史已知评论"

    page["comments"] = [new_root, known_root]
    page["comment_count_l1"] = 12
    page["has_more"] = True
    # 保留 Fixture 已验证 cursor/index/pageArea，并确保状态向前推进。
    return body


def _comments_page2_should_not_be_requested() -> dict[str, object]:
    body = _fixture("comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    root = _root_template()
    root["id"] = "xiaohongshu-comment-too-old"
    root["content"] = "如果请求到这一页说明增量停止失败"
    page["comments"] = [root]
    page["comment_count_l1"] = 12
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


def _seed_previous_content(runtime: DatabaseRuntime) -> UUID:
    content_id = uuid4()
    session = runtime.new_session()
    try:
        with session.begin():
            session.execute(
                insert(contents_table).values(
                    id=content_id,
                    platform="xiaohongshu",
                    external_content_id=_CONTENT_EXTERNAL_ID,
                    content_type="image",
                    first_seen_at=_OBSERVED_AT,
                    last_seen_at=_OBSERVED_AT,
                    current_version=1,
                    current_comment_count=10,
                    field_observed_at={},
                    updated_at=_OBSERVED_AT,
                )
            )
            session.execute(
                insert(comments_table).values(
                    id=uuid4(),
                    content_id=content_id,
                    external_comment_id=_KNOWN_COMMENT_ID,
                    root_comment_id=_KNOWN_COMMENT_ID,
                    parent_comment_id=None,
                    text="历史已知评论",
                    first_seen_at=_OBSERVED_AT,
                    last_seen_at=_OBSERVED_AT,
                    current_version=1,
                    current_reply_count=0,
                    field_observed_at={},
                    updated_at=_OBSERVED_AT,
                )
            )
    finally:
        session.close()
    return content_id


def test_xiaohongshu_incremental_comments_stop_after_safe_known_comment_boundary(
    database_runtime: DatabaseRuntime,
    created_provider_config_ids: set[UUID],
    tmp_path: Path,
) -> None:
    content_id = _seed_previous_content(database_runtime)

    session = database_runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub xiaohongshu Incremental Comments",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/xiaohongshu-incremental-comments",
                    enabled=True,
                )
            )
            created_provider_config_ids.add(provider_config.id)
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"xiaohongshu-incremental-comments:{uuid4()}",
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
                },
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
                worker_id="xiaohongshu-incremental-comments-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
    finally:
        session.close()

    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=_search_response()),
            ProviderTransportResponse(status_code=200, body=_detail_response()),
            ProviderTransportResponse(status_code=200, body=_comments_page1()),
            ProviderTransportResponse(
                status_code=200,
                body=_comments_page2_should_not_be_requested(),
            ),
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
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=fence, context=_Context(fence))

    assert result.outcome == "succeeded"
    assert transport.call_count == 3
    assert [request.path for request in transport.seen_requests] == [
        "/api/v1/xiaohongshu/app_v2/search_notes",
        "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
        "/api/v1/xiaohongshu/app_v2/get_note_comments",
    ]
    assert transport.seen_requests[-1].params["sort_strategy"] == "latest_v2"

    session = database_runtime.new_session()
    try:
        with session.begin():
            comment_ids = set(
                session.scalars(
                    select(comments_table.c.external_comment_id).where(
                        comments_table.c.content_id == content_id
                    )
                ).all()
            )
            coverage = (
                session.execute(
                    select(comment_coverage_observations_table)
                    .where(comment_coverage_observations_table.c.content_id == content_id)
                    .order_by(comment_coverage_observations_table.c.observed_at.desc())
                    .limit(1)
                )
                .mappings()
                .one()
            )
        assert _NEW_COMMENT_ID in comment_ids
        assert _KNOWN_COMMENT_ID in comment_ids
        assert "xiaohongshu-comment-too-old" not in comment_ids
        assert coverage["coverage"] == "partial"
        assert coverage["sort_mode"] == "latest"
        assert coverage["stop_reason"] == "known_comment_reached"
    finally:
        session.close()
