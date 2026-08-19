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
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XhsMappingContext,
    map_comment,
    map_content,
)
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import extract_search_items
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

_FIXTURE = Path("tests/fixtures/providers/tikhub/xhs/search_notes_page1.sanitized.json")
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
            config_snapshot={"platforms": ["xhs"]},
            status="queued",
            created_at=now,
        )
    )
    session.execute(
        insert(collection_scopes_table).values(
            id=scope_id,
            run_id=run_id,
            platform="xhs",
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


def _mapping_context(chain: SourceChain, *, operation: str) -> XhsMappingContext:
    assert chain.artifact_id is not None
    return XhsMappingContext(
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
        assert content_row["platform"] == "xhs"
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
                    accounts_table.c.platform == "xhs",
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
