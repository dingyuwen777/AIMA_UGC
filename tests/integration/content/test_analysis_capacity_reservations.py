"""专属 PostgreSQL 中验证共享预留、缩容排空与 Fence 生命周期。"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_capacity import (
    LATENCY_BUCKETS,
    PostgresAnalysisCapacityRepository,
    empty_window,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.runtime_config import active_llm_provider
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState
from aima_ugc.modules.analysis.content_analysis_job import CONTENT_ANALYSIS_JOB_TYPE
from aima_ugc.modules.analysis.tables import analysis_llm_capacity_profiles_table as profiles
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import func, select, update

from tests.integration.content.test_analysis_adaptive_capacity import _worker
from tests.integration.content.test_analysis_adaptive_capacity import runtime as runtime
from tests.integration.content.test_analysis_provider_concurrency import (
    _client,
    _create_run,
    _seed_contents,
    _seed_provider,
)


def _claimed(runtime, *, shards=2):
    """通过公开 API 和真实 Planner 建立指定数量运行任务，不伪造业务写路径。"""
    runtime.settings = runtime.settings.model_copy(
        update={"analysis_run_max_in_flight_jobs": shards}
    )
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime)
    for _ in range(shards):
        _create_run(client, ids, runtime, key=str(uuid4()), legacy=False)
    with runtime.database.engine.begin() as connection:
        connection.execute(update(profiles).values(state=asdict(CapacityState(current=1024))))
    worker = _worker(runtime)
    for _ in range(shards):
        assert worker.run_once()
    fences = []
    session = runtime.database.new_session()
    try:
        with session.begin():
            provider = active_llm_provider(session, runtime.settings)
            for index in range(shards):
                job = PostgresJobRepository(session).claim_next(
                    supported_job_types=(CONTENT_ANALYSIS_JOB_TYPE,),
                    worker_id=f"reserve-{index}",
                    lease_seconds=120,
                )
                assert job is not None
                fences.append(JobExecutionFence(job_id=job.id, lease_token=job.lease_token))
            session.execute(update(profiles).values(state=asdict(CapacityState(current=10))))
    finally:
        session.close()
    return provider, fences


def _reserve(runtime, provider, fence, wanted, occupied=0):
    """每次预留使用独立短事务，调用生产 Repository 的行锁与分配。"""
    session = runtime.database.new_session()
    try:
        with session.begin():
            return PostgresAnalysisCapacityRepository(session).reserve(
                provider.id,
                provider.model,
                fence=fence,
                wanted=wanted,
                occupied=occupied,
                timeout_seconds=120,
            )[0]
    finally:
        session.close()


def test_concurrent_reservations_are_atomic_and_shrink_waits_for_old_inflight(runtime):
    """两个真实事务的许可总额有界，缩容后旧在途排空才重新分配。"""
    provider, fences = _claimed(runtime)
    barrier = Barrier(2)

    def claim(fence):
        """同时进入两个事务，覆盖共享行锁下的竞争分配。"""
        barrier.wait(timeout=3)
        return _reserve(runtime, provider, fence, 8)

    with ThreadPoolExecutor(max_workers=2) as pool:
        grants = list(pool.map(claim, fences))
    assert grants == [5, 5]
    with runtime.database.engine.begin() as connection:
        connection.execute(update(profiles).values(state=asdict(CapacityState(current=2))))
    # 缩容不能把已经发出的槽位交给另一片；先停止补发，再排空到新总额。
    assert [_reserve(runtime, provider, fence, 8, 5) for fence in fences] == [0, 0]
    assert _reserve(runtime, provider, fences[0], 8, 0) == 0
    assert _reserve(runtime, provider, fences[1], 8, 0) == 1
    assert _reserve(runtime, provider, fences[0], 8, 0) == 1
    with runtime.database.engine.begin() as connection:
        holders = connection.execute(select(profiles.c.window)).scalar_one()["reservations"]
        assert sum(value["reserved"] for value in holders.values()) == 2


def test_tail_can_lend_unused_slots_without_multiplying_global_capacity(runtime):
    """尾片可借出闲置许可，总预留不能因跨片借用而倍增。"""
    provider, fences = _claimed(runtime)
    assert _reserve(runtime, provider, fences[0], 1) == 1
    assert _reserve(runtime, provider, fences[1], 10) == 9
    assert _reserve(runtime, provider, fences[0], 10, 1) == 1
    session = runtime.database.new_session()
    try:
        with session.begin():
            PostgresAnalysisCapacityRepository(session).release(
                provider.id, provider.model, fences[1]
            )
    finally:
        session.close()
    # 同一活跃任务还未退出，借用必须等待它报告新的真实需求。
    assert _reserve(runtime, provider, fences[0], 10) == 5


def test_idle_remainder_share_can_be_lent_when_capacity_is_less_than_shard_count(runtime):
    """C=1 时零 ready 的分片不占份额，余数许可也能交给真正就绪的分片。"""
    provider, fences = _claimed(runtime)
    with runtime.database.new_session() as session, session.begin():
        active = PostgresAnalysisCapacityRepository(session).active_shards(
            provider.id, provider.model
        )
        session.execute(update(profiles).values(state=asdict(CapacityState(current=1))))
    idle = next(fence for fence in fences if fence.job_id == active[0])
    ready = next(fence for fence in fences if fence.job_id != idle.job_id)
    assert _reserve(runtime, provider, idle, 0) == 0
    assert _reserve(runtime, provider, ready, 8) == 1
    # 闲置片重新就绪时仍不能借出 peer 已发送或保留的真实许可。
    assert _reserve(runtime, provider, idle, 8) == 0


def test_takeover_keeps_old_unknown_occupancy_and_old_cleanup_preserves_new_fence(runtime):
    """旧 Fence 的未知占用保守保留，旧进程清理不能删除接管者许可。"""
    provider, fences = _claimed(runtime)
    old = fences[0]
    assert _reserve(runtime, provider, old, 8) == 5
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == old.job_id)
            .values(lease_expires_at=func.clock_timestamp() - timedelta(seconds=1))
        )
    session = runtime.database.new_session()
    try:
        with session.begin():
            job = PostgresJobRepository(session).claim_next(
                supported_job_types=(CONTENT_ANALYSIS_JOB_TYPE,),
                worker_id="takeover",
                lease_seconds=120,
            )
            assert job is not None and job.id == old.job_id and job.lease_token != old.lease_token
            new = JobExecutionFence(job_id=job.id, lease_token=job.lease_token)
            repo = PostgresAnalysisCapacityRepository(session)
            grant, _ = repo.reserve(
                provider.id, provider.model, fence=new, wanted=8, occupied=0, timeout_seconds=120
            )
            assert grant <= 5
            window = repo.get(provider.id, provider.model)["window"]
            assert len(window["reservations"]) == 2
            repo.release(provider.id, provider.model, old)
            holders = repo.get(provider.id, provider.model)["window"]["reservations"]
            assert f"{new.job_id}:{new.lease_token}" in holders
            assert f"{old.job_id}:{old.lease_token}" not in holders
    finally:
        session.close()


def test_configuration_warm_start_preserves_inflight_reservations(runtime):
    """配置变化只重置观测阶段，不能提前借出仍有持有者的许可。"""
    provider, fences = _claimed(runtime)
    assert _reserve(runtime, provider, fences[0], 8) == 5
    session = runtime.database.new_session()
    try:
        with session.begin():
            repo = PostgresAnalysisCapacityRepository(session)
            before = repo.get(provider.id, provider.model)["window"]
            repo.ensure(
                provider.id, provider.model, revision=provider.revision + 1, prompt_sha256="b" * 64
            )
            after = repo.get(provider.id, provider.model)["window"]
            assert after["reservations"] == before["reservations"]
            assert after["epoch"] > before["epoch"]
            assert after["requests"] == 0
    finally:
        session.close()


def test_old_controller_upgrade_discards_false_boundary_and_seeds_verified_model(runtime):
    """旧算法的误判上界不迁作新证明，已核验模型从有界初值重探。"""
    provider, _fences = _claimed(runtime)
    session = runtime.database.new_session()
    try:
        with session.begin():
            repo = PostgresAnalysisCapacityRepository(session)
            row = repo.get(provider.id, provider.model)
            old = asdict(CapacityState(current=10, last_safe=10, unsafe=20, phase="cooldown"))
            old.pop("control_version")
            session.execute(update(profiles).values(state=old))
            state = repo.ensure(
                provider.id,
                provider.model,
                revision=provider.revision,
                prompt_sha256=row["prompt_sha256"],
                declared_ceiling=2500,
            )
            assert state.current == 50
            assert state.unsafe is None and state.last_safe == 0
            assert state.phase == "exploring" and state.control_version == 3
    finally:
        session.close()


@pytest.mark.parametrize("old_hint,new_hint,expected", [(2500, None, 1000), (None, 500, 500)])
def test_connection_hint_change_limits_new_capacity_without_releasing_old_holders(
    runtime, old_hint, new_hint, expected
):
    """连接端点变更同步声明并限制新容量，真实事务仍保留在途持有者。"""
    provider, fences = _claimed(runtime)
    assert _reserve(runtime, provider, fences[0], 8) == 5
    session = runtime.database.new_session()
    try:
        with session.begin():
            repo = PostgresAnalysisCapacityRepository(session)
            before = repo.get(provider.id, provider.model)
            holders = before["window"]["reservations"]
            session.execute(
                update(profiles).values(
                    state=asdict(
                        CapacityState(current=2000, last_safe=2000, declared_ceiling=old_hint)
                    )
                )
            )
            state = repo.ensure(
                provider.id,
                provider.model,
                revision=provider.revision + 1,
                prompt_sha256=before["prompt_sha256"],
                declared_ceiling=new_hint,
            )
            assert state.current == expected and state.declared_ceiling == new_hint
            assert repo.get(provider.id, provider.model)["window"]["reservations"] == holders
            grant, _epoch = repo.reserve(
                provider.id,
                provider.model,
                fence=fences[1],
                wanted=2000,
                occupied=0,
                timeout_seconds=120,
            )
            assert grant <= expected
    finally:
        session.close()


def _rates(runtime):
    """读正式持久预留，确认多事务之间的速率承诺，没有替代生产分配。"""
    with runtime.database.new_session() as session, session.begin():
        return session.scalar(select(profiles.c.window))["reservations"]


def _set_capacity(runtime, concurrency, rps):
    """只设置测试提供方已有学习事实，后续分配全部走正式 Owner。"""
    with runtime.database.new_session() as session, session.begin():
        session.execute(
            update(profiles).values(state=asdict(CapacityState(current=concurrency, rps=rps)))
        )


def _allocation(runtime, provider, fence, wanted, occupied=0):
    """同一短事务取得 C 和 RPS，匹配 Feedback 的安装边界。"""
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresAnalysisCapacityRepository(session)
        grant, _ = repo.reserve(
            provider.id,
            provider.model,
            fence=fence,
            wanted=wanted,
            occupied=occupied,
            timeout_seconds=120,
        )
        return grant, repo.reserved_rps(provider.id, provider.model, fence=fence)


@pytest.mark.parametrize("rate", [10.0, 0.08])
def test_rate_lending_returns_to_fair_shares_without_duplicate_budget(runtime, rate):
    """空闲归还全部速率，恢复需求后异步刷新归还借额，小数速率不抬高下限。"""
    provider, (first, second) = _claimed(runtime)
    _set_capacity(runtime, 10, rate)
    assert _allocation(runtime, provider, first, 10) == (5, rate / 2)
    assert _allocation(runtime, provider, second, 10) == (5, rate / 2)
    assert _allocation(runtime, provider, second, 0, occupied=5) == (0, 0)
    # 旧 HTTP 仍占 C，但不占未来发送速率；唯一发送者获得完整 RPS。
    assert _allocation(runtime, provider, first, 10) == (5, rate)
    assert _allocation(runtime, provider, second, 0) == (0, 0)
    assert _allocation(runtime, provider, first, 10) == (10, rate)
    # 恢复者先记录需求；不能提前借出 peer 已安装的速率。
    assert _allocation(runtime, provider, second, 10) == (0, 0)
    assert _allocation(runtime, provider, first, 10) == (5, rate)
    assert _allocation(runtime, provider, second, 10) == (5, 0)
    assert _allocation(runtime, provider, first, 10) == (5, rate / 2)
    assert _allocation(runtime, provider, second, 10) == (5, rate / 2)
    assert sum(value["rps"] for value in _rates(runtime).values()) == pytest.approx(rate)


def test_machine_limited_single_sender_uses_full_rate_and_remainder_can_return(runtime):
    """本机 C 小于全局上限仍可用足速率，C=1 的余数借额恢复后无稳定零许可。"""
    provider, fences = _claimed(runtime)
    with runtime.database.new_session() as session, session.begin():
        active = PostgresAnalysisCapacityRepository(session).active_shards(
            provider.id, provider.model
        )
    first = next(fence for fence in fences if fence.job_id == active[0])
    second = next(fence for fence in fences if fence.job_id != first.job_id)
    _set_capacity(runtime, 100, 10)
    assert _allocation(runtime, provider, first, 0) == (0, 0)
    assert _allocation(runtime, provider, second, 2) == (2, 10)
    _set_capacity(runtime, 1, 10)
    assert _allocation(runtime, provider, second, 2) == (1, 10)
    assert _allocation(runtime, provider, first, 1) == (0, 0)
    assert _allocation(runtime, provider, second, 2) == (0, 0)
    assert _allocation(runtime, provider, first, 1) == (1, 10)


def test_rate_drop_reconciles_old_commitments_before_new_rate_is_lent(runtime):
    """全局降档先收紧本 Fence，新许可扣除其他旧承诺，刷新后恢复正速率。"""
    provider, (first, second) = _claimed(runtime)
    _set_capacity(runtime, 10, 10)
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    assert _allocation(runtime, provider, second, 10) == (5, 5)
    _set_capacity(runtime, 10, 2)
    assert _allocation(runtime, provider, first, 10) == (5, 0)
    assert _allocation(runtime, provider, second, 10) == (5, 1)
    assert _allocation(runtime, provider, first, 10) == (5, 1)
    assert sum(value["rps"] for value in _rates(runtime).values()) == 2
    # 全局提高后仍扣除旧承诺，逐次收敛至新的公平份额。
    _set_capacity(runtime, 10, 10)
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    assert _allocation(runtime, provider, second, 10) == (5, 5)


def test_new_third_holder_cannot_bypass_old_rate_commitments_after_drop(runtime, monkeypatch):
    """新参与者也扣除尚未归还的旧速率，多片最终恢复正许可且总额有界。"""
    from aima_ugc.bootstrap.runtime import PlatformRuntime
    from aima_ugc.platform.capacity import ResourceSnapshot

    # 本用例验证三个已被准入的持有者；先提供明确的六核预算，再收紧模型速率。
    # 独立的三核 Linux 测试容器仍应真实限制运行资源，不能让它的两 Job 窗口替代场景。
    monkeypatch.setattr(
        PlatformRuntime,
        "worker_resources",
        lambda _: ResourceSnapshot(6, 8 * 1024**3, 7 * 1024**3, "three-holder-fixture"),
    )
    provider, fences = _claimed(runtime, shards=3)
    _set_capacity(runtime, 10, 10)
    first = _allocation(runtime, provider, fences[0], 10)
    second = _allocation(runtime, provider, fences[1], 10)
    assert first[1] > 0 and second[1] > 0
    _set_capacity(runtime, 10, 2)
    assert _allocation(runtime, provider, fences[2], 10)[1] == 0
    for _ in range(3):
        for fence in fences:
            _allocation(runtime, provider, fence, 10)
    rates = [value["rps"] for value in _rates(runtime).values()]
    assert all(rate > 0 for rate in rates)
    assert sum(rates) == pytest.approx(2)


@pytest.mark.parametrize("historical_rate", ["missing", None])
def test_unknown_historical_rate_is_not_borrowed_before_owner_refresh(runtime, historical_rate):
    """旧缺失/无限制记录表示未知速率，不当成零借出；本 Fence 刷新后解除阻塞。"""
    provider, (first, second) = _claimed(runtime)
    _set_capacity(runtime, 10, 10)
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    with runtime.database.new_session() as session, session.begin():
        window = session.scalar(select(profiles.c.window))
        entry = window["reservations"][f"{first.job_id}:{first.lease_token}"]
        if historical_rate == "missing":
            entry.pop("rps")
        else:
            entry["rps"] = historical_rate
        session.execute(update(profiles).values(window=window))
    assert _allocation(runtime, provider, second, 10) == (5, 0)
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    assert _allocation(runtime, provider, second, 10) == (5, 5)
    _set_capacity(runtime, 10, None)
    assert _allocation(runtime, provider, second, 10) == (5, None)


def test_rate_reservation_rollback_and_expired_old_fence_restore_available_budget(runtime):
    """失败事务不发布派生额度；旧 Fence 过期前保护未知发送，过期后可借出。"""
    provider, (first, second) = _claimed(runtime)
    _set_capacity(runtime, 10, 10)
    before = _rates(runtime)
    with pytest.raises(RuntimeError, match="injected"):
        with runtime.database.new_session() as session, session.begin():
            PostgresAnalysisCapacityRepository(session).reserve(
                provider.id, provider.model, fence=first, wanted=10, occupied=0, timeout_seconds=120
            )
            raise RuntimeError("injected")
    assert _rates(runtime) == before
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    with runtime.database.new_session() as session, session.begin():
        window = session.scalar(select(profiles.c.window))
        old = dict(window["reservations"].pop(f"{first.job_id}:{first.lease_token}"))
        old_key = f"{first.job_id}:{uuid4()}"
        window["reservations"][old_key] = old
        session.execute(update(profiles).values(window=window))
    # 新身份不能继承或清理旧速率承诺。
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    assert _allocation(runtime, provider, second, 10) == (0, 0)
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresAnalysisCapacityRepository(session)
        repo.release(provider.id, provider.model, second)
        window = repo.get(provider.id, provider.model)["window"]
        window["reservations"][old_key]["expires_at"] = (
            repo._now() - timedelta(seconds=1)
        ).isoformat()
        session.execute(update(profiles).values(window=window))
    assert _allocation(runtime, provider, second, 10) == (5, 5)
    assert old_key not in _rates(runtime)


@pytest.mark.parametrize("version", [None, 2])
def test_controller_upgrade_preserves_old_rate_and_physical_commitments(runtime, version):
    """控制证据重探不能删除旧 Fence 未过期的 C/RPS 承诺。"""
    provider, (first, second) = _claimed(runtime)
    _set_capacity(runtime, 10, 10)
    assert _allocation(runtime, provider, first, 10) == (5, 5)
    before = _rates(runtime)
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresAnalysisCapacityRepository(session)
        row = repo.get(provider.id, provider.model)
        state = dict(row["state"])
        state.pop("control_version")
        if version is not None:
            state.update(
                control_version=version,
                phase="stable",
                unsafe=12,
                evidence_seconds=100,
                evidence_persisted=100,
            )
        session.execute(update(profiles).values(state=state))
        upgraded = repo.ensure(
            provider.id,
            provider.model,
            revision=provider.revision,
            prompt_sha256=row["prompt_sha256"],
        )
        assert repo.get(provider.id, provider.model)["window"]["reservations"] == before
        assert upgraded.control_version == 3 and upgraded.unsafe is None
        assert upgraded.evidence_seconds == upgraded.evidence_persisted == 0
    assert _allocation(runtime, provider, second, 10)[1] == 5


@pytest.mark.parametrize("holder", ["last", "peer", "unknown"])
def test_release_discards_only_last_holders_unfinished_probe(runtime, monkeypatch, holder):
    """真实事务覆盖未闭尾窗、最后退出和同身份重入，peer/未知Fence承诺保留。"""
    provider, (first, second) = _claimed(runtime)
    _set_capacity(runtime, 100, 10)
    _allocation(runtime, provider, first, 100)
    if holder != "last":
        _allocation(runtime, provider, second, 100)
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresAnalysisCapacityRepository(session)
        row = repo.get(provider.id, provider.model)
        base = repo._now()
        prompt_hash = row["prompt_sha256"]
        window = row["window"]
        if holder == "unknown":
            entry = window["reservations"].pop(f"{second.job_id}:{second.lease_token}")
            window["reservations"][f"{second.job_id}:{uuid4()}"] = entry
        session.execute(
            update(profiles).values(
                state=asdict(
                    CapacityState(
                        current=100,
                        last_safe=50,
                        rps=10,
                        safe_bound=50,
                        last_safe_throughput=3,
                        latency_p95=12,
                    )
                ),
                window=window,
                window_started_at=base,
                updated_at=base,
            )
        )
    now = [base]
    monkeypatch.setattr(PostgresAnalysisCapacityRepository, "_now", lambda _: now[0])

    def observe(seconds, count):
        """只替换墙钟，聚合、成熟度、行锁与提交仍由生产Owner处理。"""
        now[0] += timedelta(seconds=seconds)
        delta = empty_window()
        delta.update(
            requests=count,
            persisted=count,
            cohort_requests=count,
            started=count,
            busy_seconds=100 * seconds,
            demand=True,
            sample_seconds=seconds,
        )
        delta["latency"][next(i for i, upper in enumerate(LATENCY_BUCKETS) if upper >= 12)] = count
        with runtime.database.new_session() as session, session.begin():
            repo = PostgresAnalysisCapacityRepository(session)
            delta["epoch"] = repo.get(provider.id, provider.model)["window"]["epoch"]
            return dict(
                repo.observe(
                    provider.id,
                    provider.model,
                    revision=provider.revision,
                    prompt_sha256=prompt_hash,
                    delta=delta,
                )
            )

    observe(2, 10)
    before = observe(2, 10)
    assert before["state"]["evidence_seconds"] == 4
    assert before["state"]["evidence_persisted"] == 20
    tail = observe(1, 0)
    assert tail["window"]["busy_seconds"] == 100  # 不足2秒的末次刷新没有闭窗。
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresAnalysisCapacityRepository(session)
        repo.release(provider.id, provider.model, first)
        released = repo.get(provider.id, provider.model)
        remaining = dict(tail["window"]["reservations"])
        remaining.pop(f"{first.job_id}:{first.lease_token}")
        assert released["window"]["reservations"] == remaining
        assert released["state"]["current"] == 100
        assert released["state"]["last_safe_throughput"] == 3
        assert released["state"]["evidence_persisted"] == (0 if holder == "last" else 20)
    if holder != "last":
        return  # 仍有持有者时既有C/RPS与共享候选都不能被无关退出清除。
    now[0] += timedelta(minutes=5)
    with runtime.database.new_session() as session, session.begin():
        repo = PostgresAnalysisCapacityRepository(session)
        reentered = repo.ensure(
            provider.id, provider.model, revision=provider.revision, prompt_sha256=prompt_hash
        )
        assert reentered.current == 100 and reentered.evidence_persisted == 0
    _allocation(runtime, provider, first, 100)
    after = observe(2, 30)
    assert after["state"]["current"] == 100
    assert after["state"]["reason"] == "collecting_capacity_evidence"
