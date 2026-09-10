"""旧 Content 重分类在真实 PostgreSQL 与正式 Job Runtime 上的关键回归。"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import (
    PostgresBrandVehicleRepository,
)
from aima_ugc.adapters.persistence.postgres.content_reclassification import (
    PostgresContentReclassificationRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.vehicles import (
    PostgresVehicleCatalogRepository,
)
from aima_ugc.bootstrap.content_reclassification_worker import (
    PostgresContentReclassificationJobExecutor,
)
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.worker import create_job_worker, create_worker_runtime
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.vehicles.content_reclassification import (
    CONTENT_RECLASSIFICATION_JOB_TYPE,
    ContentReclassificationJobHandler,
    ReclassificationBatchCounters,
    register_content_reclassification_job,
)
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_vehicle_evidence_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs import JobExecutionFence, JobRegistry, LeaseLostError
from aima_ugc.platform.time import beijing_now
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

type _Fixture = tuple[
    UUID,
    UUID,
    UUID,
    UUID,
    UUID,
    tuple[UUID, ...],
    int,
]


@pytest.fixture
def runtime() -> Iterator[PlatformRuntime]:
    """隔离本文件拥有的 Content、目录与 Job 数据。"""

    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE contents, vehicle_brands, jobs RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def _insert_content(
    session: Session,
    content_id: UUID,
    *,
    external_id: str,
    title: str,
    body: str,
) -> None:
    now = beijing_now()
    session.execute(
        insert(contents_table).values(
            id=content_id,
            platform="xiaohongshu",
            external_content_id=external_id,
            content_type="note",
            title=title,
            text=body,
            first_seen_at=now,
            last_seen_at=now,
            current_version=1,
            field_observed_at={},
            updated_at=now,
        )
    )


def _enqueue_fixture(runtime: PlatformRuntime) -> _Fixture:
    content_ids = tuple(uuid4() for _ in range(4))
    session = runtime.database.new_session()
    try:
        with session.begin():
            brand_repository = PostgresBrandVehicleRepository(session)
            aima = brand_repository.create_brand(
                code="AIMA-RECLASS",
                display_name="爱玛重分类",
                role="owned",
                aliases=("爱玛",),
                actor_ref="test",
            )
            competitor = brand_repository.create_brand(
                code="COMP-RECLASS",
                display_name="竞品重分类",
                role="competitor",
                aliases=("竞品",),
                actor_ref="test",
            )
            vehicle_repository = PostgresVehicleCatalogRepository(session)
            vehicle = vehicle_repository.create_model(
                code="LUNA-RECLASS",
                display_name="露娜重分类",
                aliases=("露娜Air",),
                actor_ref="test",
                brand_id=aima.id,
            )
            _insert_content(
                session,
                content_ids[0],
                external_id="reclass-brand-title",
                title="爱玛新品发布",
                body="普通正文",
            )
            _insert_content(
                session,
                content_ids[1],
                external_id="reclass-vehicle-body",
                title="普通标题",
                body="露娜Air实际体验",
            )
            _insert_content(
                session,
                content_ids[2],
                external_id="reclass-manual-lock",
                title="爱玛露娜Air",
                body="人工结论必须优先",
            )
            _insert_content(
                session,
                content_ids[3],
                external_id="reclass-existing-vehicle",
                title="无直接别名",
                body="仅依赖既有车型证据",
            )
            brand_repository.replace_manual_brand_evidence(
                content_id=content_ids[2],
                content_version=1,
                brand_ids=(competitor.id,),
                unlock_existing=False,
                actor_ref="reviewer",
            )
            vehicle_repository.replace_manual_evidence(
                content_id=content_ids[2],
                content_version=1,
                model_ids=(),
                unlock_existing=False,
                actor_ref="reviewer",
            )
            vehicle_repository.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_ids[3],
                    content_version=1,
                    vehicle_model_id=vehicle.id,
                    source="import",
                    matched_text="历史车型列",
                    source_field="vehicle_model",
                    catalog_version=vehicle_repository.current_catalog_version(),
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )
            vehicle_repository.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_ids[0],
                    content_version=1,
                    vehicle_model_id=vehicle.id,
                    source="alias_match",
                    matched_text="旧目录误命中",
                    source_field="text",
                    catalog_version=vehicle_repository.current_catalog_version(),
                    confidence=1.0,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )
            repository = PostgresContentReclassificationRepository(session)
            run, job = repository.enqueue(
                idempotency_key="stage7-postgres-golden",
                shard_index=0,
                shard_count=1,
                start_after_content_id=None,
                end_at_content_id=None,
                batch_size=1,
                max_contents=100,
                created_by="test",
                request_id="stage7-postgres-golden",
            )
            duplicate_run, duplicate_job = repository.enqueue(
                idempotency_key="stage7-postgres-golden",
                shard_index=0,
                shard_count=1,
                start_after_content_id=None,
                end_at_content_id=None,
                batch_size=1,
                max_contents=100,
                created_by="test",
                request_id="stage7-postgres-golden",
            )
            assert duplicate_run.id == run.id
            assert duplicate_job.id == job.id
            with pytest.raises(
                RuntimeError,
                match="idempotency_key 已绑定不同的重分类范围或参数",
            ):
                repository.enqueue(
                    idempotency_key="stage7-postgres-golden",
                    shard_index=0,
                    shard_count=2,
                    start_after_content_id=None,
                    end_at_content_id=None,
                    batch_size=1,
                    max_contents=100,
                    created_by="test",
                    request_id="stage7-postgres-golden",
                )
            frozen_catalog_version = run.catalog_snapshot.catalog_version
    finally:
        session.close()

    session = runtime.database.new_session()
    try:
        with session.begin():
            PostgresBrandVehicleRepository(session).add_brand_alias(
                competitor.id,
                text="爱玛",
                actor_ref="post-snapshot-change",
            )
    finally:
        session.close()
    return run.id, job.id, aima.id, competitor.id, vehicle.id, content_ids, frozen_catalog_version


def test_reclassification_job_uses_frozen_snapshot_preserves_locks_and_current(runtime) -> None:  # type: ignore[no-untyped-def]
    """正式 Worker 分批写 Evidence，并保留人工锁与 Content Current。"""

    run_id, job_id, aima_id, competitor_id, vehicle_id, content_ids, frozen_version = (
        _enqueue_fixture(runtime)
    )
    registry = JobRegistry()
    register_content_reclassification_job(
        registry,
        ContentReclassificationJobHandler(PostgresContentReclassificationJobExecutor(runtime)),
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id="stage7-reclassification-test",
        lease_seconds=30,
        retry_delay_seconds=0,
    )

    assert worker.run_once() is True

    session = runtime.database.new_session()
    try:
        with session.begin():
            run = PostgresContentReclassificationRepository(session).get(run_id)
            job = PostgresJobRepository(session).get(job_id)
            assert run is not None
            assert job is not None
            assert job.status == "succeeded"
            assert job.progress == 100
            assert run.catalog_snapshot.catalog_version == frozen_version
            assert run.processed_count == 4
            assert run.matched_count == 4
            assert run.unmatched_count == 0
            assert run.checkpoint_content_id == max(content_ids)
            assert run.brand_locked_count == 1
            assert run.vehicle_locked_count == 1

            brand_rows = tuple(
                session.execute(
                    select(
                        content_brand_evidence_table.c.content_id,
                        content_brand_evidence_table.c.brand_id,
                        content_brand_evidence_table.c.source,
                        content_brand_evidence_table.c.derived_vehicle_model_id,
                        content_brand_evidence_table.c.is_manual_locked,
                    ).where(content_brand_evidence_table.c.is_active.is_(True))
                )
            )
            vehicle_rows = tuple(
                session.execute(
                    select(
                        content_vehicle_evidence_table.c.content_id,
                        content_vehicle_evidence_table.c.vehicle_model_id,
                        content_vehicle_evidence_table.c.source,
                    ).where(content_vehicle_evidence_table.c.is_active.is_(True))
                )
            )
            current_rows = {
                row.id: (row.current_version, row.title, row.text)
                for row in session.execute(
                    select(
                        contents_table.c.id,
                        contents_table.c.current_version,
                        contents_table.c.title,
                        contents_table.c.text,
                    )
                )
            }
    finally:
        session.close()

    assert (content_ids[0], aima_id, "alias_match", None, False) in brand_rows
    assert (content_ids[1], aima_id, "vehicle_match", vehicle_id, False) in brand_rows
    assert (content_ids[2], competitor_id, "manual_review", None, True) in brand_rows
    assert not any(row[0] == content_ids[2] and row[1] == aima_id for row in brand_rows)
    assert (content_ids[3], aima_id, "vehicle_match", vehicle_id, False) in brand_rows
    assert (content_ids[1], vehicle_id, "alias_match") in vehicle_rows
    assert not any(row[0] == content_ids[0] for row in vehicle_rows)
    assert not any(row[0] == content_ids[2] for row in vehicle_rows)
    assert (content_ids[3], vehicle_id, "import") in vehicle_rows
    assert current_rows[content_ids[0]] == (1, "爱玛新品发布", "普通正文")
    assert current_rows[content_ids[2]] == (1, "爱玛露娜Air", "人工结论必须优先")


def test_reclassification_checkpoint_rejects_stale_fence_atomically(runtime) -> None:  # type: ignore[no-untyped-def]
    """接管后旧 Token 不能推进检查点或累计统计。"""

    run_id, job_id, *_ = _enqueue_fixture(runtime)
    first = runtime.database.new_session()
    try:
        with first.begin():
            old_claim = PostgresJobRepository(first).claim_next(
                supported_job_types=(CONTENT_RECLASSIFICATION_JOB_TYPE,),
                worker_id="old-worker",
                lease_seconds=30,
            )
            assert old_claim is not None
            assert old_claim.lease_token is not None
    finally:
        first.close()

    with runtime.database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE jobs SET lease_expires_at = clock_timestamp() - interval '1 second' "
                "WHERE id = :job_id"
            ),
            {"job_id": job_id},
        )
    second = runtime.database.new_session()
    try:
        with second.begin():
            takeover = PostgresJobRepository(second).claim_next(
                supported_job_types=(CONTENT_RECLASSIFICATION_JOB_TYPE,),
                worker_id="new-worker",
                lease_seconds=30,
            )
            assert takeover is not None
            assert takeover.lease_token != old_claim.lease_token
    finally:
        second.close()

    stale = runtime.database.new_session()
    try:
        with pytest.raises(LeaseLostError):
            with stale.begin():
                PostgresContentReclassificationRepository(stale).advance(
                    run_id=run_id,
                    checkpoint_content_id=uuid4(),
                    counters=ReclassificationBatchCounters(
                        processed_count=1,
                        matched_count=1,
                        unmatched_count=0,
                        brand_evidence_count=1,
                        vehicle_evidence_count=0,
                        conflict_count=0,
                        brand_locked_count=0,
                        vehicle_locked_count=0,
                    ),
                    fence=JobExecutionFence(
                        job_id=job_id,
                        lease_token=old_claim.lease_token,
                    ),
                )
        with stale.begin():
            run = PostgresContentReclassificationRepository(stale).get(run_id)
            assert run is not None
            assert run.checkpoint_content_id is None
            assert run.processed_count == 0
    finally:
        stale.close()
