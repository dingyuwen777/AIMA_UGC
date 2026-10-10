"""Collection live runtime 的 Content previous-state 与 Fenced Ingestion 集成测试。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.collection import PostgresCollectionRepository
from aima_ugc.adapters.persistence.postgres.collection_content import (
    CollectionContentIdentityConflictError,
    PostgresCollectionContentStateReader,
    PostgresFencedCollectionIngestionWriter,
)
from aima_ugc.adapters.persistence.postgres.content_queries import PostgresContentQueryRepository
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.contracts.canonical import (
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.execution import (
    CollectionExecutionService,
    CollectionScopeDefinition,
)
from aima_ugc.modules.collection.tables import (
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.query import ContentReadQuery
from aima_ugc.modules.content.read_model_tables import voice_plaza_projection_state_table
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.vehicles.brand_vehicle import BrandVehicleResolver
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_brand_review_locks_table,
    content_vehicle_review_locks_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

_NOW = datetime(2026, 8, 17, 1, 15, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _LiveSource:
    job_id: UUID
    scope_id: UUID
    request_id: UUID
    attempt_id: UUID
    artifact_id: UUID
    source_value: str
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


def _clear_data(connection: Connection) -> None:
    """测试数据库专用清理；TRUNCATE 不改变生产 append-only UPDATE/DELETE Trigger。"""
    connection.exec_driver_sql("TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE")


def _create_live_source(
    runtime: DatabaseRuntime, *, source_value: str, enrichment: bool = False, account: bool = False
) -> _LiveSource:
    """建立真实 Fence/Attempt 来源；补采场景使用正式 content_enrichment Scope。"""
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
                config_snapshot={
                    "plan_type": "tikhub",
                    "comment_policy": "adaptive",
                    "decision_policy": {"comment_mode": "adaptive"},
                    "schema_version": "collection-run-config.v5"
                    if account
                    else "collection-run-config.v4",
                    **(
                        {
                            "mode": "account_discovery",
                            "account_selection": {
                                "kind": "accounts",
                                "accounts": [
                                    {
                                        "platform": "xiaohongshu",
                                        "account_id_type": "user_id",
                                        "account_id": "synthetic-user",
                                    }
                                ],
                                "published_from": "2026-10-01T00:00:00+08:00",
                                "published_to": "2026-10-09T23:59:59+08:00",
                            },
                        }
                        if account
                        else {}
                    ),
                },
                scopes=(
                    CollectionScopeDefinition(
                        platform="xiaohongshu",
                        source_type="account"
                        if account
                        else "content"
                        if enrichment
                        else "keyword_search",
                        source_value=source_value,
                        operation_group="content_enrichment" if enrichment else "content_discovery",
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
            source_value=source_value,
            fence=JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token),
        )
    finally:
        session.close()


def _canonical(
    source: _LiveSource,
    *,
    external_content_id: str | None = None,
) -> CanonicalContentV1:
    content_id = external_content_id or f"note-runtime-{source.attempt_id}"
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=content_id,
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
            source_value=source.source_value,
            item_locator=f"note:{content_id}",
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


def _candidate_id_for_attempt(runtime: DatabaseRuntime, attempt_id: UUID) -> UUID | None:
    session = runtime.new_session()
    try:
        with session.begin():
            return session.scalar(
                select(collection_candidates_table.c.id)
                .where(collection_candidates_table.c.provider_request_attempt_id == attempt_id)
                .limit(1)
            )
    finally:
        session.close()


def _content_id_for_external(
    runtime: DatabaseRuntime,
    external_content_id: str,
) -> UUID | None:
    session = runtime.new_session()
    try:
        with session.begin():
            return session.scalar(
                select(contents_table.c.id)
                .where(
                    contents_table.c.platform == "xiaohongshu",
                    contents_table.c.external_content_id == external_content_id,
                )
                .limit(1)
            )
    finally:
        session.close()


@pytest.mark.parametrize("account", [False, True])
def test_supplement_reclassifies_merged_current_and_accepts_empty_evidence(
    database_runtime: DatabaseRuntime,
    account: bool,
) -> None:
    """稀疏详情沿用完整正文，无命中仍入库；重试不重复当前品牌证据。"""
    source = _create_live_source(
        database_runtime, source_value="supplement", enrichment=not account, account=account
    )
    brand_alias = f"补采{uuid4().hex}"
    with database_runtime.new_session() as session, session.begin():
        repository = PostgresBrandVehicleRepository(session)
        brand = repository.create_brand(
            code=f"SUPPLEMENT-{uuid4()}",
            display_name=brand_alias,
            role="owned",
            aliases=(brand_alias,),
            actor_ref="test",
        )
        snapshot = repository.snapshot(brand_ids=None)
    writer = PostgresFencedCollectionIngestionWriter(database_runtime.new_session)
    initial = _canonical(source).model_copy(update={"title": f"{brand_alias} 原标题"})
    first = writer.ingest_content(canonical=initial, fence=source.fence)
    sparse = initial.model_copy(
        update={
            "title": None,
            "text": None,
            "share_url": "https://example.com/supplement",
            "observed_fields": ["share_url"],
            "observed_at": _NOW + timedelta(seconds=1),
        }
    )
    empty = BrandVehicleResolver().resolve(
        snapshot, title=None, raw_text=None, transcript_text=None
    )
    second = writer.ingest_content(
        canonical=sparse,
        fence=source.fence,
        brand_vehicle_snapshot=snapshot,
        brand_vehicle_resolution=empty,
    )
    assert second.target_id == first.target_id and second.version_no == 2
    writer.ingest_content(
        canonical=sparse,
        fence=source.fence,
        brand_vehicle_snapshot=snapshot,
        brand_vehicle_resolution=empty,
    )
    with database_runtime.new_session() as session, session.begin():
        rows = (
            session.execute(
                select(content_brand_evidence_table).where(
                    content_brand_evidence_table.c.content_id == first.target_id,
                    content_brand_evidence_table.c.content_version == 2,
                    content_brand_evidence_table.c.is_active,
                )
            )
            .mappings()
            .all()
        )
        assert [row["brand_id"] for row in rows] == [brand.id]
        assert rows[0]["source_field"] == "title"
        assert rows[0]["catalog_version"] == snapshot.catalog_version
    removed = sparse.model_copy(
        update={
            "title": "没有目录品牌的正文",
            "observed_fields": ["title"],
            "observed_at": _NOW + timedelta(seconds=2),
        }
    )
    third = writer.ingest_content(
        canonical=removed,
        fence=source.fence,
        brand_vehicle_snapshot=snapshot,
        brand_vehicle_resolution=empty,
    )
    assert third.version_no == 3
    with database_runtime.new_session() as session, session.begin():
        assert (
            session.scalar(
                select(func.count())
                .select_from(content_brand_evidence_table)
                .where(
                    content_brand_evidence_table.c.content_id == first.target_id,
                    content_brand_evidence_table.c.content_version == 3,
                    content_brand_evidence_table.c.is_active,
                )
            )
            == 0
        )
        assert session.scalar(select(contents_table.c.current_version)) == 3


@pytest.mark.parametrize("changed_field", ("title", "text"))
def test_supplement_adds_new_brand_from_changed_current_field(
    database_runtime: DatabaseRuntime, changed_field: str
) -> None:
    """已有帖子后来出现新品牌时，按新 Current 保留所有品牌及实际命中字段。"""
    source = _create_live_source(database_runtime, source_value="new-brand", enrichment=True)
    old_alias = f"原有品牌{uuid4().hex}"
    new_alias = f"新增品牌{uuid4().hex}"
    with database_runtime.new_session() as session, session.begin():
        repository = PostgresBrandVehicleRepository(session)
        old_brand = repository.create_brand(
            code=f"ORIGINAL-{uuid4()}",
            display_name=old_alias,
            role="owned",
            aliases=(old_alias,),
            actor_ref="test",
        )
        new_brand = repository.create_brand(
            code=f"NEW-{uuid4()}",
            display_name=new_alias,
            role="competitor",
            aliases=(new_alias,),
            actor_ref="test",
        )
        snapshot = repository.snapshot(brand_ids=None)
    empty = BrandVehicleResolver().resolve(
        snapshot, title=None, raw_text=None, transcript_text=None
    )
    writer = PostgresFencedCollectionIngestionWriter(database_runtime.new_session)
    initial = _canonical(source).model_copy(update={"title": old_alias})
    first = writer.ingest_content(
        canonical=initial,
        fence=source.fence,
        brand_vehicle_snapshot=snapshot,
        brand_vehicle_resolution=empty,
    )
    with database_runtime.new_session() as session, session.begin():
        assert set(
            session.scalars(
                select(content_brand_evidence_table.c.brand_id).where(
                    content_brand_evidence_table.c.content_id == first.target_id,
                    content_brand_evidence_table.c.content_version == first.version_no,
                    content_brand_evidence_table.c.is_active,
                )
            )
        ) == {old_brand.id}
    changed = initial.model_copy(
        update={
            changed_field: f"{old_alias} {new_alias}" if changed_field == "title" else new_alias,
            "observed_fields": [changed_field],
            "observed_at": _NOW + timedelta(seconds=1),
        }
    )
    supplemented = writer.ingest_content(
        canonical=changed,
        fence=source.fence,
        brand_vehicle_snapshot=snapshot,
        brand_vehicle_resolution=empty,
        expected_content_id=first.target_id,
    )
    assert supplemented.target_id == first.target_id
    assert supplemented.version_no == first.version_no + 1
    with database_runtime.new_session() as session, session.begin():
        evidence = (
            session.execute(
                select(content_brand_evidence_table).where(
                    content_brand_evidence_table.c.content_id == first.target_id,
                    content_brand_evidence_table.c.content_version == supplemented.version_no,
                    content_brand_evidence_table.c.is_active,
                )
            )
            .mappings()
            .all()
        )
        assert {row["brand_id"] for row in evidence} == {old_brand.id, new_brand.id}
        added = next(row for row in evidence if row["brand_id"] == new_brand.id)
        assert added["source_field"] == ("title" if changed_field == "title" else "raw_text")
        assert added["matched_text"] == new_alias
        assert added["catalog_version"] == snapshot.catalog_version


def test_discovery_does_not_accept_empty_brand_resolution(
    database_runtime: DatabaseRuntime,
) -> None:
    """空分类结果只放行明确的详情补采来源，不放宽 Discovery Filter。"""
    source = _create_live_source(database_runtime, source_value="discovery")
    with database_runtime.new_session() as session, session.begin():
        snapshot = PostgresBrandVehicleRepository(session).snapshot(brand_ids=None)
    empty = BrandVehicleResolver().resolve(
        snapshot, title=None, raw_text=None, transcript_text=None
    )
    with pytest.raises(ValueError):
        PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
            canonical=_canonical(source),
            fence=source.fence,
            brand_vehicle_snapshot=snapshot,
            brand_vehicle_resolution=empty,
        )
    assert (
        _content_id_for_external(database_runtime, _canonical(source).external_content_id) is None
    )


@pytest.mark.parametrize("empty_manual", [False, True])
def test_supplement_carries_manual_brand_and_empty_vehicle_locks(
    database_runtime: DatabaseRuntime, empty_manual: bool
) -> None:
    """人工品牌选择及人工空车型锁随版本继承，自动解析不能覆盖。"""
    source = _create_live_source(database_runtime, source_value="manual", enrichment=True)
    writer = PostgresFencedCollectionIngestionWriter(database_runtime.new_session)
    initial = _canonical(source)
    first = writer.ingest_content(canonical=initial, fence=source.fence)
    with database_runtime.new_session() as session, session.begin():
        brands = PostgresBrandVehicleRepository(session)
        brand = brands.create_brand(
            code=f"MANUAL-{uuid4()}",
            display_name=f"人工{uuid4().hex}",
            role="owned",
            aliases=(),
            actor_ref="test",
        )
        PostgresVehicleCatalogRepository(session).replace_manual_evidence(
            content_id=first.target_id,
            content_version=1,
            model_ids=(),
            unlock_existing=False,
            actor_ref="reviewer",
        )
        brands.replace_manual_brand_evidence(
            content_id=first.target_id,
            content_version=1,
            brand_ids=() if empty_manual else (brand.id,),
            unlock_existing=False,
            actor_ref="reviewer",
        )
        snapshot = brands.snapshot(brand_ids=None)
    changed = initial.model_copy(
        update={
            "title": "更新后没有品牌",
            "observed_at": _NOW + timedelta(seconds=1),
        }
    )
    resolution = BrandVehicleResolver().resolve(
        snapshot, title=changed.title, raw_text=changed.text, transcript_text=None
    )
    second = writer.ingest_content(
        canonical=changed,
        fence=source.fence,
        brand_vehicle_snapshot=snapshot,
        brand_vehicle_resolution=resolution,
    )
    with database_runtime.new_session() as session, session.begin():
        for table in (content_brand_review_locks_table, content_vehicle_review_locks_table):
            assert (
                session.scalar(
                    select(table.c.is_locked).where(
                        table.c.content_id == second.target_id,
                        table.c.content_version == 2,
                    )
                )
                is True
            )
        active = (
            session.execute(
                select(content_brand_evidence_table).where(
                    content_brand_evidence_table.c.content_id == second.target_id,
                    content_brand_evidence_table.c.content_version == 2,
                    content_brand_evidence_table.c.is_active,
                )
            )
            .mappings()
            .all()
        )
        assert {row["brand_id"] for row in active} == (set() if empty_manual else {brand.id})
        assert all(row["source"] == "manual_review" for row in active)


def test_supplement_evidence_failure_rolls_back_version_and_ingestion(
    database_runtime: DatabaseRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content 已变更后 Evidence Owner 抛错，原版本和来源账本仍整体保持原状。"""
    source = _create_live_source(database_runtime, source_value="rollback", enrichment=True)
    writer = PostgresFencedCollectionIngestionWriter(database_runtime.new_session)
    initial = _canonical(source)
    first = writer.ingest_content(canonical=initial, fence=source.fence)
    with database_runtime.new_session() as session, session.begin():
        snapshot = PostgresBrandVehicleRepository(session).snapshot(brand_ids=None)
        ingestion_count = session.scalar(
            select(func.count()).select_from(collection_candidate_ingestions_table)
        )
    changed = initial.model_copy(
        update={
            "title": "失败的新版本",
            "observed_at": _NOW + timedelta(seconds=1),
        }
    )
    resolution = BrandVehicleResolver().resolve(
        snapshot, title=changed.title, raw_text=changed.text, transcript_text=None
    )

    def fail_after_content(*args: object, **kwargs: object) -> None:
        """在生产 Owner 的事务中模拟数据库派生写入失败。"""
        raise RuntimeError("evidence-write-failure")

    monkeypatch.setattr(
        PostgresBrandVehicleRepository,
        "converge_automatic_brand_evidence_for_replay",
        fail_after_content,
    )
    with pytest.raises(RuntimeError, match="evidence-write-failure"):
        writer.ingest_content(
            canonical=changed,
            fence=source.fence,
            brand_vehicle_snapshot=snapshot,
            brand_vehicle_resolution=resolution,
        )
    with database_runtime.new_session() as session, session.begin():
        assert (
            session.scalar(
                select(contents_table.c.current_version).where(
                    contents_table.c.id == first.target_id
                )
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(content_versions_table)) == 1
        assert (
            session.scalar(select(func.count()).select_from(collection_candidate_ingestions_table))
            == ingestion_count
        )


def test_supplement_wrong_content_identity_rolls_back_before_commit(
    database_runtime: DatabaseRuntime,
) -> None:
    """详情映射到错误主身份时，在同一入库事务撤销新 Content 与 Candidate。"""
    source = _create_live_source(database_runtime, source_value="identity", enrichment=True)
    with pytest.raises(CollectionContentIdentityConflictError):
        PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
            canonical=_canonical(source),
            fence=source.fence,
            expected_content_id=uuid4(),
        )
    assert _candidate_id_for_attempt(database_runtime, source.attempt_id) is None
    assert (
        _content_id_for_external(database_runtime, _canonical(source).external_content_id) is None
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
            candidate_id = session.scalar(
                select(collection_candidates_table.c.id).where(
                    collection_candidates_table.c.provider_request_attempt_id == source.attempt_id
                )
            )
            assert candidate_id is not None
            ingestion_target = session.scalar(
                select(collection_candidate_ingestions_table.c.content_id).where(
                    collection_candidate_ingestions_table.c.candidate_id == candidate_id
                )
            )
        assert content_row["external_content_id"] == canonical.external_content_id
        assert ingestion_target == result.target_id
    finally:
        session.close()


def test_stale_fence_cannot_write_candidate_or_content(
    database_runtime: DatabaseRuntime,
) -> None:
    source = _create_live_source(database_runtime, source_value="爱玛")
    canonical = _canonical(source)
    stale = JobExecutionFence(job_id=source.job_id, lease_token="stale-token")

    with pytest.raises(LeaseLostError):
        PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
            canonical=canonical,
            fence=stale,
        )

    assert _candidate_id_for_attempt(database_runtime, source.attempt_id) is None
    assert _content_id_for_external(database_runtime, canonical.external_content_id) is None


def test_valid_fence_cannot_ingest_attempt_owned_by_another_job(
    database_runtime: DatabaseRuntime,
) -> None:
    first = _create_live_source(database_runtime, source_value="爱玛")
    second = _create_live_source(database_runtime, source_value="电动车")
    canonical = _canonical(second)

    with pytest.raises(LeaseLostError):
        PostgresFencedCollectionIngestionWriter(database_runtime.new_session).ingest_content(
            canonical=canonical,
            fence=first.fence,
        )

    assert _candidate_id_for_attempt(database_runtime, second.attempt_id) is None
    assert _content_id_for_external(database_runtime, canonical.external_content_id) is None


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
            "observed_fields": [field for field in canonical.observed_fields if field != "title"],
        }
    )
    title_state = reader.evaluate(title_not_observed)
    assert title_state is not None
    assert title_state.business_changed is False


@pytest.mark.parametrize("projection_status", ["pending", "ready"])
def test_repeated_unchanged_content_remains_in_each_collection_run_result(
    database_runtime: DatabaseRuntime, projection_status: str
) -> None:
    """重复采集保留来源结果，但不能为建立关联伪造新的业务版本。"""
    first = _create_live_source(database_runtime, source_value="首次采集")
    second = _create_live_source(database_runtime, source_value="重复补采")
    unrelated = _create_live_source(database_runtime, source_value="未入库任务")
    writer = PostgresFencedCollectionIngestionWriter(database_runtime.new_session)
    original = writer.ingest_content(
        canonical=_canonical(first, external_content_id="repeated-note"), fence=first.fence
    )
    repeated = writer.ingest_content(
        canonical=_canonical(second, external_content_id="repeated-note"), fence=second.fence
    )
    assert repeated.target_id == original.target_id
    session = database_runtime.new_session()
    try:
        # 只在当前读取事务切换回填状态，关闭 Session 时恢复测试前的状态。
        session.execute(update(voice_plaza_projection_state_table).values(status=projection_status))
        assert (
            session.scalar(
                select(func.count())
                .select_from(content_versions_table)
                .where(content_versions_table.c.content_id == original.target_id)
            )
            == 1
        )
        repository = PostgresContentQueryRepository(session, analysis_identity=None)
        for source, expected_ids in (
            (first, (original.target_id,)),
            (second, (original.target_id,)),
            (unrelated, ()),
        ):
            run_id = session.scalar(
                select(collection_scopes_table.c.run_id).where(
                    collection_scopes_table.c.id == source.scope_id
                )
            )
            filters = ContentFilterSnapshot(source_identifier=run_id)
            records = repository.list_contents(
                ContentReadQuery(filters=filters, position=None, limit=20)
            )
            assert tuple(item.id for item in records) == expected_ids, source.source_value
            assert repository.last_projection_ready is (projection_status == "ready")
            assert (
                tuple(target.content_id for target in repository.freeze_targets(filters=filters))
                == expected_ids
            )
            if projection_status == "ready":
                assert repository.projection_count(filters) == len(expected_ids)
    finally:
        session.close()
