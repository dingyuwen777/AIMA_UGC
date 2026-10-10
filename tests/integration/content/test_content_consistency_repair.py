"""历史一致性修复使用正式规则、有限目标和持久 Job 的回归。"""

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.collection_content import (
    PostgresFencedCollectionIngestionWriter,
)
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.content_consistency_repair import (
    PostgresContentConsistencyRepairRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.adapters.persistence.postgres.voice_plaza_projection import (
    defer_voice_plaza_projection,
)
from aima_ugc.bootstrap.content_consistency_repair_worker import (
    PostgresContentConsistencyRepairExecutor,
)
from aima_ugc.bootstrap.worker import create_collection_job_registry, create_job_worker
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.analysis.tables import (
    analysis_content_results_table,
    analysis_content_runs_table,
    analysis_content_version_reuses_table,
)
from aima_ugc.modules.collection.tables import collection_scopes_table
from aima_ugc.modules.content.consistency_repair import (
    CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,
    ContentConsistencyRepairPayload,
)
from aima_ugc.modules.content.consistency_repair_tables import (
    content_consistency_repair_runs_table,
    content_consistency_repair_targets_table,
)
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.modules.vehicles.tables import (
    content_brand_evidence_table,
    content_brand_review_locks_table,
    content_vehicle_evidence_table,
    content_vehicle_review_locks_table,
)
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from tests.integration.collection.test_collection_content_runtime import (
    _canonical,
    _create_live_source,
)
from tests.integration.content.test_analysis_version_reuse import (  # noqa: F401
    _observe,
)
from tests.integration.content.test_analysis_version_reuse import (
    reuse_runtime as _reuse_runtime,
)
from tests.integration.content.test_content_current_concurrency import _source
from tests.integration.stage3_brand_support import stage3_filter_brand_id

reuse_runtime = _reuse_runtime


def _counts(session):  # type: ignore[no-untyped-def]
    """比对业务事实与运行事实，证明预检或失败没有隐式持久写入。"""
    return tuple(
        session.scalar(select(func.count()).select_from(table))
        for table in (
            jobs_table,
            content_consistency_repair_runs_table,
            content_consistency_repair_targets_table,
            content_versions_table,
            content_brand_evidence_table,
            content_vehicle_evidence_table,
            analysis_content_version_reuses_table,
            analysis_content_results_table,
            analysis_content_runs_table,
        )
    )


def _get_run(runtime, run_id):  # type: ignore[no-untyped-def]
    """从正式持久化事实读取批次进度。"""
    with runtime.database.new_session() as session:
        run = PostgresContentConsistencyRepairRepository(session).get(run_id)
        assert run is not None
        return run


def _damage(runtime, content_id):  # type: ignore[no-untyped-def]
    """模拟已经发生的历史补采缺证，不篡改不可变模型执行结果。"""
    with runtime.database.engine.begin() as connection:
        version = connection.scalar(
            select(contents_table.c.current_version).where(contents_table.c.id == content_id)
        )
        connection.execute(delete(analysis_content_version_reuses_table))
        connection.execute(
            delete(content_brand_evidence_table).where(
                content_brand_evidence_table.c.content_id == content_id,
                content_brand_evidence_table.c.content_version == version,
            )
        )


def _enqueue(runtime, ids, *, key=None, **changes):  # type: ignore[no-untyped-def]
    """通过正式 Owner 原子冻结范围与 Job。"""
    options = dict(
        content_ids=tuple(ids),
        collection_run_id=None,
        max_contents=1000,
        batch_size=2,
        idempotency_key=key or uuid4().hex,
        created_by="repair-test",
    )
    options.update(changes)
    with runtime.database.new_session() as session, session.begin():
        return PostgresContentConsistencyRepairRepository(session).enqueue(**options)


def _worker(runtime):  # type: ignore[no-untyped-def]
    """真实注册的 Worker 领取新协议；模型与 Provider 不参与修复。"""
    return create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(runtime=runtime),
        worker_id="consistency-repair-test",
        lease_seconds=120,
        retry_delay_seconds=0,
        supported_job_types=(CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,),
    )


def _new_contents(runtime, count, *, title="爱玛 修复正文"):  # type: ignore[no-untyped-def]
    """复用生产 Content Owner 批量建立有真实来源的两个版本，无模型结果。"""
    now = beijing_now()
    source = _source(runtime.database, observed_at=now, suffix=uuid4().hex)
    observations = tuple(
        CanonicalContentV1(
            platform="xiaohongshu",
            external_content_id=f"repair-{uuid4()}",
            content_type="note",
            title=title,
            observed_at=now,
            observed_fields=["content_type", "title"],
            source=source.model_copy(update={"item_locator": f"repair:{index}"}),
        )
        for index in range(count)
    )
    with runtime.database.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        results = owner.ingest_contents_batch(observations)
        owner.ingest_contents_batch(
            tuple(
                item.model_copy(
                    update={
                        "share_url": "https://example.com/repair",
                        "observed_fields": ["share_url"],
                        "observed_at": now + timedelta(seconds=1),
                    }
                )
                for item in observations
            )
        )
    return tuple(sorted(item.target_id for item in results))


def _claim(runtime):  # type: ignore[no-untyped-def]
    """用正式 Runtime 原子取得当前 Fence。"""
    with runtime.database.new_session() as session, session.begin():
        job = PostgresJobRepository(session).claim_next(
            supported_job_types=(CONTENT_CONSISTENCY_REPAIR_JOB_TYPE,),
            worker_id="repair-direct",
            lease_seconds=120,
        )
        assert job is not None and job.lease_token is not None
        return JobExecutionFence(job_id=job.id, lease_token=job.lease_token)


class _Context:
    """只隔离进度回报，业务事务、Fence、恢复和目标页均使用真实 PostgreSQL。"""

    def __init__(self, fence, *, stop_after_batch=False):  # type: ignore[no-untyped-def]
        """显式要求一批后停止，稳定制造持久恢复边界。"""
        self.fence = fence
        self.stop_after_batch = stop_after_batch
        self.heartbeats = 0

    def heartbeat(self, *, progress):  # type: ignore[no-untyped-def]
        """记录已提交批次的进度信号。"""
        self.heartbeats += 1

    def cancel_requested(self):  # type: ignore[no-untyped-def]
        """在批次提交之后确定性结束当前执行周期。"""
        return self.stop_after_batch and self.heartbeats > 0


def test_dry_run_proves_reusable_history_without_creating_business_facts(reuse_runtime):  # type: ignore[no-untyped-def]
    """旧补采缺证与 stale 可被只读预检发现，且不生成修复或模型执行。"""
    runtime, service, content_id = reuse_runtime
    _observe(runtime)
    _damage(runtime, content_id)
    with runtime.database.new_session() as session, session.begin():
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        session.execute(text("SET TRANSACTION READ ONLY"))
        before = _counts(session)
        preview = PostgresContentConsistencyRepairRepository(session).dry_run(
            content_ids=(content_id,), collection_run_id=None, max_contents=10, batch_size=2
        )
        assert preview["target_count"] == 1
        assert preview["candidate_count"] == 1
        assert preview["equivalent_count"] == 1
        assert preview["analysis_reasons"] == {"equivalent": 1}
        assert _counts(session) == before
    assert service.get_content(content_id).content_version == 2


@pytest.mark.parametrize("reason", ("input_mismatch", "unknown_protocol", "no_success"))
def test_dry_run_reports_conservative_rejection_without_writes(reuse_runtime, reason):  # type: ignore[no-untyped-def]
    """输入变化、未知历史协议和从未分析的内容均保持原事实。"""
    runtime, _, content_id = reuse_runtime
    if reason == "no_success":
        content_id = _new_contents(runtime, 1)[0]
    else:
        if reason == "unknown_protocol":
            with runtime.database.engine.begin() as connection:
                connection.execute(
                    update(analysis_content_results_table).values(schema_version="unknown.v99")
                )
        _observe(runtime, **({"text": "爱玛 实际输入改变"} if reason == "input_mismatch" else {}))
        _damage(runtime, content_id)
    with runtime.database.new_session() as session:
        before = _counts(session)
        preview = PostgresContentConsistencyRepairRepository(session).dry_run(
            content_ids=(content_id,), collection_run_id=None, max_contents=1
        )
        assert preview["analysis_reasons"] == {reason: 1}
        assert preview["equivalent_count"] == 0
        assert _counts(session) == before


def test_worker_repairs_then_repeats_without_duplicate_business_facts(reuse_runtime):  # type: ignore[no-untyped-def]
    """正式 Worker 恢复当前品牌和原 AI Result，再执行时不产生重复证据或模型运行。"""
    runtime, service, content_id = reuse_runtime
    original = service.get_content(content_id)
    _observe(runtime)
    _damage(runtime, content_id)
    with runtime.database.new_session() as session:
        result_before = tuple(session.execute(select(analysis_content_results_table)))
        analysis_runs_before = session.scalar(
            select(func.count()).select_from(analysis_content_runs_table)
        )
    run, job = _enqueue(runtime, (content_id,))
    assert _worker(runtime).run_once()
    repaired = _get_run(runtime, run.id)
    assert repaired.processed_count == repaired.candidate_count == repaired.reused_count == 1
    assert repaired.brand_changed_count == 1
    after = service.get_content(content_id)
    assert after.content_version == 2 and after.analysis.status == "completed"
    assert after.analysis.analyzed_at == original.analysis.analyzed_at
    with runtime.database.new_session() as session:
        assert PostgresJobRepository(session).get(job.id).status == "succeeded"
        evidence_before = PostgresContentConsistencyRepairRepository(session).evidence_state(
            ((content_id, 2),)
        )
    second, _ = _enqueue(runtime, (content_id,))
    assert _worker(runtime).run_once()
    repeated = _get_run(runtime, second.id)
    assert repeated.processed_count == repeated.existing_reuse_count == 1
    assert repeated.brand_changed_count == repeated.reused_count == 0
    with runtime.database.new_session() as session:
        assert (
            PostgresContentConsistencyRepairRepository(session).evidence_state(((content_id, 2),))
            == evidence_before
        )
        assert tuple(session.execute(select(analysis_content_results_table))) == result_before
        assert (
            session.scalar(select(func.count()).select_from(analysis_content_runs_table))
            == analysis_runs_before
        )
        assert (
            session.scalar(select(func.count()).select_from(analysis_content_version_reuses_table))
            == 1
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"max_contents": 999},
        {"batch_size": 1},
        {"created_by": "other"},
    ),
)
def test_run_idempotency_rejects_parameter_drift(reuse_runtime, changes):  # type: ignore[no-untyped-def]
    """已冻结 Run 可以原样重放，但不得用同一身份改变运维参数。"""
    runtime, _, content_id = reuse_runtime
    key = uuid4().hex
    run, job = _enqueue(runtime, (content_id,), key=key)
    same, same_job = _enqueue(runtime, (content_id, content_id), key=key)
    assert same == run and same_job.id == job.id
    with pytest.raises(ValueError, match="不同的修复范围或参数"):
        _enqueue(runtime, (content_id,), key=key, **changes)
    other = _new_contents(runtime, 1)[0]
    with pytest.raises(ValueError, match="不同的修复范围或参数"):
        _enqueue(runtime, (other,), key=key)


@pytest.mark.parametrize(
    "options, message",
    (
        ({"max_contents": 10001}, "1—10000"),
        ({"max_contents": 0}, "1—10000"),
        ({"batch_size": 1001}, "1—1000"),
        ({"batch_size": 0}, "1—1000"),
        ({"content_ids": ()}, "只能指定"),
        ({"content_ids": (uuid4(),)}, "不存在"),
        ({"collection_run_id": uuid4()}, "只能指定"),
    ),
)
def test_scope_limits_reject_without_creating_jobs(reuse_runtime, options, message):  # type: ignore[no-untyped-def]
    """没有隐式全库范围，超出硬限制或无效目标不留下空 Job。"""
    runtime, _, content_id = reuse_runtime
    with runtime.database.new_session() as session:
        before = _counts(session)
    with pytest.raises(ValueError, match=message):
        _enqueue(runtime, (content_id,), **options)
    with runtime.database.new_session() as session:
        assert _counts(session) == before


def test_explicit_limit_is_rejection_not_truncation(reuse_runtime):  # type: ignore[no-untyped-def]
    """有限集合超过操作者给出的范围时必须整次拒绝。"""
    runtime, _, _ = reuse_runtime
    ids = _new_contents(runtime, 2)
    with pytest.raises(ValueError, match="超过 max_contents"):
        _enqueue(runtime, ids, max_contents=1)


def test_empty_brand_match_is_success_and_advances_checkpoint(reuse_runtime):  # type: ignore[no-untyped-def]
    """合法空分类仍提交完整检查点，不创建分析运行或额外内容版本。"""
    runtime, _, _ = reuse_runtime
    ids = _new_contents(runtime, 1, title="普通通勤，天气晴朗")
    run, _ = _enqueue(runtime, ids)
    assert _worker(runtime).run_once()
    completed = _get_run(runtime, run.id)
    assert completed.processed_count == completed.unmatched_count == 1
    assert completed.checkpoint_content_id == ids[0] and completed.reused_count == 0
    with runtime.database.new_session() as session:
        assert (
            session.scalar(
                select(contents_table.c.current_version).where(contents_table.c.id == ids[0])
            )
            == 2
        )
        assert session.scalar(select(func.count()).select_from(analysis_content_runs_table)) == 1


def test_failure_after_business_and_checkpoint_writes_rolls_back_entire_batch(
    reuse_runtime, monkeypatch
):  # type: ignore[no-untyped-def]
    """在最终检查点写后故障时，已写 Evidence/复用/投影与检查点一起回滚。"""
    runtime, service, content_id = reuse_runtime
    _observe(runtime)
    _damage(runtime, content_id)
    run, _ = _enqueue(runtime, (content_id,))
    fence = _claim(runtime)
    executor = PostgresContentConsistencyRepairExecutor(runtime)
    payload = ContentConsistencyRepairPayload(run_id=run.id)
    original = PostgresContentConsistencyRepairRepository.advance

    def fail_after_advance(self, **kwargs):  # type: ignore[no-untyped-def]
        """只注入异常，业务写链和检查点 CAS 使用生产实现。"""
        original(self, **kwargs)
        raise RuntimeError("injected after checkpoint")

    with runtime.database.new_session() as session:
        before = _counts(session)
    monkeypatch.setattr(PostgresContentConsistencyRepairRepository, "advance", fail_after_advance)
    with pytest.raises(RuntimeError, match="after checkpoint"):
        executor.execute(payload=payload, fence=fence, context=_Context(fence))
    rolled_back = _get_run(runtime, run.id)
    assert rolled_back.processed_count == 0 and rolled_back.checkpoint_content_id is None
    assert rolled_back.reused_count == rolled_back.brand_changed_count == 0
    with runtime.database.new_session() as session:
        assert _counts(session) == before
    assert service.get_content(content_id).analysis.status == "stale"
    monkeypatch.setattr(PostgresContentConsistencyRepairRepository, "advance", original)
    assert (
        executor.execute(payload=payload, fence=fence, context=_Context(fence)).outcome
        == "succeeded"
    )
    assert _get_run(runtime, run.id).reused_count == 1
    assert service.get_content(content_id).analysis.status == "completed"


def test_checkpoint_takeover_rejects_old_fence_and_resumes_remaining_targets(reuse_runtime):  # type: ignore[no-untyped-def]
    """接管读取已提交 UUID 检查点；旧 Worker 不能再处理下一页。"""
    runtime, _, _ = reuse_runtime
    ids = _new_contents(runtime, 3)
    run, _ = _enqueue(runtime, ids, batch_size=1)
    fence = _claim(runtime)
    executor = PostgresContentConsistencyRepairExecutor(runtime)
    payload = ContentConsistencyRepairPayload(run_id=run.id)
    assert (
        executor.execute(
            payload=payload, fence=fence, context=_Context(fence, stop_after_batch=True)
        ).outcome
        == "cancelled"
    )
    first = _get_run(runtime, run.id)
    assert first.processed_count == 1 and first.checkpoint_content_id == ids[0]
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == fence.job_id)
            .values(lease_expires_at=beijing_now() - timedelta(seconds=1))
        )
    replacement = _claim(runtime)
    assert replacement.lease_token != fence.lease_token
    with pytest.raises(LeaseLostError):
        executor.execute(payload=payload, fence=fence, context=_Context(fence))
    assert _get_run(runtime, run.id) == first
    assert (
        executor.execute(payload=payload, fence=replacement, context=_Context(replacement)).outcome
        == "succeeded"
    )
    completed = _get_run(runtime, run.id)
    assert completed.processed_count == completed.target_count == completed.brand_changed_count == 3
    assert completed.checkpoint_content_id == ids[-1]
    assert completed.analysis_reasons == {"no_success": 3}


def test_cancelled_run_cannot_write_remaining_targets(reuse_runtime):  # type: ignore[no-untyped-def]
    """正式取消状态阻止仍持有旧 Token 的执行继续提交。"""
    runtime, _, _ = reuse_runtime
    ids = _new_contents(runtime, 2)
    run, _ = _enqueue(runtime, ids, batch_size=1)
    fence = _claim(runtime)
    executor = PostgresContentConsistencyRepairExecutor(runtime)
    payload = ContentConsistencyRepairPayload(run_id=run.id)
    executor.execute(payload=payload, fence=fence, context=_Context(fence, stop_after_batch=True))
    before = _get_run(runtime, run.id)
    with runtime.database.new_session() as session, session.begin():
        PostgresContentConsistencyRepairRepository(session).request_cancel(run.id)
    with pytest.raises(LeaseLostError):
        executor.execute(payload=payload, fence=fence, context=_Context(fence))
    assert _get_run(runtime, run.id) == before


def test_collection_source_scope_is_forward_bounded_and_frozen(reuse_runtime):  # type: ignore[no-untyped-def]
    """只选择指定 Run 成功入库账本；重放不包含之后到达的新来源。"""
    runtime, _, unrelated = reuse_runtime
    source = _create_live_source(
        runtime.database, source_value=f"repair-{uuid4()}", enrichment=True
    )
    writer = PostgresFencedCollectionIngestionWriter(runtime.database.new_session)
    first = writer.ingest_content(canonical=_canonical(source), fence=source.fence)
    with runtime.database.new_session() as session:
        collection_id = session.scalar(
            select(collection_scopes_table.c.run_id).where(
                collection_scopes_table.c.id == source.scope_id
            )
        )
        repository = PostgresContentConsistencyRepairRepository(session)
        assert repository.resolve_targets(
            content_ids=(), collection_run_id=collection_id, max_contents=1
        ) == (first.target_id,)
        assert unrelated != first.target_id
    key = uuid4().hex
    run, _ = _enqueue(runtime, (), collection_run_id=collection_id, key=key, max_contents=1)
    second = writer.ingest_content(
        canonical=_canonical(source, external_content_id=f"later-{uuid4()}"), fence=source.fence
    )
    assert second.target_id != first.target_id
    same, _ = _enqueue(runtime, (), collection_run_id=collection_id, key=key, max_contents=1)
    assert same == run
    with runtime.database.new_session() as session:
        repository = PostgresContentConsistencyRepairRepository(session)
        assert repository.target_ids(run.id) == (first.target_id,)
        with pytest.raises(ValueError, match="超过 max_contents"):
            repository.dry_run(content_ids=(), collection_run_id=collection_id, max_contents=1)
        assert (
            repository.dry_run(content_ids=(), collection_run_id=collection_id, max_contents=2)[
                "target_count"
            ]
            == 2
        )


def test_preview_query_count_is_constant_per_bounded_page(reuse_runtime, record_property):  # type: ignore[no-untyped-def]
    """同一页 1 与 100 条查询次数一致，所有业务读取均有显式目标限制。"""
    runtime, _, unrelated = reuse_runtime
    ids = _new_contents(runtime, 100)
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        """记录真实 SQL，观察批量读取是否退化为逐条查询。"""
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    counts = []
    event.listen(runtime.database.engine, "before_cursor_execute", record)
    try:
        for selected in (ids[:1], ids):
            statements.clear()
            with runtime.database.new_session() as session:
                preview = PostgresContentConsistencyRepairRepository(session).dry_run(
                    content_ids=selected, collection_run_id=None, max_contents=100, batch_size=100
                )
            assert preview["target_count"] == len(selected)
            assert preview["analysis_reasons"] == {"no_success": len(selected)}
            counts.append(len(statements))
            assert all("WHERE" in query for query in statements if "FROM contents" in query)
    finally:
        event.remove(runtime.database.engine, "before_cursor_execute", record)
    record_property("preview_sql_counts_for_1_and_100", json.dumps(counts))
    assert counts[0] == counts[1] and counts[0] <= 12
    run, _ = _enqueue(runtime, ids[:3], batch_size=2)
    fence = _claim(runtime)
    PostgresContentConsistencyRepairExecutor(runtime).execute(
        payload=ContentConsistencyRepairPayload(run_id=run.id),
        fence=fence,
        context=_Context(fence, stop_after_batch=True),
    )
    assert _get_run(runtime, run.id).processed_count == 2
    with runtime.database.new_session() as session:
        repository = PostgresContentConsistencyRepairRepository(session)
        assert repository.load_next_target_ids(_get_run(runtime, run.id)) == ids[2:3]
        assert unrelated not in repository.target_ids(run.id)


@pytest.mark.parametrize("unlock_vehicle", (False, True))
def test_manual_dimensions_inherit_independent_sources_and_respect_tombstone(
    reuse_runtime, unlock_vehicle
):  # type: ignore[no-untyped-def]
    """品牌 V2 与车型 V1 分别继承；较新的车型显式解锁阻止旧人工结论复活。"""
    runtime, _, _ = reuse_runtime
    content_id = _new_contents(runtime, 1)[0]
    brand_id = UUID(stage3_filter_brand_id(runtime, alias="爱玛"))
    with runtime.database.new_session() as session, session.begin():
        brand = PostgresBrandVehicleRepository(session)
        vehicle = PostgresVehicleCatalogRepository(session)
        model = vehicle.create_model(
            code=f"repair-{uuid4().hex}",
            display_name="人工长途车型",
            aliases=("人工长途车型",),
            actor_ref="catalog-test",
            brand_id=brand_id,
        )
        vehicle.replace_manual_evidence(
            content_id=content_id,
            content_version=1,
            model_ids=(model.id,),
            unlock_existing=False,
            actor_ref="vehicle-reviewer",
        )
        brand.replace_manual_brand_evidence(
            content_id=content_id,
            content_version=2,
            brand_ids=(brand_id,),
            unlock_existing=False,
            actor_ref="brand-reviewer",
        )
        if unlock_vehicle:
            vehicle.replace_manual_evidence(
                content_id=content_id,
                content_version=2,
                model_ids=(),
                unlock_existing=True,
                actor_ref="vehicle-unlocker",
            )
        original_brand = (
            session.execute(
                select(content_brand_review_locks_table).where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == 2,
                )
            )
            .mappings()
            .one()
        )
        external_id = session.scalar(
            select(contents_table.c.external_content_id).where(contents_table.c.id == content_id)
        )
    now = beijing_now() + timedelta(seconds=5)
    source = _source(runtime.database, observed_at=now, suffix=uuid4().hex)
    observation = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_id,
        content_type="note",
        share_url="https://example.com/third-version",
        observed_at=now,
        observed_fields=["share_url"],
        source=source,
    )
    with runtime.database.new_session() as session, session.begin():
        PostgresCompleteContentRepository(session).ingest_content(observation)
        assert (
            session.scalar(
                select(contents_table.c.current_version).where(contents_table.c.id == content_id)
            )
            == 3
        )
        pairs = ((content_id, 3),)
        vehicle_sources, brand_sources = PostgresContentConsistencyRepairRepository(
            session
        ).manual_carry_sources(pairs)
        assert brand_sources == ((content_id, 2, 3),)
        assert vehicle_sources == (() if unlock_vehicle else ((content_id, 1, 3),))
    run, _ = _enqueue(runtime, (content_id,))
    assert _worker(runtime).run_once()
    assert _get_run(runtime, run.id).processed_count == 1
    with runtime.database.new_session() as session:
        inherited = (
            session.execute(
                select(content_brand_review_locks_table).where(
                    content_brand_review_locks_table.c.content_id == content_id,
                    content_brand_review_locks_table.c.content_version == 3,
                )
            )
            .mappings()
            .one()
        )
        assert inherited["actor_ref"] == "brand-reviewer"
        assert inherited["updated_at"] == original_brand["updated_at"]
        vehicles = tuple(
            session.scalars(
                select(content_vehicle_evidence_table.c.vehicle_model_id).where(
                    content_vehicle_evidence_table.c.content_id == content_id,
                    content_vehicle_evidence_table.c.content_version == 3,
                    content_vehicle_evidence_table.c.is_active.is_(True),
                    content_vehicle_evidence_table.c.is_manual_locked.is_(True),
                )
            )
        )
        assert vehicles == (() if unlock_vehicle else (model.id,))


def test_catalog_is_frozen_before_execution_and_keyset_resume(reuse_runtime):  # type: ignore[no-untyped-def]
    """已启动的修复不会在重试或接管时静默采用后发布的目录。"""
    runtime, _, _ = reuse_runtime
    alias = f"后发布目录{uuid4().hex}品牌"
    ids = _new_contents(runtime, 2, title=f"{alias} 通勤")
    run, _ = _enqueue(runtime, ids, batch_size=1)
    with runtime.database.new_session() as session, session.begin():
        added = PostgresBrandVehicleRepository(session).create_brand(
            code=f"repair-{uuid4().hex}",
            display_name=alias,
            role="competitor",
            aliases=(alias,),
            actor_ref="catalog-test",
        )
    assert added.catalog_version > run.catalog_snapshot.catalog_version
    fence = _claim(runtime)
    executor = PostgresContentConsistencyRepairExecutor(runtime)
    payload = ContentConsistencyRepairPayload(run_id=run.id)
    executor.execute(payload=payload, fence=fence, context=_Context(fence, stop_after_batch=True))
    assert _get_run(runtime, run.id).processed_count == 1
    assert (
        executor.execute(payload=payload, fence=fence, context=_Context(fence)).outcome
        == "succeeded"
    )
    assert _get_run(runtime, run.id).unmatched_count == 2
    with runtime.database.new_session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(content_brand_evidence_table)
                .where(
                    content_brand_evidence_table.c.content_id.in_(ids),
                    content_brand_evidence_table.c.is_active.is_(True),
                )
            )
            == 0
        )


def test_empty_manual_locks_and_current_unlock_keep_original_identity(reuse_runtime):  # type: ignore[no-untyped-def]
    """合法空锁仍继承，当前显式解锁不能被历史结论重新锁定。"""
    runtime, _, _ = reuse_runtime
    locked_id, unlocked_id = _new_contents(runtime, 2)
    with runtime.database.new_session() as session, session.begin():
        vehicle = PostgresVehicleCatalogRepository(session)
        brand = PostgresBrandVehicleRepository(session)
        for content_id in (locked_id, unlocked_id):
            vehicle.replace_manual_evidence(
                content_id=content_id,
                content_version=1,
                model_ids=(),
                unlock_existing=False,
                actor_ref="empty-vehicle-reviewer",
            )
            brand.replace_manual_brand_evidence(
                content_id=content_id,
                content_version=1,
                brand_ids=(),
                unlock_existing=False,
                actor_ref="empty-brand-reviewer",
            )
        vehicle.replace_manual_evidence(
            content_id=unlocked_id,
            content_version=2,
            model_ids=(),
            unlock_existing=True,
            actor_ref="current-vehicle-unlocker",
        )
        brand.replace_manual_brand_evidence(
            content_id=unlocked_id,
            content_version=2,
            brand_ids=(),
            unlock_existing=True,
            actor_ref="current-brand-unlocker",
        )
        sources = PostgresContentConsistencyRepairRepository(session).manual_carry_sources(
            ((locked_id, 2), (unlocked_id, 2))
        )
        assert sources == (((locked_id, 1, 2),), ((locked_id, 1, 2),))
    run, _ = _enqueue(runtime, (locked_id, unlocked_id))
    assert _worker(runtime).run_once()
    assert _get_run(runtime, run.id).processed_count == 2
    with runtime.database.new_session() as session:
        for table in (content_vehicle_review_locks_table, content_brand_review_locks_table):
            source = (
                session.execute(
                    select(table).where(
                        table.c.content_id == locked_id,
                        table.c.content_version == 1,
                    )
                )
                .mappings()
                .one()
            )
            target = (
                session.execute(
                    select(table).where(
                        table.c.content_id == locked_id,
                        table.c.content_version == 2,
                    )
                )
                .mappings()
                .one()
            )
            assert target["is_locked"] is True
            assert target["actor_ref"] == source["actor_ref"]
            assert target["updated_at"] == source["updated_at"]
            unlocked = (
                session.execute(
                    select(table).where(
                        table.c.content_id == unlocked_id,
                        table.c.content_version == 2,
                    )
                )
                .mappings()
                .one()
            )
            assert unlocked["is_locked"] is False
            assert "unlocker" in unlocked["actor_ref"]
        assert (
            session.scalar(
                select(func.count())
                .select_from(content_brand_evidence_table)
                .where(
                    content_brand_evidence_table.c.content_id == locked_id,
                    content_brand_evidence_table.c.content_version == 2,
                    content_brand_evidence_table.c.is_active.is_(True),
                )
            )
            == 0
        )


def test_registered_worker_retries_failed_batch_without_partial_success(reuse_runtime, monkeypatch):  # type: ignore[no-untyped-def]
    """数据库失败经正式 Runtime 重试，第一次不留下业务写入或错误的成功计数。"""
    runtime, _, content_id = reuse_runtime
    _observe(runtime)
    _damage(runtime, content_id)
    run, job = _enqueue(runtime, (content_id,))
    advance = PostgresContentConsistencyRepairRepository.advance
    calls = 0

    def fail_first(self, **kwargs):  # type: ignore[no-untyped-def]
        """生产 CAS 之后仅第一次抛数据库异常，观察真实 Job 重试状态机。"""
        nonlocal calls
        calls += 1
        updated = advance(self, **kwargs)
        if calls == 1:
            raise SQLAlchemyError("injected transient failure")
        return updated

    monkeypatch.setattr(PostgresContentConsistencyRepairRepository, "advance", fail_first)
    worker = _worker(runtime)
    assert worker.run_once()
    first = _get_run(runtime, run.id)
    assert first.processed_count == first.reused_count == 0
    with runtime.database.new_session() as session:
        first_job = PostgresJobRepository(session).get(job.id)
        assert first_job.status == "queued" and first_job.attempt == 1
        assert (
            session.scalar(select(func.count()).select_from(analysis_content_version_reuses_table))
            == 0
        )
    assert worker.run_once()
    assert _get_run(runtime, run.id).reused_count == 1
    with runtime.database.new_session() as session:
        final_job = PostgresJobRepository(session).get(job.id)
        assert final_job.status == "succeeded" and final_job.attempt == 2


def test_automatic_repair_query_count_is_constant_for_one_or_hundred_targets(
    reuse_runtime, record_property
):  # type: ignore[no-untyped-def]
    """真实业务 apply 同一页 1/100 条使用固定往返，且只刷新选中页的投影。"""
    runtime, _, _ = reuse_runtime
    ids = _new_contents(runtime, 101)
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        """记录真实生产修复链 SQL，包括证据和投影写入。"""
        statements.append(statement)

    counts = []
    for selected in (ids[:1], ids[1:]):
        run, _ = _enqueue(runtime, selected, batch_size=100)
        fence = _claim(runtime)
        statements.clear()
        event.listen(runtime.database.engine, "before_cursor_execute", record)
        try:
            result = PostgresContentConsistencyRepairExecutor(runtime).execute(
                payload=ContentConsistencyRepairPayload(run_id=run.id),
                fence=fence,
                context=_Context(fence),
            )
        finally:
            event.remove(runtime.database.engine, "before_cursor_execute", record)
        assert result.outcome == "succeeded"
        assert _get_run(runtime, run.id).brand_changed_count == len(selected)
        counts.append(len(statements))
        assert all("WHERE" in query for query in statements if "FROM contents" in query)
    record_property("automatic_apply_sql_counts_for_1_and_100", json.dumps(counts))
    assert counts[0] == counts[1] and counts[0] <= 90


def test_manual_carry_owner_batch_queries_are_constant_for_one_or_hundred_sources(
    reuse_runtime, record_property
):  # type: ignore[no-untyped-def]
    """人工锁和证据继承也必须集合写入，不能把修复页退化成逐条 SQL。"""
    runtime, _, _ = reuse_runtime
    ids = _new_contents(runtime, 101)
    brand_id = UUID(stage3_filter_brand_id(runtime, alias="爱玛"))
    with runtime.database.new_session() as session, session.begin():
        defer_voice_plaza_projection(session)
        vehicle = PostgresVehicleCatalogRepository(session)
        brand = PostgresBrandVehicleRepository(session)
        model = vehicle.create_model(
            code=f"manual-bulk-{uuid4().hex}",
            display_name="批量人工车型",
            aliases=(),
            actor_ref="catalog-test",
            brand_id=brand_id,
        )
        for content_id in ids:
            vehicle.replace_manual_evidence(
                content_id=content_id,
                content_version=1,
                model_ids=(model.id,),
                unlock_existing=False,
                actor_ref="bulk-vehicle-reviewer",
            )
            brand.replace_manual_brand_evidence(
                content_id=content_id,
                content_version=1,
                brand_ids=(brand_id,),
                unlock_existing=False,
                actor_ref="bulk-brand-reviewer",
            )
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        """只计实际 Owner 批量继承期间的数据库往返。"""
        statements.append(statement)

    counts = []
    for selected in (ids[:1], ids[1:]):
        with runtime.database.new_session() as session, session.begin():
            defer_voice_plaza_projection(session)
            entries = tuple((content_id, 1, 2) for content_id in selected)
            statements.clear()
            event.listen(runtime.database.engine, "before_cursor_execute", record)
            try:
                assert PostgresVehicleCatalogRepository(session).carry_manual_review_batch(
                    entries
                ) == set(selected)
                assert PostgresBrandVehicleRepository(session).carry_manual_brand_review_batch(
                    entries
                ) == set(selected)
            finally:
                event.remove(runtime.database.engine, "before_cursor_execute", record)
            counts.append(len(statements))
            assert session.scalar(
                select(func.count())
                .select_from(content_vehicle_evidence_table)
                .where(
                    content_vehicle_evidence_table.c.content_id.in_(selected),
                    content_vehicle_evidence_table.c.content_version == 2,
                    content_vehicle_evidence_table.c.is_manual_locked.is_(True),
                )
            ) == len(selected)
    record_property("manual_carry_sql_counts_for_1_and_100", json.dumps(counts))
    assert counts[0] == counts[1] and counts[0] <= 12, counts


def test_cli_dry_run_start_status_cancel_uses_real_local_runtime(reuse_runtime):  # type: ignore[no-untyped-def]
    """实际运维命令形成可审查预检、持久 Job 与正式取消，不启动付费执行。"""
    runtime, _, content_id = reuse_runtime
    root = Path(__file__).resolve().parents[3]

    def invoke(*arguments):  # type: ignore[no-untyped-def]
        """调用当前 Python 工程入口，读取最后一行结构化输出。"""
        completed = subprocess.run(
            [sys.executable, "scripts/operations/content_consistency_repair.py", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])

    with runtime.database.new_session() as session:
        before = _counts(session)
    scope = ("--content-id", str(content_id), "--max-contents", "1", "--batch-size", "1")
    preview = invoke("dry-run", *scope)
    assert preview["target_count"] == 1 and preview["analysis_reasons"] == {"direct": 1}
    with runtime.database.new_session() as session:
        assert _counts(session) == before
    started = invoke("start", *scope, "--idempotency-key", uuid4().hex, "--created-by", "cli-test")
    status = invoke("status", "--run-id", started["run_id"])
    assert status["job_status"] == "queued" and status["processed_count"] == 0
    cancelled = invoke("cancel", "--run-id", started["run_id"])
    assert cancelled["job_status"] == "cancelled" and cancelled["processed_count"] == 0
