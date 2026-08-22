"""TikHub 真实脱敏 Fixture → Canonical → PostgreSQL 的多平台纵切回归。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.content import PostgresContentRepository
from aima_ugc.adapters.providers.tikhub.mappers.bilibili import (
    BilibiliMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.bilibili import (
    map_content as map_bilibili_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    DouyinMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    map_comment as map_douyin_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    map_content as map_douyin_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    KuaishouMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    map_comment as map_kuaishou_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    map_content as map_kuaishou_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    WeiboMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    map_comment as map_weibo_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    map_content as map_weibo_content,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XhsMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    map_comment as map_xhs_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    map_content as map_xhs_content,
)
from aima_ugc.adapters.providers.tikhub.operations import (
    bilibili,
    douyin,
    kuaishou,
    weibo,
    xiaohongshu,
)
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import (
    comment_metric_observations_table,
    comment_versions_table,
    comments_table,
    contents_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import insert, select

_ROOT = Path("tests/fixtures/providers/tikhub")
_OBSERVED_AT = datetime(2026, 8, 15, 20, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SourceChain:
    request_id: UUID
    attempt_id: UUID
    artifact_id: UUID


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


def _fixture(platform: str, name: str) -> dict[str, object]:
    return json.loads((_ROOT / platform / name).read_text(encoding="utf-8"))


def _insert_source_chain(
    session,
    *,
    platform: str,
    operation: str,
    source_value: str,
    operation_group: str,
) -> SourceChain:
    job_id = uuid4()
    run_id = uuid4()
    scope_id = uuid4()
    request_id = uuid4()
    attempt_id = uuid4()
    artifact_id = uuid4()
    now = _OBSERVED_AT

    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type="collection.run.v1",
            payload_version="collection.run.v1",
            payload={"schema_version": "collection.run.v1"},
            status="queued",
            internal_idempotency_key=f"real-normalized-ingestion:{job_id}",
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
            config_snapshot={"platforms": [platform]},
            status="queued",
            created_at=now,
        )
    )
    session.execute(
        insert(collection_scopes_table).values(
            id=scope_id,
            run_id=run_id,
            platform=platform,
            source_type="keyword_search" if operation_group == "content_discovery" else "content",
            source_value=source_value,
            operation_group=operation_group,
            status="running",
        )
    )
    session.execute(
        insert(provider_requests_table).values(
            id=request_id,
            scope_id=scope_id,
            provider="tikhub",
            operation=operation,
            request_fingerprint=uuid4().hex * 2,
            request_params={"source": source_value},
            pagination_input={},
            status="completed",
            attempt_count=1,
            created_at=now,
            completed_at=now,
        )
    )
    session.execute(
        insert(artifacts_table).values(
            id=artifact_id,
            kind="provider-raw",
            storage_backend="local",
            storage_key=f"raw/real-normalized-ingestion/{artifact_id}.json.gz",
            content_type="application/json",
            encoding="gzip",
            sha256=uuid4().hex * 2,
            byte_size=1,
            retention_class="raw",
            storage_status="linked",
            created_at=now,
            stored_at=now,
            linked_at=now,
        )
    )
    session.execute(
        insert(provider_request_attempts_table).values(
            id=attempt_id,
            provider_request_id=request_id,
            attempt_no=1,
            dispatch_status="completed",
            dispatch_started_at=now,
            completed_at=now,
            http_status=200,
            raw_artifact_id=artifact_id,
            billing_status="not_billable",
            created_at=now,
        )
    )
    return SourceChain(request_id, attempt_id, artifact_id)


def _common_context(
    context_type: type,
    chain: SourceChain,
    *,
    operation: str,
    source_value: str,
    external_content_id: str | None = None,
    root_comment_id: str | None = None,
):
    return context_type(
        provider_request_id=str(chain.request_id),
        provider_attempt_id=str(chain.attempt_id),
        raw_artifact_id=chain.artifact_id,
        operation=operation,
        source_type="keyword_search" if external_content_id is None else "content",
        source_value=source_value,
        observed_at=_OBSERVED_AT,
        external_content_id=external_content_id,
        root_comment_id=root_comment_id,
    )


def _xhs_context(chain: SourceChain, *, operation: str, source_value: str) -> XhsMappingContext:
    return XhsMappingContext(
        provider_request_id=str(chain.request_id),
        provider_attempt_id=str(chain.attempt_id),
        raw_artifact_id=chain.artifact_id,
        operation=operation,
        source_type="keyword_search",
        source_value=source_value,
        observed_at=_OBSERVED_AT,
    )


def _assert_content_persisted(session, canonical: CanonicalContentV1, target_id: UUID) -> None:
    row = (
        session.execute(select(contents_table).where(contents_table.c.id == target_id))
        .mappings()
        .one()
    )
    assert row["platform"] == canonical.platform
    assert row["external_content_id"] == canonical.external_content_id
    assert isinstance(row["external_content_id"], str)
    assert row["content_type"] == canonical.content_type
    if "title" in canonical.observed_fields:
        assert row["title"] == canonical.title
    if "text" in canonical.observed_fields:
        assert row["text"] == canonical.text
    for metric_name in (
        "like_count",
        "comment_count",
        "share_count",
        "repost_count",
        "favorite_count",
        "view_count",
        "play_count",
        "danmaku_count",
        "coin_count",
        "download_count",
    ):
        if f"metrics.{metric_name}" in canonical.observed_fields:
            assert row[f"current_{metric_name}"] == getattr(canonical.metrics, metric_name)


def test_real_search_fixtures_normalize_and_persist_for_all_five_platforms(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin_nested():
            service = ContentIngestionService(PostgresContentRepository(session))

            xhs_chain = _insert_source_chain(
                session,
                platform="xiaohongshu",
                operation="search_notes",
                source_value="爱玛",
                operation_group="content_discovery",
            )
            xhs_item = xiaohongshu.extract_search_items(
                _fixture("xiaohongshu", "search_notes_page1.sanitized.json")
            )[1]
            xhs_canonical = map_xhs_content(
                xhs_item,
                _xhs_context(xhs_chain, operation="search_notes", source_value="爱玛"),
                item_locator="data.data.items[1]",
            )
            xhs_result = service.ingest_content(xhs_canonical)

            cases = (
                (
                    "douyin",
                    "fetch_video_search_v2",
                    douyin.extract_search_items(_fixture("douyin", "search_page1.sanitized.json"))[
                        0
                    ],
                    DouyinMappingContext,
                    map_douyin_content,
                    "data.business_data[0]",
                ),
                (
                    "weibo",
                    "fetch_search",
                    weibo.extract_search_items(_fixture("weibo", "search_page1.sanitized.json"))[0],
                    WeiboMappingContext,
                    map_weibo_content,
                    "data.data.cards[0]",
                ),
                (
                    "bilibili",
                    "fetch_search_by_type",
                    bilibili.extract_search_items(
                        _fixture("bilibili", "search_page1.sanitized.json")
                    )[0],
                    BilibiliMappingContext,
                    map_bilibili_content,
                    "data.data.items[0]",
                ),
                (
                    "kuaishou",
                    "search_video_v2",
                    kuaishou.extract_search_items(
                        _fixture("kuaishou", "search_page1.sanitized.json")
                    )[0],
                    KuaishouMappingContext,
                    map_kuaishou_content,
                    "data.mixFeeds[0]",
                ),
            )
            mapped_results: list[tuple[CanonicalContentV1, UUID]] = [
                (xhs_canonical, xhs_result.target_id)
            ]
            for platform, operation, raw_item, context_type, mapper, locator in cases:
                chain = _insert_source_chain(
                    session,
                    platform=platform,
                    operation=operation,
                    source_value="爱玛",
                    operation_group="content_discovery",
                )
                canonical = mapper(
                    raw_item,
                    _common_context(
                        context_type,
                        chain,
                        operation=operation,
                        source_value="爱玛",
                    ),
                    item_locator=locator,
                )
                result = service.ingest_content(canonical)
                mapped_results.append((canonical, result.target_id))

        assert {canonical.platform for canonical, _ in mapped_results} == {
            "xiaohongshu",
            "douyin",
            "weibo",
            "bilibili",
            "kuaishou",
        }
        for canonical, target_id in mapped_results:
            _assert_content_persisted(session, canonical, target_id)
    finally:
        session.rollback()
        session.close()


def _parent_content(
    *, platform: str, external_content_id: str, chain: SourceChain
) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform=platform,
        external_content_id=external_content_id,
        content_type="unknown",
        observed_at=_OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="fixture_parent",
            provider_request_id=str(chain.request_id),
            provider_attempt_id=str(chain.attempt_id),
            raw_artifact_id=chain.artifact_id,
            source_type="content",
            source_value=external_content_id,
            item_locator="fixture-parent",
            observed_at=_OBSERVED_AT,
        ),
        observed_fields=["content_type"],
    )


def test_real_root_comment_fixtures_persist_canonical_comment_semantics(
    database_runtime: DatabaseRuntime,
) -> None:
    session = database_runtime.new_session()
    try:
        with session.begin_nested():
            service = ContentIngestionService(PostgresContentRepository(session))
            cases = (
                (
                    "xiaohongshu",
                    "xhs-note-1",
                    "get_note_comments",
                    xiaohongshu.extract_comment_items(
                        _fixture("xiaohongshu", "comments_page1.sanitized.json")
                    )[0],
                    XhsMappingContext,
                    map_xhs_comment,
                    "data.data.comments[0]",
                ),
                (
                    "douyin",
                    "douyin-aweme-1",
                    "fetch_video_comments",
                    douyin.extract_comment_items(
                        _fixture("douyin", "comments_page1.sanitized.json")
                    )[0],
                    DouyinMappingContext,
                    map_douyin_comment,
                    "data.comments[0]",
                ),
                (
                    "weibo",
                    "weibo-status-1",
                    "fetch_status_comments",
                    weibo.extract_comment_items(_fixture("weibo", "comments_page1.sanitized.json"))[
                        0
                    ],
                    WeiboMappingContext,
                    map_weibo_comment,
                    "data.items[0].data",
                ),
                (
                    "kuaishou",
                    "100003",
                    "fetch_one_video_comment",
                    kuaishou.extract_comment_items(
                        _fixture("kuaishou", "comments_page1.sanitized.json")
                    )[0],
                    KuaishouMappingContext,
                    map_kuaishou_comment,
                    "data.rootComments[0]",
                ),
            )
            results = []
            for (
                platform,
                content_id,
                operation,
                raw_comment,
                context_type,
                mapper,
                locator,
            ) in cases:
                parent_chain = _insert_source_chain(
                    session,
                    platform=platform,
                    operation="fixture_parent",
                    source_value=content_id,
                    operation_group="content_discovery",
                )
                service.ingest_content(
                    _parent_content(
                        platform=platform,
                        external_content_id=content_id,
                        chain=parent_chain,
                    )
                )
                comment_chain = _insert_source_chain(
                    session,
                    platform=platform,
                    operation=operation,
                    source_value=content_id,
                    operation_group="comments",
                )
                if platform == "xiaohongshu":
                    context = XhsMappingContext(
                        provider_request_id=str(comment_chain.request_id),
                        provider_attempt_id=str(comment_chain.attempt_id),
                        raw_artifact_id=comment_chain.artifact_id,
                        operation=operation,
                        source_type="content",
                        source_value=content_id,
                        observed_at=_OBSERVED_AT,
                    )
                else:
                    context = _common_context(
                        context_type,
                        comment_chain,
                        operation=operation,
                        source_value=content_id,
                        external_content_id=content_id,
                    )
                canonical = mapper(
                    raw_comment,
                    context,
                    item_locator=locator,
                    is_root=True,
                )
                result = service.ingest_comment(canonical)
                results.append((canonical, result.target_id))

        assert {canonical.platform for canonical, _ in results} == {
            "xiaohongshu",
            "douyin",
            "weibo",
            "kuaishou",
        }
        for canonical, target_id in results:
            row = (
                session.execute(select(comments_table).where(comments_table.c.id == target_id))
                .mappings()
                .one()
            )
            assert row["external_comment_id"] == canonical.external_comment_id
            assert isinstance(row["external_comment_id"], str)
            assert row["root_comment_id"] == canonical.external_comment_id
            assert row["parent_comment_id"] is None
            if "text" in canonical.observed_fields:
                assert row["text"] == canonical.text
            if "metrics.like_count" in canonical.observed_fields:
                assert row["current_like_count"] == canonical.metrics.like_count
            if "metrics.reply_count" in canonical.observed_fields:
                assert row["current_reply_count"] == canonical.metrics.reply_count
            assert session.execute(
                select(comment_versions_table.c.version_no).where(
                    comment_versions_table.c.comment_id == target_id
                )
            ).scalars().all() == [1]
            assert session.execute(
                select(comment_metric_observations_table.c.reason).where(
                    comment_metric_observations_table.c.comment_id == target_id
                )
            ).scalars().all() == ["initial"]
    finally:
        session.rollback()
        session.close()
