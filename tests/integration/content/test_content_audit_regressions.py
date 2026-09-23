"""全面审计发现的 Content Current/账号稳定 ID 回归。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.content import PostgresContentRepository
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalLocationV1,
    CanonicalMediaV1,
    CanonicalMentionV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
    CanonicalTopicV1,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.account_tables import account_external_ids_table
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.content.extended_tables import (
    content_external_ids_table,
    content_locations_table,
    content_media_table,
    content_mentions_table,
    content_topics_table,
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
from sqlalchemy import insert, select


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
                    internal_idempotency_key=f"audit-content:{suffix}:{job_id}",
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
        item_locator=f"audit:{suffix}",
        observed_at=observed_at,
    )


def test_older_sparse_content_can_fill_field_never_seen_by_newer_observation(
    database_runtime: DatabaseRuntime,
) -> None:
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    newer = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-sparse-content",
        content_type="note",
        title="NEW",
        observed_at=newer_at,
        metrics=CanonicalMetricsV1(like_count=20),
        source=_source(database_runtime, observed_at=newer_at, suffix="content-newer"),
        observed_fields=["content_type", "title", "metrics.like_count"],
    )
    older = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-sparse-content",
        content_type="note",
        text="OLDER DETAIL TEXT",
        observed_at=older_at,
        source=_source(database_runtime, observed_at=older_at, suffix="content-older"),
        observed_fields=["content_type", "text"],
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            repository = PostgresContentRepository(session)
            first = repository.ingest_content(newer)
            repository.ingest_content(older)
        current = (
            session.execute(select(contents_table).where(contents_table.c.id == first.target_id))
            .mappings()
            .one()
        )
    finally:
        session.close()

    assert current["title"] == "NEW"
    assert current["text"] == "OLDER DETAIL TEXT"
    assert current["current_like_count"] == 20
    assert current["last_seen_at"] == newer_at


def test_newer_explicit_null_blocks_older_non_null_value(
    database_runtime: DatabaseRuntime,
) -> None:
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    newer = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-explicit-null-content",
        content_type="note",
        title=None,
        observed_at=newer_at,
        source=_source(database_runtime, observed_at=newer_at, suffix="explicit-null-newer"),
        observed_fields=["content_type", "title"],
    )
    older = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-explicit-null-content",
        content_type="note",
        title="OLDER TITLE",
        observed_at=older_at,
        source=_source(database_runtime, observed_at=older_at, suffix="explicit-null-older"),
        observed_fields=["content_type", "title"],
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            repository = PostgresContentRepository(session)
            first = repository.ingest_content(newer)
            repository.ingest_content(older)
        current = (
            session.execute(select(contents_table).where(contents_table.c.id == first.target_id))
            .mappings()
            .one()
        )
    finally:
        session.close()

    assert current["title"] is None
    assert current["field_observed_at"]["title"] == newer_at.isoformat()
    assert current["last_seen_at"] == newer_at


def test_older_sparse_comment_can_fill_field_never_seen_by_newer_observation(
    database_runtime: DatabaseRuntime,
) -> None:
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    parent = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-comment-parent",
        content_type="note",
        observed_at=older_at,
        source=_source(database_runtime, observed_at=older_at, suffix="comment-parent"),
        observed_fields=["content_type"],
    )
    newer = CanonicalCommentV1(
        platform="xiaohongshu",
        external_content_id="audit-comment-parent",
        external_comment_id="audit-comment",
        root_comment_id="audit-comment",
        text="NEW",
        observed_at=newer_at,
        source=_source(database_runtime, observed_at=newer_at, suffix="comment-newer"),
        observed_fields=["root_comment_id", "text"],
    )
    older = CanonicalCommentV1(
        platform="xiaohongshu",
        external_content_id="audit-comment-parent",
        external_comment_id="audit-comment",
        root_comment_id="audit-comment",
        parent_comment_id="older-parent-id",
        observed_at=older_at,
        source=_source(database_runtime, observed_at=older_at, suffix="comment-older"),
        observed_fields=["root_comment_id", "parent_comment_id"],
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            repository = PostgresContentRepository(session)
            repository.ingest_content(parent)
            first = repository.ingest_comment(newer)
            repository.ingest_comment(older)
        current = (
            session.execute(select(comments_table).where(comments_table.c.id == first.target_id))
            .mappings()
            .one()
        )
    finally:
        session.close()

    assert current["text"] == "NEW"
    assert current["parent_comment_id"] == "older-parent-id"
    assert current["last_seen_at"] == newer_at


def test_older_sparse_account_can_fill_field_never_seen_by_newer_observation(
    database_runtime: DatabaseRuntime,
) -> None:
    newer_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    older_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    newer_author = CanonicalAuthorV1(
        external_account_id="audit-account",
        display_name="NEW NAME",
    )
    older_author = CanonicalAuthorV1(
        external_account_id="audit-account",
        bio="OLDER BIO",
    )
    newer = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-account-content-new",
        content_type="note",
        author=newer_author,
        observed_at=newer_at,
        source=_source(database_runtime, observed_at=newer_at, suffix="account-newer"),
        observed_fields=[
            "content_type",
            "author.external_account_id",
            "author.display_name",
        ],
    )
    older = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-account-content-old",
        content_type="note",
        author=older_author,
        observed_at=older_at,
        source=_source(database_runtime, observed_at=older_at, suffix="account-older"),
        observed_fields=[
            "content_type",
            "author.external_account_id",
            "author.bio",
        ],
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            repository = PostgresContentRepository(session)
            repository.ingest_content(newer)
            repository.ingest_content(older)
        account = (
            session.execute(
                select(accounts_table).where(
                    accounts_table.c.platform == "xiaohongshu",
                    accounts_table.c.external_account_id == "audit-account",
                )
            )
            .mappings()
            .one()
        )
    finally:
        session.close()

    assert account["display_name"] == "NEW NAME"
    assert account["bio"] == "OLDER BIO"
    assert account["last_seen_at"] == newer_at


def test_alternate_stable_id_conflict_fails_closed_instead_of_overwriting(
    database_runtime: DatabaseRuntime,
) -> None:
    first_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    second_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    first_author = CanonicalAuthorV1(
        external_account_id="audit-alt-account",
        alternate_ids={"red_id": "red-stable-1"},
    )
    second_author = CanonicalAuthorV1(
        external_account_id="audit-alt-account",
        alternate_ids={"red_id": "red-conflict-2"},
    )
    first = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-alt-content-1",
        content_type="note",
        author=first_author,
        observed_at=first_at,
        source=_source(database_runtime, observed_at=first_at, suffix="alt-first"),
        observed_fields=[
            "content_type",
            "author.external_account_id",
            "author.alternate_ids",
        ],
    )
    second = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="audit-alt-content-2",
        content_type="note",
        author=second_author,
        observed_at=second_at,
        source=_source(database_runtime, observed_at=second_at, suffix="alt-second"),
        observed_fields=[
            "content_type",
            "author.external_account_id",
            "author.alternate_ids",
        ],
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            PostgresContentRepository(session).ingest_content(first)
        with pytest.raises(ValueError, match="稳定外部 ID 冲突"):
            with session.begin():
                PostgresContentRepository(session).ingest_content(second)
        row = session.execute(select(account_external_ids_table)).mappings().one()
    finally:
        session.close()

    assert row["id_type"] == "red_id"
    assert row["external_id"] == "red-stable-1"


def test_complete_new_content_batch_persists_rich_projection_and_reversible_delta(
    database_runtime: DatabaseRuntime,
) -> None:
    """集合快路径必须完整保存 Current、子实体、指标、首版本和可逆来源贡献。"""

    observed_at = datetime(2026, 9, 23, 12, 30, tzinfo=UTC)
    observation = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="batch-rich-content",
        alternate_ids={"note_id": "batch-rich-note"},
        content_type="note",
        title="批量完整投影",
        text="星曜批量写入",
        canonical_url="https://www.xiaohongshu.com/explore/batch-rich-content",
        share_url="https://www.xiaohongshu.com/discovery/item/batch-rich-content",
        author=CanonicalAuthorV1(handle="batch-author", display_name="批量作者"),
        published_at=observed_at - timedelta(hours=1),
        source_updated_at=observed_at - timedelta(minutes=5),
        observed_at=observed_at,
        media=[
            CanonicalMediaV1(
                media_type="image",
                external_media_id="batch-image",
                url="https://example.com/batch-image.jpg",
                width=1080,
                height=1440,
                position=2,
                alt_text="批量图片",
            )
        ],
        topics=[
            CanonicalTopicV1(
                name="星曜话题",
                external_topic_id="batch-topic",
                url="https://example.com/topics/batch-topic",
            )
        ],
        mentions=[
            CanonicalMentionV1(
                account=CanonicalAuthorV1(
                    external_account_id="mentioned-account",
                    display_name="被提及账号",
                ),
                display_text="@被提及账号",
            )
        ],
        locations=[
            CanonicalLocationV1(
                location_type="place",
                label="上海",
                country="中国",
                city="上海",
                latitude=31.2304,
                longitude=121.4737,
            )
        ],
        metrics=CanonicalMetricsV1(like_count=128, view_count=4096),
        status="available",
        source=_source(database_runtime, observed_at=observed_at, suffix="batch-rich"),
        observed_fields=[
            "alternate_ids",
            "content_type",
            "title",
            "text",
            "canonical_url",
            "share_url",
            "author.handle",
            "author.display_name",
            "published_at",
            "source_updated_at",
            "media",
            "topics",
            "mentions",
            "locations",
            "metrics.like_count",
            "metrics.view_count",
            "status",
        ],
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            results = PostgresCompleteContentRepository(
                session,
                replay_visibility_owner_id=None,
            ).ingest_new_contents_batch((observation,))
        assert len(results) == 1
        content_id = results[0].result.target_id
        current = (
            session.execute(select(contents_table).where(contents_table.c.id == content_id))
            .mappings()
            .one()
        )
        version = (
            session.execute(
                select(content_versions_table).where(
                    content_versions_table.c.content_id == content_id
                )
            )
            .mappings()
            .one()
        )
        metric = (
            session.execute(
                select(content_metric_observations_table).where(
                    content_metric_observations_table.c.content_id == content_id
                )
            )
            .mappings()
            .one()
        )
        contribution = (
            session.execute(
                select(content_source_contributions_table).where(
                    content_source_contributions_table.c.content_id == content_id
                )
            )
            .mappings()
            .one()
        )
        extension_rows = {
            "alternate_ids": session.execute(
                select(content_external_ids_table).where(
                    content_external_ids_table.c.content_id == content_id
                )
            )
            .mappings()
            .all(),
            "media": session.execute(
                select(content_media_table).where(content_media_table.c.content_id == content_id)
            )
            .mappings()
            .all(),
            "topics": session.execute(
                select(content_topics_table).where(content_topics_table.c.content_id == content_id)
            )
            .mappings()
            .all(),
            "mentions": session.execute(
                select(content_mentions_table).where(
                    content_mentions_table.c.content_id == content_id
                )
            )
            .mappings()
            .all(),
            "locations": session.execute(
                select(content_locations_table).where(
                    content_locations_table.c.content_id == content_id
                )
            )
            .mappings()
            .all(),
        }
    finally:
        session.close()

    assert current["title"] == observation.title
    assert current["text"] == observation.text
    assert current["current_version"] == 1
    assert current["current_like_count"] == 128
    assert current["current_view_count"] == 4096
    assert current["replay_visibility_owner_id"] is None
    assert set(current["field_observed_at"]) >= set(observation.observed_fields) - {
        "author.handle",
        "author.display_name",
    }
    assert version["author_snapshot"]["display_name"] == "批量作者"
    assert metric["like_count"] == 128
    assert metric["view_count"] == 4096
    assert all(len(rows) == 1 for rows in extension_rows.values())
    assert extension_rows["media"][0]["position"] == 2
    assert extension_rows["mentions"][0]["display_text"] == "@被提及账号"
    assert extension_rows["locations"][0]["city"] == "上海"
    delta = contribution["delta"]
    assert delta["schema_version"] == "content-source-contribution.v1"
    assert delta["created_content"] is True
    assert set(delta["collections"]) == set(extension_rows)
