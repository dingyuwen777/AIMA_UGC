"""Collection live runtime 的 Content previous-state 与 Fenced Ingestion 集成测试。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, select

from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresCollectionContentStateReader,
    PostgresFencedCollectionIngestionWriter,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.account_tables import account_external_ids_table
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
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage.tables import artifacts_table

_NOW = datetime(2026, 8, 17, 1, 15, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _LiveSource:
    job_id: UUID
    scope_id: UUID
    request_id: UUID
    attempt_id: UUID
    artifact_id: UUID
    fence: JobExecutionFence


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        _clear_data(connection)
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            _clear_data(connection)
        runtime.dispose()


def _clear_data(connection) -> None:
    connection.execute(delete(collection_candidate_ingestions_table))
    connection.execute(delete(collection_candidates_table))
    connection.execute(delete(comment_metric_observations_table))
    connection.execute(delete(comment_versions_table))
    connection.execute(delete(comments_table))
    connection.execute(delete(content_metric_observations_table))
    connection.execute(delete(content_versions_table))
    connection.execute(delete(contents_table))
    connection.execute(delete(account_external_ids_table))
    connection.execute(delete(accounts_table))
    connection.execute(delete(provider_request_attempts_table))
    connection.execute(delete(provider_requests_table))
    connection.execute(delete(collection_scopes_table))
    connection.execute(delete(collection_runs_table))
    connection.execute(delete(artifacts_table))
    connection.execute(delete(job_attempt_events_table))
    connection.execute(delete(jobs_table))


def _create_live_source(runtime: DatabaseRuntime, *, source_value: str) -> _LiveSource:
    session = runtime.new_session()
    request_id = uuid4()
    attempt_id = uuid4()
    artifact_id = uuid4()
    try:
        with session.begin():
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"content-runtime:{uuid4().hex}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            execution = CollectionExecutionService(
                PostgresCollectionRepository(session)
            ).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot={"schema_version": "collection-run-config.v1"},
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value=source_value,
                        operation_group="content_discovery",
                    ),
                ),
            )
            scope = execution.scopes[0]
            session.execute(
                insert(artifacts_table).values(
                    id=artifact_id,
                    kind="provider-raw",
                    storage_backend="local",
                    storage_key=f"raw/content-runtime/{artifact_id}.json.gz",
                    content_type="application/json",
                    encoding="gzip",
                    sha256="a" * 64,
                    byte_size=1,
                    retention_class="raw",
                    storage_status="linked",
                    created_at=_NOW,
                    stored_at=_NOW,
                    linked_at=_NOW + timedelta(seconds=1),
                )
            )
            session.execute(
                insert(provider_requests_table).values(
                    id=request_id,
                    scope_id=scope.id,
                    provider="tikhub",
                    operation="search_notes",
                    request_fingerprint=attempt_id.hex * 2,
                    request_params={"keyword": source_value},
                    pagination_input={},
                    status="completed",
                    attempt_count=1,
                    created_at=_NOW,
                    completed_at=_NOW + timedelta(seconds=1),
                )
            )
            session.execute(
                insert(provider_request_attempts_table).values(
                    id=attempt_id,
                    provider_request_id=request_id,
                    attempt_no=1,
                    dispatch_status="completed",
                    dispatch_started_at=_NOW,
                    completed_at=_NOW + timedelta(seconds=1),
                    http_status=200,
                    raw_artifact_id=artifact_id,
                    billing_status="not_billable",
                    created_at=_NOW,
                )
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id=f"content-runtime-{job.id}",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.id == job.id and claimed.lease_token is not None
        return _LiveSource(
            job_id=job.id,
            scope_id=scope.id,
            request_id=request_id,
            attempt_id=attempt_id,
            artifact_id=artifact_id,
            fence=JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token),
        )
    finally:
        session.close()


def _canonical(source: _LiveSource, *, external_content_id: str = "note-runtime-1") -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xhs",
        external_content_id=external_content_id,
        content_type="image",
        title="标题 A",
        text="正文 A",
        observed_at=_NOW,
        metrics=CanonicalMetricsV1(like_count=10, comment_count=1, favorite_count=2),
        status="active",
        source=CanonicalSourceV1(
            provider_name="tikhub",
            operation="search_notes",
            provider_request_id=str(source.request_id),
            provider_attempt_id=str(source.attempt_id),
            raw_artifact_id=source.artifact_id,
            source_type="keyword_search",
            source_value="爱玛",
            item_locator=f"note:{external_content_id}",
            observed_at=_NOW,
        ),
        observed_fields=[
            "content_type",
            "title",
            "text",
            "metrics.like_count",
            "metrics.comment_count",
            "metrics.favorite_count",
            "status",
        ],
    )


def test_current_fence_ingests_candidate_and_content_atomically(
    database_runtime: DatabaseRuntime,
) -> None:
    source = _create_live_source(database_runtime, source_value="爱玛")
    canonical = _canonical(source)

    result = PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
        canonical=canonical,
        fence=source.fence,
    )

    session = database_runtime.new_session()
    try:
        with session.begin():
            content_row = (
                session.execute(
                    select(contents_table).where(contents_table.c.id == result.target_id)
                )
                .mappings()
                .one()
            )
            candidate_attempt = session.scalar(
                select(collection_candidates_table.c.provider_request_attempt_id)
            )
            ingestion_target = session.scalar(
                select(collection_candidate_ingestions_table.c.content_id)
            )
        assert content_row["external_content_id"] == canonical.external_content_id
        assert candidate_attempt == source.attempt_id
        assert ingestion_target == result.target_id
    finally:
        session.close()


def test_stale_fence_cannot_write_candidate_or_content(
    database_runtime: DatabaseRuntime,
) -> None:
    source = _create_live_source(database_runtime, source_value="爱玛")
    stale = JobExecutionFence(job_id=source.job_id, lease_token="stale-token")

    with pytest.raises(LeaseLostError):
        PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
            canonical=_canonical(source),
            fence=stale,
        )

    session = database_runtime.new_session()
    try:
        with session.begin():
            assert session.scalar(select(collection_candidates_table.c.id).limit(1)) is None
            assert session.scalar(select(contents_table.c.id).limit(1)) is None
    finally:
        session.close()


def test_valid_fence_cannot_ingest_attempt_owned_by_another_job(
    database_runtime: DatabaseRuntime,
) -> None:
    first = _create_live_source(database_runtime, source_value="爱玛")
    second = _create_live_source(database_runtime, source_value="电动车")

    with pytest.raises(LeaseLostError):
        PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
            canonical=_canonical(second),
            fence=first.fence,
        )

    session = database_runtime.new_session()
    try:
        with session.begin():
            assert session.scalar(select(collection_candidates_table.c.id).limit(1)) is None
            assert session.scalar(select(contents_table.c.id).limit(1)) is None
    finally:
        session.close()


def test_content_state_reader_separates_comment_count_from_other_business_change(
    database_runtime: DatabaseRuntime,
) -> None:
    source = _create_live_source(database_runtime, source_value="爱玛")
    canonical = _canonical(source)
    PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
        canonical=canonical,
        fence=source.fence,
    )
    reader = PostgresCollectionContentStateReader(database_runtime.new_session)

    same = reader.evaluate(canonical)
    assert same is not None
    assert same.previous.comment_count == 1
    assert same.business_changed is False

    comment_only = canonical.model_copy(
        update={"metrics": canonical.metrics.model_copy(update={"comment_count": 2})}
    )
    comment_state = reader.evaluate(comment_only)
    assert comment_state is not None
    assert comment_state.previous.comment_count == 1
    assert comment_state.business_changed is False

    likes_changed = canonical.model_copy(
        update={"metrics": canonical.metrics.model_copy(update={"like_count": 11})}
    )
    like_state = reader.evaluate(likes_changed)
    assert like_state is not None
    assert like_state.business_changed is True

    title_not_observed = canonical.model_copy(
        update={
            "title": "标题 B",
            "observed_fields": [
                field for field in canonical.observed_fields if field != "title"
            ],
        }
    )
    title_state = reader.evaluate(title_not_observed)
    assert title_state is not None
    assert title_state.business_changed is False
