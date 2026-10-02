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
from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresCollectionContentStateReader,
)
from aima_ugc.adapters.persistence.postgres.collection_run_execution import (
    PostgresCollectionRunExecutionGateway,
)
from aima_ugc.adapters.persistence.postgres.content_coverage import PostgresContentCoverageReader
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.contracts.collection import CollectionDecisionPolicyV1
from aima_ugc.modules.collection.collection_run_executor import CollectionRunExecutor
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.providers import ProviderTransportResponse, RawArtifactService
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.extended_tables import comment_thread_coverage_observations_table
from aima_ugc.modules.content.tables import (
    comment_coverage_observations_table,
    comments_table,
    contents_table,
)
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.storage import ArtifactService
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import func, select

from tests.integration.stage3_brand_support import stage4_collection_config_snapshot

_FIXTURES = Path("tests/fixtures/providers/tikhub/xiaohongshu")
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
            "TRUNCATE TABLE collection_plans, jobs, artifacts, accounts RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE collection_plans, jobs, artifacts, accounts RESTART IDENTITY CASCADE"
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


def _comments_response(*, count: int, has_more: bool, start: int = 0) -> dict[str, object]:
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
        root["id"] = f"xiaohongshu-comment-{start + index + 1}"
        root["note_id"] = "note-fixture-1"
        root["sub_comment_count"] = 0
        root["sub_comments"] = []
        comments.append(root)
    page["comments"] = comments
    page["comment_count"] = count
    page["comment_count_l1"] = count
    page["has_more"] = has_more
    page["cursor"] = f"cursor-{start + count}" if has_more else "cursor-end"
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


def _prepare_run(runtime: DatabaseRuntime, *, comment_policy: str = "adaptive") -> _PreparedRun:
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
                    **stage4_collection_config_snapshot(runtime, alias="脱敏"),
                    "detail_policy": "on_change",
                    "schema_version": "collection-run-config.v4",
                    "plan_type": "tikhub",
                    "comment_policy": comment_policy,
                    "decision_policy": CollectionDecisionPolicyV1(
                        comment_mode=comment_policy
                    ).model_dump(mode="json"),
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
    comment_policy: str = "adaptive",
    expected_outcome: str = "succeeded",
) -> tuple[_PreparedRun, FakeProviderTransport]:
    prepared = _prepare_run(runtime, comment_policy=comment_policy)
    transport = FakeProviderTransport(responses)
    fence = JobExecutionFence(job_id=prepared.job_id, lease_token=prepared.lease_token)
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=runtime.new_session,
            raw_artifacts=_raw_service(runtime, tmp_path / "artifacts"),
            artifacts=ArtifactService(
                metadata=PostgresArtifactMetadataGateway(runtime.new_session),
                store=LocalArtifactStore(tmp_path / "artifacts"),
            ),
            artifact_store=LocalArtifactStore(tmp_path / "artifacts"),
            transport_factory=lambda _config: transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == prepared.provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=fence, context=_Context(fence))
    with runtime.new_session() as diagnostics:
        errors = diagnostics.execute(
            select(collection_scopes_table.c.stop_reason)
            .join(
                collection_runs_table,
                collection_scopes_table.c.run_id == collection_runs_table.c.id,
            )
            .where(collection_runs_table.c.job_id == prepared.job_id)
        ).all()
    assert result.outcome == expected_outcome, (errors, [r.path for r in transport.seen_requests])
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


def test_full_500_roots_crosses_sampling_limit_and_unchanged_next_run_skips_comments(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _, first = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=500)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=500)),
            *(
                ProviderTransportResponse(
                    status_code=200,
                    body=_comments_response(
                        count=100,
                        start=page * 100,
                        has_more=page < 4,
                    ),
                )
                for page in range(5)
            ),
        ),
    )
    assert first.call_count == 7
    with database_runtime.new_session() as session:
        coverage = session.execute(select(comment_coverage_observations_table)).mappings().one()
        content_id = session.scalar(select(contents_table.c.id))
        assert session.scalar(select(func.count()).select_from(comments_table)) == 500
        assert coverage["coverage"] == "complete"
        assert coverage["collected_count"] == coverage["target_count"] == 500
        assert PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=500
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(collection_runs_table)
                .where(collection_runs_table.c.status.in_(("queued", "running")))
            )
            == 0
        )
    # 没有full计划或活动v4 Run时，已完成的fetch_full审计本身仍必须阻止降级。
    with pytest.raises(RuntimeError, match="不能安全降级"):
        command.downgrade(Config("alembic.ini"), "20261001_0078")
    _, second = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=500)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=500)),
        ),
    )
    assert second.call_count == 2
    assert not any("get_note_comments" in request.path for request in second.seen_requests)
    with database_runtime.new_session() as session:
        assert PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=500
        )


def test_full_partial_same_count_is_refetched_and_adaptive_sample_is_not_complete(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=60)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=60)),
            ProviderTransportResponse(
                status_code=200, body=_comments_response(count=50, has_more=True)
            ),
        ),
    )
    with database_runtime.new_session() as session:
        content_id = session.scalar(select(contents_table.c.id))
        assert not PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=60
        )
    _, refill = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=60)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=60)),
            ProviderTransportResponse(
                status_code=200, body=_comments_response(count=60, has_more=False)
            ),
        ),
    )
    assert refill.call_count == 3
    with database_runtime.new_session() as session:
        assert PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=60
        )


def _root_page_with_replies(
    *, reply_count: int | None, include_new_root: bool = False
) -> dict[str, object]:
    body = _comments_response(count=2 if include_new_root else 1, has_more=include_new_root)
    page = body["data"]["data"]
    roots = page["comments"]
    if reply_count is None:
        roots[0].pop("sub_comment_count")
    else:
        roots[0]["sub_comment_count"] = reply_count
    if include_new_root:
        page["comments"] = list(reversed(roots))
    return body


def _reply_page(*, start: int, count: int, has_more: bool) -> dict[str, object]:
    body = _fixture("sub_comments_page1.sanitized.json")
    page = body["data"]["data"]
    template = page["comments"][0]
    replies = []
    for index in range(start, start + count):
        reply = deepcopy(template)
        reply["id"] = f"xiaohongshu-reply-{index}"
        reply["note_id"] = "note-fixture-1"
        reply["target_comment"]["id"] = "xiaohongshu-comment-1"
        replies.append(reply)
    page.update(comments=replies, has_more=has_more, cursor=f"reply-cursor-{start + count}")
    return body


@pytest.mark.parametrize("reply_count", [30, None])
def test_full_replies_cross_five_and_unknown_counts_continue_to_exhaustion(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    reply_count: int | None,
) -> None:
    _, transport = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=1)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=1)),
            ProviderTransportResponse(
                status_code=200, body=_root_page_with_replies(reply_count=reply_count)
            ),
            ProviderTransportResponse(
                status_code=200, body=_reply_page(start=0, count=15, has_more=True)
            ),
            ProviderTransportResponse(
                status_code=200, body=_reply_page(start=15, count=15, has_more=False)
            ),
        ),
    )
    assert transport.call_count == 5
    with database_runtime.new_session() as session:
        thread = (
            session.execute(select(comment_thread_coverage_observations_table)).mappings().one()
        )
        content_id = session.scalar(select(contents_table.c.id))
        assert thread["coverage"] == "complete"
        assert thread["captured_count"] == 30
        # Provider 可以只给根归属、不提供直接父节点；回复仍不能成为一级评论。
        session.execute(
            comments_table.update()
            .where(comments_table.c.root_comment_id.is_not(None))
            .values(parent_comment_id=None)
        )
        session.commit()
        assert (
            len(
                PostgresCollectionContentStateReader(
                    database_runtime.new_session
                ).known_root_comment_ids(content_id)
            )
            == 1
        )
        assert PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=1
        )
    _, unchanged = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=1)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=1)),
        ),
    )
    assert unchanged.call_count == 2
    assert not any("comments" in request.path for request in unchanged.seen_requests)
    if reply_count is None:
        return
    # 增加一个新根，整页中的已完整旧线程不得再付费；到稳定历史边界后仍保持完整。
    _, incremental = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=(
            ProviderTransportResponse(status_code=200, body=_search_response(comment_count=2)),
            ProviderTransportResponse(status_code=200, body=_detail_response(comment_count=2)),
            ProviderTransportResponse(
                status_code=200, body=_root_page_with_replies(reply_count=30, include_new_root=True)
            ),
        ),
    )
    assert incremental.call_count == 3
    assert not any("sub_comments" in request.path for request in incremental.seen_requests)
    with database_runtime.new_session() as session:
        root = (
            session.execute(
                select(comment_coverage_observations_table).where(
                    comment_coverage_observations_table.c.stop_reason == "known_comment_reached",
                )
            )
            .mappings()
            .one()
        )
        assert root["coverage"] == "complete"
        assert root["collected_count"] == 2
        assert PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=2
        )


@pytest.mark.parametrize("boundary", ["root_limit", "reply_limit", "stalled"])
def test_full_safety_boundary_preserves_partial_and_stop_reason(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    monkeypatch,
    boundary: str,
) -> None:
    import aima_ugc.bootstrap.collection_scope as scope_runtime

    assert scope_runtime.MAX_COMMENT_PAGES == scope_runtime.MAX_SUB_COMMENT_PAGES == 100
    # 缩短本场景循环，不改变生产上限；真实分页、摄取和 Coverage 仍走生产入口。
    monkeypatch.setattr(scope_runtime, "MAX_COMMENT_PAGES", 2)
    monkeypatch.setattr(scope_runtime, "MAX_SUB_COMMENT_PAGES", 2)
    count = 1 if boundary == "reply_limit" else 300
    pages = (
        [
            _root_page_with_replies(reply_count=30),
            _reply_page(start=0, count=15, has_more=True),
            _reply_page(start=15, count=15, has_more=True),
        ]
        if boundary == "reply_limit"
        else [
            _comments_response(count=1, has_more=True),
            _comments_response(count=1, has_more=True, start=0 if boundary == "stalled" else 1),
        ]
    )
    prepared, _ = _execute(
        runtime=database_runtime,
        tmp_path=tmp_path,
        comment_policy="full",
        responses=tuple(
            ProviderTransportResponse(status_code=200, body=body)
            for body in [
                _search_response(comment_count=count),
                _detail_response(comment_count=count),
                *pages,
            ]
        ),
    )
    with database_runtime.new_session() as session:
        assert (
            session.scalar(
                select(collection_runs_table.c.status).where(
                    collection_runs_table.c.job_id == prepared.job_id
                )
            )
            == "partial_success"
        )
        content_id = session.scalar(select(contents_table.c.id))
        assert content_id is not None
        assert not PostgresContentCoverageReader(session).full_capture_complete(
            content_id, comment_count=count
        )
        table = (
            comment_thread_coverage_observations_table
            if boundary == "reply_limit"
            else comment_coverage_observations_table
        )
        coverage = (
            session.execute(select(table).order_by(table.c.observed_at.desc())).mappings().first()
        )
        assert coverage is not None and coverage["coverage"] == "partial"
        assert coverage["stop_reason"] == (
            "pagination_not_advanced" if boundary == "stalled" else "page_limit"
        )
