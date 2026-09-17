"""Stage 6 小红书 Raw → Candidate → Canonical → PostgreSQL 纵切。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.candidates import PostgresCandidateRepository
from aima_ugc.adapters.persistence.postgres.content import PostgresContentRepository
from aima_ugc.adapters.persistence.postgres.content_queries import (
    PostgresContentQueryRepository,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XiaohongshuMappingContext,
    map_comment,
    map_content,
)
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import extract_search_items
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.contracts.http import ContentCommentListQuery
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.candidates import CandidateIngestionService
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.content_cursor import (
    ContentCursorPosition,
    InvalidContentCursor,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_metric_observations_table,
    comment_versions_table,
    comments_table,
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import DBAPIError

_FIXTURE = Path("tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json")
OBSERVED_AT = datetime(2026, 8, 5, 10, 0, 12, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SourceChain:
    run_id: UUID
    scope_id: UUID
    request_id: UUID
    attempt_id: UUID
    artifact_id: UUID | None


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


def _raw_fixture() -> dict[str, object]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _insert_source_chain(
    session,
    *,
    operation: str,
    source_value: str,
    completed: bool = True,
) -> SourceChain:
    now = OBSERVED_AT
    job_id = uuid4()
    run_id = uuid4()
    scope_id = uuid4()
    request_id = uuid4()
    attempt_id = uuid4()
    artifact_id = uuid4() if completed else None

    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type="collection.run.v1",
            payload_version="collection.run.v1",
            payload={"schema_version": "collection.run.v1"},
            status="queued",
            internal_idempotency_key=f"stage6:{job_id}",
            priority=10,
            attempt=0,
            max_attempts=2,
            timeout_seconds=300,
            progress=0,
            available_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        insert(collection_runs_table).values(
            id=run_id,
            job_id=job_id,
            trigger_type="backfill",
            config_snapshot={"platforms": ["xiaohongshu"]},
            status="queued",
            created_at=now,
        )
    )
    session.execute(
        insert(collection_scopes_table).values(
            id=scope_id,
            run_id=run_id,
            platform="xiaohongshu",
            source_type="keyword_search",
            source_value=source_value,
            operation_group=("content_discovery" if operation == "search_notes" else "comments"),
            status="running",
        )
    )
    session.execute(
        insert(provider_requests_table).values(
            id=request_id,
            scope_id=scope_id,
            provider="tikhub",
            operation=operation,
            request_fingerprint=("1" if operation == "search_notes" else "2") * 64,
            request_params={"source": source_value},
            pagination_input={},
            status="completed" if completed else "dispatching",
            attempt_count=1,
            created_at=now,
            completed_at=now + timedelta(seconds=1) if completed else None,
        )
    )
    if artifact_id is not None:
        session.execute(
            insert(artifacts_table).values(
                id=artifact_id,
                kind="provider-raw",
                storage_backend="local",
                storage_key=f"raw/test/{artifact_id}.json.gz",
                content_type="application/json",
                encoding="gzip",
                sha256="a" * 64,
                byte_size=1,
                retention_class="raw",
                storage_status="linked",
                created_at=now,
                stored_at=now,
                linked_at=now + timedelta(seconds=1),
            )
        )
    session.execute(
        insert(provider_request_attempts_table).values(
            id=attempt_id,
            provider_request_id=request_id,
            attempt_no=1,
            dispatch_status="completed" if completed else "dispatching",
            dispatch_started_at=now,
            completed_at=now + timedelta(seconds=1) if completed else None,
            http_status=200 if completed else None,
            raw_artifact_id=artifact_id,
            billing_status="not_billable",
            created_at=now,
        )
    )
    return SourceChain(run_id, scope_id, request_id, attempt_id, artifact_id)


def _mapping_context(chain: SourceChain, *, operation: str) -> XiaohongshuMappingContext:
    assert chain.artifact_id is not None
    return XiaohongshuMappingContext(
        provider_request_id=str(chain.request_id),
        provider_attempt_id=str(chain.attempt_id),
        raw_artifact_id=chain.artifact_id,
        operation=operation,
        source_type="keyword_search",
        source_value="爱玛",
        observed_at=OBSERVED_AT,
    )


def test_real_search_fixture_ingests_content_and_candidate_lineage(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛",
            )
            candidate_service = CandidateIngestionService(PostgresCandidateRepository(session))
            content_service = ContentIngestionService(PostgresContentRepository(session))
            raw_item = extract_search_items(_raw_fixture())[0]
            candidate = candidate_service.discover(
                provider_request_attempt_id=chain.attempt_id,
                item_kind="content",
                external_item_id="note-fixture-1",
                item_locator="note:note-fixture-1",
                discovered_at=OBSERVED_AT,
            )
            canonical = map_content(
                raw_item,
                _mapping_context(chain, operation="search_notes"),
                item_locator=candidate.item_locator,
            )
            result = content_service.ingest_content(canonical)
            candidate_service.record_ingestion(
                candidate_id=candidate.id,
                canonical=canonical,
                target_id=result.target_id,
                result="ingested",
            )

        content_row = (
            session.execute(select(contents_table).where(contents_table.c.id == result.target_id))
            .mappings()
            .one()
        )
        assert content_row["platform"] == "xiaohongshu"
        assert content_row["external_content_id"] == "note-fixture-1"
        assert content_row["title"] == "脱敏标题 A"
        assert content_row["current_comment_count"] == 1
        assert content_row["current_favorite_count"] == 2
        assert content_row["current_share_count"] == 3
        assert session.execute(
            select(content_versions_table.c.version_no).where(
                content_versions_table.c.content_id == result.target_id
            )
        ).scalars().all() == [1]
        assert session.execute(
            select(content_metric_observations_table.c.reason).where(
                content_metric_observations_table.c.content_id == result.target_id
            )
        ).scalars().all() == ["initial"]

        lineage = session.execute(
            select(
                collection_candidates_table.c.item_locator,
                provider_request_attempts_table.c.id,
                provider_requests_table.c.id,
                collection_scopes_table.c.id,
                collection_runs_table.c.id,
                artifacts_table.c.id,
            )
            .join(
                provider_request_attempts_table,
                provider_request_attempts_table.c.id
                == collection_candidates_table.c.provider_request_attempt_id,
            )
            .join(
                provider_requests_table,
                provider_requests_table.c.id
                == provider_request_attempts_table.c.provider_request_id,
            )
            .join(
                collection_scopes_table,
                collection_scopes_table.c.id == provider_requests_table.c.scope_id,
            )
            .join(
                collection_runs_table,
                collection_runs_table.c.id == collection_scopes_table.c.run_id,
            )
            .join(
                artifacts_table,
                artifacts_table.c.id == provider_request_attempts_table.c.raw_artifact_id,
            )
            .where(collection_candidates_table.c.id == candidate.id)
        ).one()
        assert lineage == (
            "note:note-fixture-1",
            chain.attempt_id,
            chain.request_id,
            chain.scope_id,
            chain.run_id,
            chain.artifact_id,
        )
    finally:
        session.rollback()
        session.close()


def test_postgres_ingestion_preserves_sparse_fields_a_b_a_metrics_and_comment_tree(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            service = ContentIngestionService(PostgresContentRepository(session))
            base = {
                "id": "note-history",
                "type": "normal",
                "desc": "正文必须保留",
                "liked_count": 10,
            }

            first_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛-A",
            )
            first = service.ingest_content(
                map_content(
                    {**base, "title": "A"},
                    _mapping_context(first_chain, operation="search_notes"),
                    item_locator="note:note-history",
                )
            )

            second_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛-B",
            )
            service.ingest_content(
                map_content(
                    {**base, "title": "B", "liked_count": 20},
                    _mapping_context(second_chain, operation="search_notes"),
                    item_locator="note:note-history",
                )
            )

            third_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛-A2",
            )
            service.ingest_content(
                map_content(
                    {**base, "title": "A", "liked_count": 8},
                    _mapping_context(third_chain, operation="search_notes"),
                    item_locator="note:note-history",
                )
            )

            checkpoint_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛-checkpoint",
            )
            checkpoint_context = replace(
                _mapping_context(checkpoint_chain, operation="search_notes"),
                observed_at=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            )
            sparse = map_content(
                {"id": "note-history", "type": "normal", "title": "A", "liked_count": 8},
                checkpoint_context,
                item_locator="note:note-history",
            )
            service.ingest_content(sparse)
            service.ingest_content(sparse)

            comment_chain = _insert_source_chain(
                session,
                operation="get_note_comments",
                source_value="note-history",
            )
            comment = map_comment(
                {
                    "id": "comment-root",
                    "note_id": "note-history",
                    "content": "一级评论",
                    "like_count": 2,
                    "sub_comment_count": 1,
                },
                _mapping_context(comment_chain, operation="get_note_comments"),
                item_locator="comment:comment-root",
                is_root=True,
            )
            comment_result = service.ingest_comment(comment)

        current = (
            session.execute(select(contents_table).where(contents_table.c.id == first.target_id))
            .mappings()
            .one()
        )
        assert current["title"] == "A"
        assert current["text"] == "正文必须保留"
        assert current["current_like_count"] == 8
        assert current["current_version"] == 3
        assert session.execute(
            select(content_versions_table.c.title)
            .where(content_versions_table.c.content_id == first.target_id)
            .order_by(content_versions_table.c.version_no)
        ).scalars().all() == ["A", "B", "A"]
        metric_rows = session.execute(
            select(
                content_metric_observations_table.c.like_count,
                content_metric_observations_table.c.reason,
            )
            .where(content_metric_observations_table.c.content_id == first.target_id)
            .order_by(content_metric_observations_table.c.observed_at)
        ).all()
        assert (8, "changed") in metric_rows
        assert [reason for _, reason in metric_rows].count("daily_checkpoint") == 1

        comment_row = (
            session.execute(
                select(comments_table).where(comments_table.c.id == comment_result.target_id)
            )
            .mappings()
            .one()
        )
        assert comment_row["content_id"] == first.target_id
        assert comment_row["root_comment_id"] == "comment-root"
        assert comment_row["parent_comment_id"] is None
        assert session.execute(
            select(comment_versions_table.c.version_no).where(
                comment_versions_table.c.comment_id == comment_result.target_id
            )
        ).scalars().all() == [1]
        assert session.execute(
            select(comment_metric_observations_table.c.reason).where(
                comment_metric_observations_table.c.comment_id == comment_result.target_id
            )
        ).scalars().all() == ["initial"]
    finally:
        session.rollback()
        session.close()


def test_raw_replay_and_sparse_author_do_not_duplicate_or_clear_history(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            first_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛",
            )
            service = ContentIngestionService(PostgresContentRepository(session))
            full = map_content(
                {
                    "id": "note-replay",
                    "type": "normal",
                    "title": "稳定标题",
                    "liked_count": 10,
                    "user": {
                        "userid": "user-replay",
                        "nickname": "完整昵称",
                        "red_official_verified": True,
                    },
                },
                _mapping_context(first_chain, operation="search_notes"),
                item_locator="note:note-replay",
            )
            first = service.ingest_content(full)
            service.ingest_content(full)

            second_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛-补回",
            )
            sparse_author = map_content(
                {
                    "id": "note-replay",
                    "type": "normal",
                    "title": "稳定标题",
                    "liked_count": 10,
                    "user": {"userid": "user-replay"},
                },
                _mapping_context(second_chain, operation="search_notes"),
                item_locator="note:note-replay",
            )
            service.ingest_content(sparse_author)

        version_ids = (
            session.execute(
                select(content_versions_table.c.id).where(
                    content_versions_table.c.content_id == first.target_id
                )
            )
            .scalars()
            .all()
        )
        metric_ids = (
            session.execute(
                select(content_metric_observations_table.c.id).where(
                    content_metric_observations_table.c.content_id == first.target_id
                )
            )
            .scalars()
            .all()
        )
        assert len(version_ids) == 1
        assert len(metric_ids) == 1
        account = (
            session.execute(
                select(accounts_table).where(
                    accounts_table.c.platform == "xiaohongshu",
                    accounts_table.c.external_account_id == "user-replay",
                )
            )
            .mappings()
            .one()
        )
        assert account["display_name"] == "完整昵称"
        assert account["verified"] is True
    finally:
        session.rollback()
        session.close()


def test_comment_author_converges_by_existing_alternate_stable_id(
    database_runtime: DatabaseRuntime,
) -> None:
    """主 ID 漂移但 red_id 一致时，评论作者应复用既有平台账号。"""
    session = database_runtime.new_session()
    try:
        with session.begin():
            service = ContentIngestionService(PostgresContentRepository(session))
            content_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛",
            )
            content = service.ingest_content(
                map_content(
                    {
                        "id": "note-author-convergence",
                        "type": "normal",
                        "user": {
                            "userid": "historical-user-id",
                            "red_id": "stable-red-id",
                            "nickname": "同一作者",
                        },
                    },
                    _mapping_context(content_chain, operation="search_notes"),
                    item_locator="note:note-author-convergence",
                )
            )
            original_author_id = session.scalar(
                select(contents_table.c.author_account_id).where(
                    contents_table.c.id == content.target_id
                )
            )
            assert original_author_id is not None

            comment_chain = _insert_source_chain(
                session,
                operation="get_note_comments",
                source_value="note-author-convergence",
            )
            comment = service.ingest_comment(
                map_comment(
                    {
                        "id": "comment-author-convergence",
                        "note_id": "note-author-convergence",
                        "content": "评论",
                        "user": {
                            "userid": "current-provider-user-id",
                            "red_id": "stable-red-id",
                            "nickname": "同一作者",
                        },
                    },
                    _mapping_context(comment_chain, operation="get_note_comments"),
                    item_locator="comment:comment-author-convergence",
                    is_root=True,
                )
            )

        comment_author_id = session.scalar(
            select(comments_table.c.author_account_id).where(
                comments_table.c.id == comment.target_id
            )
        )
        account_ids = session.scalars(
            select(accounts_table.c.id).where(accounts_table.c.platform == "xiaohongshu")
        ).all()
        assert comment_author_id == original_author_id
        assert account_ids == [original_author_id]
    finally:
        session.rollback()
        session.close()


def test_account_primary_and_alternate_identity_conflict_fails_closed(
    database_runtime: DatabaseRuntime,
) -> None:
    """主 ID 与备用 ID 分别命中不同账号时不得错误合并。"""
    session = database_runtime.new_session()
    try:
        with session.begin():
            service = ContentIngestionService(PostgresContentRepository(session))
            for note_id, user_id, red_id in (
                ("note-account-a", "user-a", "red-a"),
                ("note-account-b", "user-b", "red-b"),
            ):
                chain = _insert_source_chain(
                    session,
                    operation="search_notes",
                    source_value=note_id,
                )
                service.ingest_content(
                    map_content(
                        {
                            "id": note_id,
                            "type": "normal",
                            "user": {"userid": user_id, "red_id": red_id},
                        },
                        _mapping_context(chain, operation="search_notes"),
                        item_locator=f"note:{note_id}",
                    )
                )

        with pytest.raises(ValueError, match="主 ID 与备用稳定 ID 指向不同账号"):
            with session.begin():
                service = ContentIngestionService(PostgresContentRepository(session))
                comment_chain = _insert_source_chain(
                    session,
                    operation="get_note_comments",
                    source_value="note-account-a",
                )
                service.ingest_comment(
                    map_comment(
                        {
                            "id": "comment-conflicting-author",
                            "note_id": "note-account-a",
                            "content": "身份矛盾",
                            "user": {"userid": "user-a", "red_id": "red-b"},
                        },
                        _mapping_context(comment_chain, operation="get_note_comments"),
                        item_locator="comment:comment-conflicting-author",
                        is_root=True,
                    )
                )

        assert len(session.scalars(select(accounts_table.c.id)).all()) == 2
        assert session.scalars(select(comments_table.c.id)).all() == []
    finally:
        session.rollback()
        session.close()


def test_sparse_sub_comment_does_not_clear_known_direct_parent(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            content_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛",
            )
            service = ContentIngestionService(PostgresContentRepository(session))
            service.ingest_content(
                map_content(
                    {"id": "note-comments", "type": "normal", "title": "评论测试"},
                    _mapping_context(content_chain, operation="search_notes"),
                    item_locator="note:note-comments",
                )
            )

            comment_chain = _insert_source_chain(
                session,
                operation="get_note_sub_comments",
                source_value="note-comments",
            )
            comment_context = replace(
                _mapping_context(comment_chain, operation="get_note_sub_comments"),
                root_comment_id="comment-root",
            )
            explicit = map_comment(
                {
                    "id": "comment-child",
                    "note_id": "note-comments",
                    "content": "回复",
                    "target_comment": {"id": "comment-parent"},
                },
                comment_context,
                item_locator="comment:comment-child",
                is_root=False,
            )
            first = service.ingest_comment(explicit)
            sparse = map_comment(
                {
                    "id": "comment-child",
                    "note_id": "note-comments",
                    "content": "回复",
                },
                comment_context,
                item_locator="comment:comment-child",
                is_root=False,
            )
            service.ingest_comment(sparse)

        comment = (
            session.execute(select(comments_table).where(comments_table.c.id == first.target_id))
            .mappings()
            .one()
        )
        assert comment["root_comment_id"] == "comment-root"
        assert comment["parent_comment_id"] == "comment-parent"
        assert comment["current_version"] == 1
    finally:
        session.rollback()
        session.close()


def test_comment_query_pages_roots_and_replies_without_losing_direct_parent(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            content_chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛评论展示",
            )
            service = ContentIngestionService(PostgresContentRepository(session))
            content = service.ingest_content(
                map_content(
                    {"id": "note-thread-query", "type": "normal", "title": "评论线程"},
                    _mapping_context(content_chain, operation="search_notes"),
                    item_locator="note:note-thread-query",
                )
            )
            root_chain = _insert_source_chain(
                session,
                operation="get_note_comments",
                source_value="note-thread-query",
            )
            root_context = _mapping_context(root_chain, operation="get_note_comments")
            for comment_id, author_id, nickname, created_at in (
                ("root-old", "author-root-old", "较早用户", 1_700_000_000),
                ("root-new", "author-root-new", "较新用户", 1_700_000_100),
            ):
                service.ingest_comment(
                    map_comment(
                        {
                            "id": comment_id,
                            "note_id": "note-thread-query",
                            "content": f"{nickname}的一级评论",
                            "create_time": created_at,
                            "user_info": {"userid": author_id, "nickname": nickname},
                        },
                        root_context,
                        item_locator=f"comment:{comment_id}",
                        is_root=True,
                    )
                )
            reply_chain = _insert_source_chain(
                session,
                operation="get_note_sub_comments",
                source_value="note-thread-query",
            )
            reply_context = replace(
                _mapping_context(reply_chain, operation="get_note_sub_comments"),
                root_comment_id="root-old",
            )
            for raw in (
                {
                    "id": "reply-parent",
                    "note_id": "note-thread-query",
                    "content": "第一条回复",
                    "create_time": 1_700_000_010,
                    "target_comment": {"id": "root-old"},
                    "user_info": {"userid": "author-reply-parent", "nickname": "回复用户甲"},
                },
                {
                    "id": "reply-child",
                    "note_id": "note-thread-query",
                    "content": "回复第一条回复",
                    "create_time": 1_700_000_020,
                    "target_comment": {"id": "reply-parent"},
                    "user_info": {"userid": "author-reply-child", "nickname": "回复用户乙"},
                },
            ):
                service.ingest_comment(
                    map_comment(
                        raw,
                        reply_context,
                        item_locator=f"comment:{raw['id']}",
                        is_root=False,
                    )
                )

        repository = PostgresContentQueryRepository(session, analysis_identity=None)
        first_roots = repository.list_comments_page(
            content.target_id,
            root_comment_id=None,
            position=None,
            limit=1,
        )
        second_roots = repository.list_comments_page(
            content.target_id,
            root_comment_id=None,
            position=ContentCursorPosition(
                sort_at=first_roots[0].published_at,
                content_id=first_roots[0].id,
            ),
            limit=2,
        )
        replies = repository.list_comments_page(
            content.target_id,
            root_comment_id="root-old",
            position=None,
            limit=20,
        )

        assert [item.external_comment_id for item in first_roots] == ["root-new"]
        assert [item.external_comment_id for item in second_roots] == ["root-old"]
        assert [item.external_comment_id for item in replies] == [
            "reply-parent",
            "reply-child",
        ]
        assert replies[0].parent_author_display_name == "较早用户"
        assert replies[1].parent_comment_id == "reply-parent"
        assert replies[1].parent_author_display_name == "回复用户甲"
        assert repository.count_comments(
            content.target_id,
            root_comment_id=None,
        ) == (2, 4)
        assert repository.count_comments(
            content.target_id,
            root_comment_id="root-old",
        ) == (2, 4)

        http_runtime = create_platform_runtime("comment-thread-integration")
        try:
            http_service = PostgresContentHttpService(
                http_runtime,
                cursor_signing_secret=b"comment-thread-integration-key-32b",
            )
            first_page = http_service.list_comments(
                content.target_id,
                ContentCommentListQuery(limit=1),
            )
            second_page = http_service.list_comments(
                content.target_id,
                ContentCommentListQuery(limit=1, cursor=first_page.next_cursor),
            )
            reply_page = http_service.list_comments(
                content.target_id,
                ContentCommentListQuery(root_comment_id="root-old", limit=20),
            )
            with pytest.raises(InvalidContentCursor):
                http_service.list_comments(
                    content.target_id,
                    ContentCommentListQuery(
                        root_comment_id="root-old",
                        cursor=first_page.next_cursor,
                        limit=20,
                    ),
                )
        finally:
            http_runtime.close()

        assert [item.external_comment_id for item in first_page.items] == ["root-new"]
        assert first_page.has_more is True
        assert [item.external_comment_id for item in second_page.items] == ["root-old"]
        assert [item.external_comment_id for item in reply_page.items] == [
            "reply-parent",
            "reply-child",
        ]
        assert reply_page.items[1].parent_author_display_name == "回复用户甲"
        assert reply_page.ingested_total_count == 4
    finally:
        session.rollback()
        session.close()


def test_candidate_requires_completed_attempt_with_linked_raw(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with pytest.raises(DBAPIError, match="Candidate 必须来自 completed"):
            with session.begin():
                chain = _insert_source_chain(
                    session,
                    operation="search_notes",
                    source_value="爱玛",
                    completed=False,
                )
                CandidateIngestionService(PostgresCandidateRepository(session)).discover(
                    provider_request_attempt_id=chain.attempt_id,
                    item_kind="content",
                    external_item_id="invalid",
                    item_locator="note:invalid",
                    discovered_at=OBSERVED_AT,
                )
    finally:
        session.rollback()
        session.close()


def test_candidate_ledgers_are_append_only_and_success_requires_target(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin():
            chain = _insert_source_chain(
                session,
                operation="search_notes",
                source_value="爱玛",
            )
            service = CandidateIngestionService(PostgresCandidateRepository(session))
            candidate = service.discover(
                provider_request_attempt_id=chain.attempt_id,
                item_kind="content",
                external_item_id="note-ledger",
                item_locator="note:note-ledger",
                discovered_at=OBSERVED_AT,
            )
            failed = service.record_ingestion(
                candidate_id=candidate.id,
                canonical=None,
                target_id=None,
                result="failed",
                error_code="mapper_failed",
            )

        mutations = (
            update(collection_candidates_table)
            .where(collection_candidates_table.c.id == candidate.id)
            .values(item_locator="note:mutated"),
            delete(collection_candidates_table).where(
                collection_candidates_table.c.id == candidate.id
            ),
            update(collection_candidate_ingestions_table)
            .where(collection_candidate_ingestions_table.c.id == failed.id)
            .values(result="unsupported"),
            delete(collection_candidate_ingestions_table).where(
                collection_candidate_ingestions_table.c.id == failed.id
            ),
        )
        for statement in mutations:
            with pytest.raises(DBAPIError, match="追加账本"):
                with session.begin():
                    session.execute(statement)

        with pytest.raises(DBAPIError, match="success_target_required"):
            with session.begin():
                session.execute(
                    insert(collection_candidate_ingestions_table).values(
                        id=uuid4(),
                        candidate_id=candidate.id,
                        ingestion_no=2,
                        observed_fields=[],
                        result="ingested",
                        processed_at=OBSERVED_AT,
                    )
                )
    finally:
        session.rollback()
        session.close()
