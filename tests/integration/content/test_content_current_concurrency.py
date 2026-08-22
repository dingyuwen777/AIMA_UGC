"""Stage 6 Content Current 的乱序与 PostgreSQL 并发回归。"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.content import PostgresContentRepository
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.tables import (
    accounts_table,
    comments_table,
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import insert, select, text


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


def _source(runtime: DatabaseRuntime, *, observed_at: datetime, suffix: str) -> CanonicalSourceV1:
    job_id = uuid4()
    run_id = uuid4()
    scope_id = uuid4()
    request_id = uuid4()
    attempt_id = uuid4()
    artifact_id = uuid4()
    session = runtime.new_session()
    try:
        with session.begin():
            session.execute(
                insert(jobs_table).values(
                    id=job_id,
                    job_type="collection.run.v1",
                    payload_version="collection.run.v1",
                    payload={"schema_version": "collection.run.v1"},
                    status="queued",
                    internal_idempotency_key=f"content-current:{suffix}:{job_id}",
                    priority=10,
                    attempt=0,
                    max_attempts=2,
                    timeout_seconds=300,
                    progress=0,
                    available_at=observed_at,
                    created_at=observed_at,
                    updated_at=observed_at,
                )
            )
            session.execute(
                insert(collection_runs_table).values(
                    id=run_id,
                    job_id=job_id,
                    trigger_type="backfill",
                    config_snapshot={},
                    status="running",
                    started_at=observed_at,
                    created_at=observed_at,
                )
            )
            session.execute(
                insert(collection_scopes_table).values(
                    id=scope_id,
                    run_id=run_id,
                    platform="xiaohongshu",
                    source_type="keyword_search",
                    source_value=suffix,
                    operation_group="content_discovery",
                    status="running",
                    started_at=observed_at,
                )
            )
            session.execute(
                insert(provider_requests_table).values(
                    id=request_id,
                    scope_id=scope_id,
                    provider="tikhub",
                    operation="search_notes",
                    request_fingerprint=uuid4().hex * 2,
                    request_params={"source": suffix},
                    pagination_input={},
                    status="completed",
                    attempt_count=1,
                    created_at=observed_at,
                    completed_at=observed_at + timedelta(seconds=1),
                )
            )
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
                    created_at=observed_at,
                    stored_at=observed_at,
                    linked_at=observed_at + timedelta(seconds=1),
                )
            )
            session.execute(
                insert(provider_request_attempts_table).values(
                    id=attempt_id,
                    provider_request_id=request_id,
                    attempt_no=1,
                    dispatch_status="completed",
                    dispatch_started_at=observed_at,
                    completed_at=observed_at + timedelta(seconds=1),
                    http_status=200,
                    raw_artifact_id=artifact_id,
                    billing_status="not_billable",
                    created_at=observed_at,
                )
            )
    finally:
        session.close()
    return CanonicalSourceV1(
        provider_name="tikhub",
        operation="search_notes",
        provider_request_id=str(request_id),
        provider_attempt_id=str(attempt_id),
        raw_artifact_id=artifact_id,
        source_type="keyword_search",
        source_value=suffix,
        item_locator=f"note:{suffix}",
        observed_at=observed_at,
    )


def _content(
    *,
    source: CanonicalSourceV1,
    observed_at: datetime,
    external_id: str,
    title: str,
    like_count: int,
    author_id: str | None = None,
) -> CanonicalContentV1:
    observed_fields = ["content_type", "title", "metrics.like_count"]
    author = None
    if author_id is not None:
        author = CanonicalAuthorV1(
            external_account_id=author_id,
            display_name=f"作者-{author_id}",
        )
        observed_fields.extend(["author.external_account_id", "author.display_name"])
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_id,
        content_type="note",
        title=title,
        author=author,
        observed_at=observed_at,
        metrics=CanonicalMetricsV1(like_count=like_count),
        source=source,
        observed_fields=observed_fields,
    )


def _comment(
    *,
    source: CanonicalSourceV1,
    observed_at: datetime,
    external_content_id: str,
    external_comment_id: str,
) -> CanonicalCommentV1:
    return CanonicalCommentV1(
        platform="xiaohongshu",
        external_content_id=external_content_id,
        external_comment_id=external_comment_id,
        root_comment_id=external_comment_id,
        text="并发评论",
        observed_at=observed_at,
        metrics=CanonicalMetricsV1(like_count=1),
        source=source,
        observed_fields=[
            "root_comment_id",
            "text",
            "metrics.like_count",
        ],
    )


def test_older_observation_does_not_regress_current_but_keeps_metric_fact(
    database_runtime: DatabaseRuntime,
) -> None:
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    newer = _content(
        source=_source(database_runtime, observed_at=newer_at, suffix="newer"),
        observed_at=newer_at,
        external_id="note-out-of-order",
        title="NEW",
        like_count=20,
    )
    older = _content(
        source=_source(database_runtime, observed_at=older_at, suffix="older"),
        observed_at=older_at,
        external_id="note-out-of-order",
        title="OLD",
        like_count=10,
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            repository = PostgresContentRepository(session)
            first = repository.ingest_content(newer)
            second = repository.ingest_content(older)

        current = (
            session.execute(select(contents_table).where(contents_table.c.id == first.target_id))
            .mappings()
            .one()
        )
        versions = session.execute(
            select(content_versions_table.c.title, content_versions_table.c.observed_at)
            .where(content_versions_table.c.content_id == first.target_id)
            .order_by(content_versions_table.c.version_no)
        ).all()
        metrics = session.execute(
            select(
                content_metric_observations_table.c.like_count,
                content_metric_observations_table.c.observed_at,
            )
            .where(content_metric_observations_table.c.content_id == first.target_id)
            .order_by(content_metric_observations_table.c.observed_at)
        ).all()
    finally:
        session.close()

    assert second.target_id == first.target_id
    assert current["title"] == "NEW"
    assert current["current_like_count"] == 20
    assert current["first_seen_at"] == older_at
    assert current["last_seen_at"] == newer_at
    assert current["updated_at"] == newer_at
    assert current["current_version"] == 1
    assert versions == [("NEW", newer_at)]
    assert metrics == [(10, older_at), (20, newer_at)]


def test_sparse_metric_history_keeps_unobserved_metrics_null(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    source = _source(database_runtime, observed_at=observed_at, suffix="sparse")
    observation = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="note-sparse-metric",
        content_type="note",
        title="稀疏",
        observed_at=observed_at,
        metrics=CanonicalMetricsV1(like_count=7, comment_count=999),
        source=source,
        observed_fields=["content_type", "title", "metrics.like_count"],
    )
    session = database_runtime.new_session()
    try:
        with session.begin():
            result = PostgresContentRepository(session).ingest_content(observation)
        metric = (
            session.execute(
                select(content_metric_observations_table).where(
                    content_metric_observations_table.c.content_id == result.target_id
                )
            )
            .mappings()
            .one()
        )
    finally:
        session.close()
    assert metric["like_count"] == 7
    assert metric["comment_count"] is None


def test_concurrent_first_content_insert_converges_on_one_row(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    observations = [
        _content(
            source=_source(database_runtime, observed_at=observed_at, suffix=f"content-{index}"),
            observed_at=observed_at,
            external_id="note-concurrent",
            title="并发内容",
            like_count=1,
        )
        for index in range(2)
    ]
    _install_delay_trigger(database_runtime, table="contents", trigger="delay_contents_insert")
    barrier = Barrier(2)

    def ingest(observation: CanonicalContentV1) -> UUID:
        session = database_runtime.new_session()
        try:
            barrier.wait()
            with session.begin():
                return PostgresContentRepository(session).ingest_content(observation).target_id
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = [
                future.result()
                for future in [executor.submit(ingest, item) for item in observations]
            ]
    finally:
        _drop_delay_trigger(database_runtime, table="contents", trigger="delay_contents_insert")

    assert ids[0] == ids[1]
    with database_runtime.engine.connect() as connection:
        count = connection.scalar(
            select(text("count(*)"))
            .select_from(contents_table)
            .where(contents_table.c.external_content_id == "note-concurrent")
        )
    assert count == 1


def test_concurrent_first_comment_insert_converges_on_one_row(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    content_source = _source(database_runtime, observed_at=observed_at, suffix="comment-parent")
    session = database_runtime.new_session()
    try:
        with session.begin():
            PostgresContentRepository(session).ingest_content(
                _content(
                    source=content_source,
                    observed_at=observed_at,
                    external_id="note-for-comment-race",
                    title="父内容",
                    like_count=0,
                )
            )
    finally:
        session.close()

    observations = [
        _comment(
            source=_source(database_runtime, observed_at=observed_at, suffix=f"comment-{index}"),
            observed_at=observed_at,
            external_content_id="note-for-comment-race",
            external_comment_id="comment-concurrent",
        )
        for index in range(2)
    ]
    _install_delay_trigger(database_runtime, table="comments", trigger="delay_comments_insert")
    barrier = Barrier(2)

    def ingest(observation: CanonicalCommentV1) -> UUID:
        worker_session = database_runtime.new_session()
        try:
            barrier.wait()
            with worker_session.begin():
                return (
                    PostgresContentRepository(worker_session).ingest_comment(observation).target_id
                )
        finally:
            worker_session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = [
                future.result()
                for future in [executor.submit(ingest, item) for item in observations]
            ]
    finally:
        _drop_delay_trigger(database_runtime, table="comments", trigger="delay_comments_insert")

    assert ids[0] == ids[1]
    with database_runtime.engine.connect() as connection:
        count = connection.scalar(
            select(text("count(*)"))
            .select_from(comments_table)
            .where(comments_table.c.external_comment_id == "comment-concurrent")
        )
    assert count == 1


def test_concurrent_first_account_insert_converges_on_one_row(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    observations = [
        _content(
            source=_source(database_runtime, observed_at=observed_at, suffix=f"account-{index}"),
            observed_at=observed_at,
            external_id=f"note-account-{index}",
            title=f"账号并发-{index}",
            like_count=1,
            author_id="author-concurrent",
        )
        for index in range(2)
    ]
    _install_delay_trigger(database_runtime, table="accounts", trigger="delay_accounts_insert")
    barrier = Barrier(2)

    def ingest(observation: CanonicalContentV1) -> UUID:
        session = database_runtime.new_session()
        try:
            barrier.wait()
            with session.begin():
                result = PostgresContentRepository(session).ingest_content(observation)
                return result.target_id
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            [future.result() for future in [executor.submit(ingest, item) for item in observations]]
    finally:
        _drop_delay_trigger(database_runtime, table="accounts", trigger="delay_accounts_insert")

    with database_runtime.engine.connect() as connection:
        rows = connection.execute(
            select(accounts_table.c.id).where(
                accounts_table.c.platform == "xiaohongshu",
                accounts_table.c.external_account_id == "author-concurrent",
            )
        ).all()
    assert len(rows) == 1


def _install_delay_trigger(runtime: DatabaseRuntime, *, table: str, trigger: str) -> None:
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE OR REPLACE FUNCTION aima_test_delay_insert() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              PERFORM pg_sleep(0.20);
              RETURN NEW;
            END;
            $$
            """
        )
        connection.exec_driver_sql(
            f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION aima_test_delay_insert()"
        )


def _drop_delay_trigger(runtime: DatabaseRuntime, *, table: str, trigger: str) -> None:
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        connection.exec_driver_sql("DROP FUNCTION IF EXISTS aima_test_delay_insert()")
