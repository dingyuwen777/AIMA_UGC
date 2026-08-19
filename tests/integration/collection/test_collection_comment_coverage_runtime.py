"""Stage 7 评论详情后决策、软目标与 Coverage 的 PostgreSQL 纵切。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
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
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import (
    comment_coverage_observations_table,
    comments_table,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactService
from pydantic import SecretStr
from sqlalchemy import func, select

_FIXTURES = Path("tests/fixtures/providers/tikhub/xhs")
_OBSERVED_AT = datetime(2026, 8, 17, 5, 0, tzinfo=UTC)


@dataclass
class _Context:
    fence: JobExecutionFence

    def heartbeat(self, *, progress: int) -> None:
        assert 0 <= progress <= 100

    def cancel_requested(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class _PreparedRun:
    job_id: UUID
    lease_token: str
    provider_config: ProviderConfig


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


def _search_response(*, comment_count: int | None) -> dict[str, object]:
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
    if comment_count is None:
        note.pop("comments_count", None)
    else:
        note["comments_count"] = comment_count
    page["items"] = [first]
    page["has_more"] = False
    return body


def _detail_response(*, comment_count: int) -> dict[str, object]:
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
    note["comments_count"] = comment_count
    return body


def _comments_response(*, count: int, has_more: bool) -> dict[str, object]:
    body = _fixture("comments_page1.sanitized.json")
    outer = body["data"]
    assert isinstance(outer, dict)
    page = outer["data"]
    assert isinstance(page, dict)
    roots = page["comments"]
    assert isinstance(roots, list) and roots
    template = roots[0]
    assert isinstance(template, dict)
    comments: list[dict[str, object]] = []
    for index in range(count):
        root = deepcopy(template)
        root["id"] = f"xhs-comment-{index + 1}"
        root["note_id"] = "note-fixture-1"
        root["sub_comment_count"] = 0
        root["sub_comments"] = []
        comments.append(root)
    page["comments"] = comments
    page["comment_count"] = count
    page["comment_count_l1"] = count
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


def _prepare_run(runtime: DatabaseRuntime) -> _PreparedRun:
    session = runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Coverage Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref="providers/tikhub/test/coverage-runtime",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"coverage-runtime:{uuid4()}",
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
                worker_id="coverage-runtime-worker",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
        return _PreparedRun(job.id, claimed.lease_token, provider_config)
    finally:
        session.close()


def _execute(
    *,
    runtime: DatabaseRuntime,
    tmp_path: Path,
    responses: tuple[ProviderTransportResponse, ...],
) -> tuple[_PreparedRun, FakeProviderTransport]:
    prepared = _prepare_run(runtime)
    transport = FakeProviderTransport(responses)
    fence = JobExecutionFence(job_id=prepared.job_id, lease_token=prepared.lease_token)
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=runtime.new_session,
            raw_artifacts=_raw_service(runtime, tmp_path / "artifacts"),
            transport_factory=lambda _config: transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == prepared.provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=fence, context=_Context(fence))
    assert result.outcome == "succeeded"
    return prepared, transport


def test_unknown_search_comment_count_is_redecided_after_detail_and_records_complete_coverage(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    prepared, transport = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        responses=(
            ProviderTransportResponse(
                status_code=200,
                body=_search_response(comment_count=None),
            ),
            ProviderTransportResponse(
                status_code=200,
                body=_detail_response(comment_count=1),
            ),
            ProviderTransportResponse(
                status_code=200,
                body=_comments_response(count=1, has_more=False),
            ),
        ),
    )

    assert transport.call_count == 3
    assert [request.path for request in transport.seen_requests] == [
        "/api/v1/xiaohongshu/app_v2/search_notes",
        "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
        "/api/v1/xiaohongshu/app_v2/get_note_comments",
    ]
    session = database_runtime.new_session()
    try:
        coverage = session.execute(select(comment_coverage_observations_table)).mappings().one()
        comment_completed_at = session.scalar(
            select(provider_request_attempts_table.c.completed_at)
            .select_from(
                provider_request_attempts_table.join(
                    provider_requests_table,
                    provider_request_attempts_table.c.provider_request_id
                    == provider_requests_table.c.id,
                )
            )
            .where(provider_requests_table.c.operation == "get_note_comments")
        )
    finally:
        session.close()
    assert coverage["coverage"] == "complete"
    assert coverage["reported_total"] == 1
    assert coverage["collected_count"] == 1
    assert coverage["sample_mode"] == "full"
    assert coverage["sort_mode"] == "latest"
    assert coverage["target_count"] == 1
    assert coverage["stop_reason"] == "provider_exhausted"
    assert comment_completed_at is not None
    assert coverage["observed_at"] == comment_completed_at
    assert prepared.job_id is not None


def test_adaptive_target_keeps_whole_paid_page_and_records_partial_coverage(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _prepared, transport = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        responses=(
            ProviderTransportResponse(
                status_code=200,
                body=_search_response(comment_count=51),
            ),
            ProviderTransportResponse(
                status_code=200,
                body=_detail_response(comment_count=51),
            ),
            ProviderTransportResponse(
                status_code=200,
                body=_comments_response(count=51, has_more=True),
            ),
        ),
    )

    assert transport.call_count == 3
    session = database_runtime.new_session()
    try:
        comment_count = session.scalar(select(func.count()).select_from(comments_table))
        coverage = session.execute(select(comment_coverage_observations_table)).mappings().one()
    finally:
        session.close()
    assert comment_count == 51
    assert coverage["coverage"] == "partial"
    assert coverage["reported_total"] == 51
    assert coverage["collected_count"] == 51
    assert coverage["sample_mode"] == "adaptive_sample"
    assert coverage["sort_mode"] == "latest"
    assert coverage["target_count"] == 50
    assert coverage["stop_reason"] == "target_reached"


def test_comment_response_zero_overrides_older_detail_count(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _prepared, transport = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        responses=(
            ProviderTransportResponse(
                status_code=200,
                body=_search_response(comment_count=1),
            ),
            ProviderTransportResponse(
                status_code=200,
                body=_detail_response(comment_count=1),
            ),
            ProviderTransportResponse(
                status_code=200,
                body=_comments_response(count=0, has_more=False),
            ),
        ),
    )

    assert transport.call_count == 3
    session = database_runtime.new_session()
    try:
        coverage = session.execute(select(comment_coverage_observations_table)).mappings().one()
    finally:
        session.close()
    assert coverage["coverage"] == "complete"
    assert coverage["reported_total"] == 0
    assert coverage["collected_count"] == 0
    assert coverage["target_count"] == 1
    assert coverage["stop_reason"] == "empty_page"
