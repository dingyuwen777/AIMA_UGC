"""Stage 12A 历史 Content 批量填空与逐行对账。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.historical_content import (
    HistoricalBatchRow,
    PostgresHistoricalContentRepository,
)
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import (
    accounts_table,
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
    processing_import_batch_item_conflicts_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
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
            "TRUNCATE TABLE historical_import_campaigns, jobs, artifacts, accounts "
            "RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE historical_import_campaigns, jobs, artifacts, accounts "
                "RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _historical_source(
    session,
    *,
    batch_id: UUID,
    artifact_id: UUID,
    observed_at: datetime,
) -> CanonicalSourceV1:
    request_id = uuid4()
    attempt_id = uuid4()
    session.execute(
        insert(provider_requests_table).values(
            id=request_id,
            import_batch_id=batch_id,
            provider="file_import",
            operation="historical_excel_import",
            request_fingerprint=uuid4().hex * 2,
            request_params={"historical": True},
            pagination_input={},
            status="completed",
            attempt_count=1,
            created_at=observed_at,
            completed_at=observed_at,
        )
    )
    session.execute(
        insert(provider_request_attempts_table).values(
            id=attempt_id,
            provider_request_id=request_id,
            attempt_no=1,
            dispatch_status="completed",
            dispatch_started_at=observed_at,
            completed_at=observed_at,
            http_status=200,
            raw_artifact_id=artifact_id,
            billing_status="not_billable",
            created_at=observed_at,
        )
    )
    return CanonicalSourceV1(
        provider_name="file_import",
        operation="historical_excel_import",
        provider_request_id=str(request_id),
        provider_attempt_id=str(attempt_id),
        raw_artifact_id=artifact_id,
        source_type="historical_excel",
        source_value="history.xlsx",
        item_locator="row:1",
        observed_at=observed_at,
    )


def _setup_batch(session, *, observed_at: datetime) -> tuple[UUID, UUID, UUID]:
    job_id = uuid4()
    artifact_id = uuid4()
    campaign_id = uuid4()
    item_id = uuid4()
    batch_id = uuid4()
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type="ingestion.historical-import-chunk.v1",
            payload_version="ingestion.historical-import-chunk.v1",
            payload={"schema_version": "ingestion.historical-import-chunk.v1"},
            status="queued",
            internal_idempotency_key=f"stage12:{job_id}",
            priority=-10,
            attempt=0,
            max_attempts=3,
            timeout_seconds=1800,
            progress=0,
            available_at=observed_at,
            created_at=observed_at,
            updated_at=observed_at,
        )
    )
    session.execute(
        insert(artifacts_table).values(
            id=artifact_id,
            kind="historical-input",
            storage_backend="local",
            storage_key=f"historical-input/{artifact_id}.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            sha256="a" * 64,
            byte_size=1,
            retention_class="raw",
            storage_status="linked",
            created_at=observed_at,
            stored_at=observed_at,
            linked_at=observed_at,
        )
    )
    session.execute(
        insert(historical_import_campaigns_table).values(
            id=campaign_id,
            client_idempotency_key=f"campaign-{campaign_id}",
            root_relative_path="",
            recursive=False,
            profile_snapshot={"schema_version": "historical-import-profile.v1"},
            keyword_pack_snapshot={},
            status="running",
            created_at=observed_at,
            started_at=observed_at,
        )
    )
    session.execute(
        insert(historical_import_campaign_items_table).values(
            id=item_id,
            campaign_id=campaign_id,
            item_kind="chunk",
            relative_path="history.xlsx",
            manifest_identity="b" * 64,
            ordinal=0,
            artifact_id=artifact_id,
            sha256="a" * 64,
            row_start=1,
            row_end=10,
            row_count=10,
            status="running",
            created_at=observed_at,
        )
    )
    session.execute(
        insert(processing_import_batches_table).values(
            id=batch_id,
            input_artifact_id=artifact_id,
            job_id=job_id,
            status="processing",
            stats={},
            historical_mode=True,
            historical_campaign_item_id=item_id,
            historical_policy_version="historical-fill-only.v1",
            created_at=observed_at,
            started_at=observed_at,
        )
    )
    return batch_id, item_id, artifact_id


def _content(
    *,
    source: CanonicalSourceV1,
    external_id: str,
    title: str | None,
    text: str | None,
    author_name: str | None,
    author_external_id: str = "author-stage12",
    author_bio: str | None = None,
    author_follower_count: int | None = None,
    like_count: int | None = None,
) -> CanonicalContentV1:
    """构造可显式控制 Content/Author 观测字段的历史行。"""

    fields = ["content_type"]
    if title is not None:
        fields.append("title")
    if text is not None:
        fields.append("text")
    author = None
    if author_name is not None or author_bio is not None:
        author = CanonicalAuthorV1(
            external_account_id=author_external_id,
            display_name=author_name,
            bio=author_bio,
            follower_count=author_follower_count,
        )
        fields.append("author.external_account_id")
        if author_name is not None:
            fields.append("author.display_name")
        if author_bio is not None:
            fields.append("author.bio")
        if author_follower_count is not None:
            fields.append("author.follower_count")
    if like_count is not None:
        fields.append("metrics.like_count")
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_id,
        content_type="note",
        title=title,
        text=text,
        author=author,
        metrics=CanonicalMetricsV1(like_count=like_count),
        observed_at=source.observed_at,
        source=source,
        observed_fields=fields,
    )


def test_historical_bulk_fill_only_preserves_nonempty_current_and_metrics(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 26, 8, 0, tzinfo=UTC)
    session = database_runtime.new_session()
    try:
        with session.begin():
            batch_id, item_id, artifact_id = _setup_batch(session, observed_at=observed_at)
            source = _historical_source(
                session,
                batch_id=batch_id,
                artifact_id=artifact_id,
                observed_at=observed_at,
            )
            live = _content(
                source=source,
                external_id="existing",
                title="在线标题",
                text=None,
                author_name="在线作者",
                like_count=99,
            )
            existing = ContentIngestionService(
                __import__(
                    "aima_ugc.adapters.persistence.postgres.content",
                    fromlist=["PostgresContentRepository"],
                ).PostgresContentRepository(session)
            ).ingest_content(live)
            before = (
                session.execute(
                    select(contents_table).where(contents_table.c.id == existing.target_id)
                )
                .mappings()
                .one()
            )

            historical = _content(
                source=source,
                external_id="existing",
                title="历史冲突标题",
                text="历史正文补空",
                author_name="历史冲突作者",
                author_follower_count=1234,
                like_count=1,
            )
            summary = PostgresHistoricalContentRepository(session).ingest_rows(
                batch_id=batch_id,
                campaign_item_id=item_id,
                chunk_ordinal=0,
                rows=(HistoricalBatchRow(source_row_ordinal=1, content=historical),),
            )

        current = (
            session.execute(select(contents_table).where(contents_table.c.id == existing.target_id))
            .mappings()
            .one()
        )
        ledger = session.execute(select(processing_import_batch_items_table)).mappings().one()
        conflicts = (
            session.execute(
                select(processing_import_batch_item_conflicts_table.c.field_name).order_by(
                    processing_import_batch_item_conflicts_table.c.field_name
                )
            )
            .scalars()
            .all()
        )
        account = (
            session.execute(
                select(accounts_table).where(
                    accounts_table.c.external_account_id == "author-stage12"
                )
            )
            .mappings()
            .one()
        )
        metric_count = (
            session.execute(
                select(content_metric_observations_table.c.id).where(
                    content_metric_observations_table.c.content_id == existing.target_id
                )
            )
            .scalars()
            .all()
        )
        versions = (
            session.execute(
                select(content_versions_table.c.version_no).where(
                    content_versions_table.c.content_id == existing.target_id
                )
            )
            .scalars()
            .all()
        )
    finally:
        session.close()

    assert summary.filled == 1
    assert current["title"] == "在线标题"
    assert current["text"] == "历史正文补空"
    assert current["last_seen_at"] == before["last_seen_at"]
    assert current["current_like_count"] == 99
    assert account["display_name"] == "在线作者"
    assert account["current_follower_count"] is None
    assert ledger["outcome"] == "filled"
    assert ledger["filled_count"] == 1
    assert ledger["conflict_count"] == 2
    assert conflicts == ["author.display_name", "title"]
    assert len(metric_count) == 1
    assert versions == [1, 2]


def test_historical_batch_retry_and_duplicate_rows_have_one_business_effect(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)
    session = database_runtime.new_session()
    try:
        with session.begin():
            batch_id, item_id, artifact_id = _setup_batch(session, observed_at=observed_at)
            source = _historical_source(
                session,
                batch_id=batch_id,
                artifact_id=artifact_id,
                observed_at=observed_at,
            )
            row = _content(
                source=source,
                external_id="new-history",
                title="历史新内容",
                text="正文",
                author_name=None,
                like_count=7,
            )
            repository = PostgresHistoricalContentRepository(session)
            first = repository.ingest_rows(
                batch_id=batch_id,
                campaign_item_id=item_id,
                chunk_ordinal=0,
                rows=(
                    HistoricalBatchRow(source_row_ordinal=1, content=row),
                    HistoricalBatchRow(source_row_ordinal=2, content=row),
                ),
            )
            retry = repository.ingest_rows(
                batch_id=batch_id,
                campaign_item_id=item_id,
                chunk_ordinal=0,
                rows=(
                    HistoricalBatchRow(source_row_ordinal=1, content=row),
                    HistoricalBatchRow(source_row_ordinal=2, content=row),
                ),
            )

        contents = (
            session.execute(
                select(contents_table).where(contents_table.c.external_content_id == "new-history")
            )
            .mappings()
            .all()
        )
        outcomes = (
            session.execute(
                select(processing_import_batch_items_table.c.outcome).order_by(
                    processing_import_batch_items_table.c.source_row_ordinal
                )
            )
            .scalars()
            .all()
        )
        metric_rows = (
            session.execute(select(content_metric_observations_table.c.id)).scalars().all()
        )
    finally:
        session.close()

    assert first.created == 1
    assert first.duplicate == 1
    assert retry.skipped_terminal == 2
    assert len(contents) == 1
    assert outcomes == ["created", "duplicate"]
    assert metric_rows == []


def test_historical_new_author_merges_complementary_fields_in_stable_row_order(
    database_runtime: DatabaseRuntime,
) -> None:
    observed_at = datetime(2026, 8, 26, 10, 0, tzinfo=UTC)
    session = database_runtime.new_session()
    try:
        with session.begin():
            batch_id, item_id, artifact_id = _setup_batch(session, observed_at=observed_at)
            source = _historical_source(
                session,
                batch_id=batch_id,
                artifact_id=artifact_id,
                observed_at=observed_at,
            )
            repository = PostgresHistoricalContentRepository(session)
            repository.ingest_rows(
                batch_id=batch_id,
                campaign_item_id=item_id,
                chunk_ordinal=0,
                rows=(
                    HistoricalBatchRow(
                        source_row_ordinal=1,
                        content=_content(
                            source=source,
                            external_id="author-first",
                            title="爱玛作者首行",
                            text=None,
                            author_name="历史作者",
                        ),
                    ),
                    HistoricalBatchRow(
                        source_row_ordinal=2,
                        content=_content(
                            source=source,
                            external_id="author-second",
                            title="爱玛作者第二行",
                            text=None,
                            author_name=None,
                            author_bio="第二行补充的作者简介",
                        ),
                    ),
                ),
            )
        account = (
            session.execute(
                select(accounts_table).where(
                    accounts_table.c.external_account_id == "author-stage12"
                )
            )
            .mappings()
            .one()
        )
    finally:
        session.close()

    assert account["display_name"] == "历史作者"
    assert account["bio"] == "第二行补充的作者简介"


def test_historical_batch_inserts_contents_with_different_observed_fields(
    database_runtime: DatabaseRuntime,
) -> None:
    """稀疏历史行必须以统一列集批量写入 Content。"""

    observed_at = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)
    session = database_runtime.new_session()
    try:
        with session.begin():
            batch_id, item_id, artifact_id = _setup_batch(session, observed_at=observed_at)
            source = _historical_source(
                session,
                batch_id=batch_id,
                artifact_id=artifact_id,
                observed_at=observed_at,
            )
            summary = PostgresHistoricalContentRepository(session).ingest_rows(
                batch_id=batch_id,
                campaign_item_id=item_id,
                chunk_ordinal=0,
                rows=(
                    HistoricalBatchRow(
                        source_row_ordinal=1,
                        content=_content(
                            source=source,
                            external_id="sparse-title",
                            title="只有标题",
                            text=None,
                            author_name=None,
                        ),
                    ),
                    HistoricalBatchRow(
                        source_row_ordinal=2,
                        content=_content(
                            source=source,
                            external_id="sparse-text",
                            title=None,
                            text="只有正文",
                            author_name=None,
                        ),
                    ),
                ),
            )
        contents = {
            row["external_content_id"]: row
            for row in session.execute(
                select(contents_table).where(
                    contents_table.c.external_content_id.in_(("sparse-title", "sparse-text"))
                )
            ).mappings()
        }
    finally:
        session.close()

    assert summary.created == 2
    assert contents["sparse-title"]["title"] == "只有标题"
    assert contents["sparse-title"]["text"] is None
    assert contents["sparse-text"]["title"] is None
    assert contents["sparse-text"]["text"] == "只有正文"


def test_historical_batch_inserts_authors_with_different_observed_fields(
    database_runtime: DatabaseRuntime,
) -> None:
    """不同作者的稀疏字段必须以统一列集批量写入。"""

    observed_at = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    session = database_runtime.new_session()
    try:
        with session.begin():
            batch_id, item_id, artifact_id = _setup_batch(session, observed_at=observed_at)
            source = _historical_source(
                session,
                batch_id=batch_id,
                artifact_id=artifact_id,
                observed_at=observed_at,
            )
            summary = PostgresHistoricalContentRepository(session).ingest_rows(
                batch_id=batch_id,
                campaign_item_id=item_id,
                chunk_ordinal=0,
                rows=(
                    HistoricalBatchRow(
                        source_row_ordinal=1,
                        content=_content(
                            source=source,
                            external_id="author-name-content",
                            title="作者名称行",
                            text=None,
                            author_name="只有名称",
                            author_external_id="author-with-name",
                        ),
                    ),
                    HistoricalBatchRow(
                        source_row_ordinal=2,
                        content=_content(
                            source=source,
                            external_id="author-bio-content",
                            title="作者简介行",
                            text=None,
                            author_name=None,
                            author_external_id="author-with-bio",
                            author_bio="只有简介",
                        ),
                    ),
                ),
            )
        accounts = {
            row["external_account_id"]: row
            for row in session.execute(
                select(accounts_table).where(
                    accounts_table.c.external_account_id.in_(
                        ("author-with-name", "author-with-bio")
                    )
                )
            ).mappings()
        }
    finally:
        session.close()

    assert summary.created == 2
    assert accounts["author-with-name"]["display_name"] == "只有名称"
    assert accounts["author-with-name"]["bio"] is None
    assert accounts["author-with-bio"]["display_name"] is None
    assert accounts["author-with-bio"]["bio"] == "只有简介"
