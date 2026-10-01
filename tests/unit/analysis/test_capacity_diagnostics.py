"""容量诊断复用正式观察与日志入口；内存 Session 隔离数据库和外部请求。"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis_capacity import (
    LATENCY_BUCKETS,
    PostgresAnalysisCapacityRepository,
    empty_window,
)
from aima_ugc.bootstrap import analysis_capacity as feedback_module
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs import JobExecutionFence
from aima_ugc.platform.time import BEIJING_TIMEZONE


class _MemorySession:
    """只应用 SQL 参数到内存行，不构造 Engine 或连接业务数据库。"""

    def __init__(self, row, *, commit_error=False):
        """持有本用例专属行，可模拟提交失败。"""
        self.row = row
        self.commit_error = commit_error

    def execute(self, statement):
        """生产 Repository 的 UPDATE 使用同一批真实编译参数。"""
        if not statement.is_insert:
            # 夹具已有 Profile，生产 INSERT ON CONFLICT 必须保持该行而非覆盖。
            self.row.update(statement.compile().params)

    @contextmanager
    def begin(self):
        """提交异常恢复内存行，避免把失败提交当作有效观察。"""
        snapshot = deepcopy(self.row)
        try:
            yield
            if self.commit_error:
                raise RuntimeError("模拟提交失败")
        except BaseException:
            self.row.clear()
            self.row.update(snapshot)
            raise

    def close(self):
        """内存替身没有待释放的外部资源。"""


@pytest.mark.parametrize("kind", ["request_rate", "token_rate", "concurrency"])
def test_physical_feedback_preserves_explicit_rate_limit_classification(kind):
    """Adapter明确分类经过反馈聚合后保持一致，不能同时计作速率和并发拒绝。"""
    provider = ProviderConfig(
        id=uuid4(),
        provider="deepseek",
        provider_kind="llm",
        display_name="测试",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-flash",
        secret_ref="fake/key",
        enabled=True,
    )
    feedback = feedback_module.AnalysisCapacityFeedback(
        SimpleNamespace(),
        provider=provider,
        prompt_sha256="a" * 64,
        run_id=uuid4(),
    )
    now = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    feedback.started()
    feedback.finished()
    feedback.audit(
        LLMHTTPRequestAudit(
            http_request_id="fake",
            logical_request_id="fake",
            provider="deepseek",
            model="deepseek-flash",
            started_at=now,
            completed_at=now + timedelta(seconds=1),
            status="http_error",
            status_code=429,
            rate_limit_kind=kind,
        )
    )
    assert feedback._delta["rate_limited"] == 1
    assert feedback._delta["concurrency_limited"] == int(kind == "concurrency")
    assert feedback._delta["rate_only_limited"] == int(kind != "concurrency")
    assert feedback._cohorts[0]["concurrency_limited"] == int(kind == "concurrency")
    assert feedback._cohorts[0]["rate_only_limited"] == int(kind != "concurrency")


class _MemoryCapacityRepository(PostgresAnalysisCapacityRepository):
    """仅替换时钟与读写边界，窗口合并及控制判断使用生产实现。"""

    def __init__(self, session, now, job_id=None):
        """绑定显式时间与活动 Job，不查询外部状态。"""
        super().__init__(session)
        self.now = now
        self.job_id = job_id

    def get(self, provider_id, model, *, for_update=False):
        """返回本用例 Profile，支持生产 observe 的锁后读回。"""
        return self._session.row

    def _now(self):
        """返回受控墙钟以覆盖窗口关闭和任务间隔。"""
        return self.now

    def active_shards(self, provider_id, model):
        """本用例只有一片，不需要查询 Job 表。"""
        return (self.job_id,)

    def legacy_jobs(self, provider_id, model):
        """本用例不混入旧协议任务。"""
        return ()

    def reserve(self, provider_id, model, **kwargs):
        """内存测试只替换预留边界；真实跨事务预留在 PostgreSQL 用例验证。"""
        return min(kwargs["wanted"], self._session.row["state"]["current"]), 0


def _profile(base):
    """构造历史 P95 已学习、没有失败的五并发 Profile。"""
    window = empty_window()
    window["reservations"] = {
        "test": {"wanted": 200, "expires_at": (base + timedelta(hours=1)).isoformat()}
    }
    return dict(
        state=asdict(CapacityState(current=5, latency_p95=16)),
        window=window,
        revision=1,
        prompt_sha256="a" * 64,
        window_started_at=base,
        last_adjusted_at=base,
        updated_at=base,
    )


@pytest.mark.parametrize("before_hint,after_hint,expected", [(2500, None, 1000), (None, 500, 500)])
def test_endpoint_change_replaces_declared_hint_and_preserves_old_reservations(
    before_hint, after_hint, expected
):
    """提示属于当前连接身份；新增容量受新额度约束，旧在途预留仍保留。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["state"] = asdict(CapacityState(current=2000, last_safe=2000, declared_ceiling=before_hint))
    reservations = deepcopy(row["window"]["reservations"])
    repo = _MemoryCapacityRepository(_MemorySession(row), base)
    state = repo.ensure(
        None, "same-model", revision=2, prompt_sha256="a" * 64, declared_ceiling=after_hint
    )
    assert state.declared_ceiling == after_hint
    assert state.current == expected
    assert row["state"]["current"] == expected
    assert row["window"]["reservations"] == reservations


def test_omitted_hint_and_old_revision_do_not_overwrite_current_declaration():
    """旧配置与仅升级控制器的调用不能抹掉当前已核验声明。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["revision"] = 2
    row["state"] = asdict(CapacityState(current=50, declared_ceiling=2500))
    repo = _MemoryCapacityRepository(_MemorySession(row), base)
    assert (
        repo.ensure(None, "same-model", revision=2, prompt_sha256="a" * 64).declared_ceiling == 2500
    )
    assert (
        repo.ensure(
            None, "same-model", revision=1, prompt_sha256="a" * 64, declared_ceiling=None
        ).declared_ceiling
        == 2500
    )
    assert (
        repo.ensure(
            None, "same-model", revision=1, prompt_sha256="a" * 64, declared_ceiling=500
        ).declared_ceiling
        == 2500
    )


@pytest.mark.parametrize("seconds", [1, 24])
def test_diagnostics_do_not_change_window_or_capacity_state(seconds):
    """开启诊断与不开启的持久状态完全一致，且未闭窗不产生决策日志数据。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    rows = [_profile(base), _profile(base)]
    delta = empty_window()
    delta.update(
        requests=5, persisted=5, cohort_requests=5, started=10, busy_seconds=60.5, demand=True
    )
    delta["sample_seconds"] = seconds
    delta["latency"][next(i for i, upper in enumerate(LATENCY_BUCKETS) if upper >= 16)] = 5
    diagnostics = {}
    provider_id = uuid4()
    for row, sink in zip(rows, (None, diagnostics), strict=True):
        repository = _MemoryCapacityRepository(
            _MemorySession(row), base + timedelta(seconds=seconds)
        )
        repository.observe(
            provider_id,
            "test",
            revision=1,
            prompt_sha256="a" * 64,
            delta=deepcopy(delta),
            diagnostics=sink,
        )
    assert rows[0] == rows[1]
    if seconds == 1:
        assert diagnostics == {}
    else:
        assert diagnostics["reported_demand"] is True
        assert diagnostics["accepted_demand"] is True
        assert diagnostics["average_in_flight"] == 2.521
        assert diagnostics["reason"] == "exponential_probe"


def test_idle_gap_and_successful_tail_do_not_pollute_next_run():
    """低负载尾部不缩容，任务间空闲不进入下一次性能分母。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["state"] = asdict(CapacityState(current=10, latency_p95=16, throughput_ewma=1.2))
    repository = _MemoryCapacityRepository(_MemorySession(row), base + timedelta(seconds=13))
    provider_id = uuid4()
    delta = empty_window()
    delta.update(requests=1, persisted=1, busy_seconds=40, demand=False)
    delta["sample_seconds"] = 13
    delta["latency"][next(i for i, upper in enumerate(LATENCY_BUCKETS) if upper >= 64)] = 1
    diagnostics = {}
    repository.observe(
        provider_id,
        "test",
        revision=1,
        prompt_sha256="a" * 64,
        delta=delta,
        diagnostics=diagnostics,
    )
    assert row["state"]["current"] == 10
    assert diagnostics["requests"] == diagnostics["persisted"] == 1
    assert diagnostics["reason"] == "insufficient_demand_or_results"
    repository.now = base + timedelta(seconds=78)
    diagnostics = {}
    repository.observe(
        provider_id,
        "test",
        revision=1,
        prompt_sha256="a" * 64,
        delta=empty_window(),
        diagnostics=diagnostics,
    )
    assert diagnostics == {}
    assert row["state"]["current"] == 10
    assert row["window_started_at"] == base + timedelta(seconds=77)


@pytest.mark.parametrize("commit_error", [False, True])
def test_capacity_window_log_contains_actual_feedback_only_after_commit(
    monkeypatch, caplog, commit_error
):
    """真实审计反馈能解释未升速；失败提交不输出有效决策且反馈仍可重试。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    session = _MemorySession(row, commit_error=commit_error)
    fence = JobExecutionFence(job_id=uuid4(), lease_token=uuid4())
    monkeypatch.setattr(
        feedback_module,
        "PostgresAnalysisCapacityRepository",
        lambda session: _MemoryCapacityRepository(
            session, base + timedelta(seconds=24), fence.job_id
        ),
    )
    monkeypatch.setattr(
        feedback_module,
        "PostgresJobRepository",
        lambda session: SimpleNamespace(lock_current_execution=lambda fence: None),
    )
    from aima_ugc.bootstrap import analysis_high_throughput_planner

    monkeypatch.setattr(
        analysis_high_throughput_planner,
        "schedule_high_throughput_analysis_run_shards",
        lambda *args, **kwargs: None,
    )
    runtime = SimpleNamespace(
        database=SimpleNamespace(new_session=lambda: session),
        settings=SimpleNamespace(analysis_run_max_in_flight_jobs=8),
        logger=logging.getLogger("test.capacity_diagnostics"),
        job_window=lambda *args, **kwargs: 8,
    )
    provider = ProviderConfig(
        id=uuid4(),
        provider="test",
        display_name="测试",
        provider_kind="llm",
        base_url="https://example.invalid/v1",
        secret_ref="providers/test/key-1.key",
        enabled=True,
        model="test-model",
    )
    feedback = feedback_module.AnalysisCapacityFeedback(
        runtime, provider=provider, prompt_sha256="a" * 64, run_id=uuid4()
    )
    clock = [0.0]
    identity = [0]
    from aima_ugc.modules.analysis.capacity_telemetry import InFlightMeter

    feedback._meter = InFlightMeter(lambda: clock[0])
    feedback._sample_at = 0
    monkeypatch.setattr(feedback_module, "monotonic", lambda: 24.0)
    monkeypatch.setattr(feedback_module, "get_ident", lambda: identity[0])
    for index in range(5):
        identity[0] = index
        feedback.started()
    clock[0] = 12.1
    for index in range(5):
        identity[0] = index
        feedback.finished()
        feedback.audit(
            LLMHTTPRequestAudit(
                http_request_id=str(index),
                logical_request_id=str(index),
                provider="test",
                model="test-model",
                started_at=base,
                completed_at=base + timedelta(seconds=12.1),
                status="completed",
                status_code=200,
            )
        )
    feedback.persisted(succeeded=5, failed=0, validation_failed=0)
    with caplog.at_level(logging.INFO):
        if commit_error:
            with pytest.raises(RuntimeError, match="模拟提交失败"):
                feedback.refresh(fence, demand=True, force=True, pending_items=200)
        else:
            feedback.refresh(fence, demand=True, force=True, pending_items=200)
    windows = [r for r in caplog.records if getattr(r, "event", "") == "analysis.capacity_window"]
    if commit_error:
        assert windows == []
        assert feedback._delta["requests"] == 5
        assert feedback.target == 0
    else:
        assert len(windows) == 1
        record = windows[0]
        assert record.requests == record.persisted == 5
        assert record.started == 5
        assert record.pending_items == 200
        assert record.window_seconds == record.feedback_gap_seconds == 24
        assert record.accepted_demand is True and record.reported_demand is True
        assert record.in_flight_seconds == 60.5
        assert record.previous_concurrency == 5 and record.global_concurrency == 10
        assert record.reason == "exponential_probe"
        assert record.control_ms >= 0
    assert feedback.control_seconds >= 0


def test_late_rejections_from_old_epoch_cannot_cascade_capacity_shrink():
    """真实 1000→500 后迟到旧请求不能继续制造 250/125/62/31。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["state"] = asdict(CapacityState(current=1000))
    repo = _MemoryCapacityRepository(_MemorySession(row), base)
    provider_id = uuid4()
    values = []
    for index, count in enumerate((100, 75, 96, 57, 15), 1):
        repo.now = base + timedelta(seconds=index * 2.3)
        delta = empty_window()
        delta.update(
            epoch=0,
            rate_limited=count,
            requests=count,
            demand=True,
            sample_seconds=2.3,
            busy_seconds=2300,
            cohorts={0: {"requests": count, "rate_limited": count}},
        )
        repo.observe(provider_id, "test", revision=1, prompt_sha256="a" * 64, delta=delta)
        values.append(row["state"]["current"])
    assert values == [500] * 5
    # 真正在降档后发出的请求仍遭拒绝时，必须继续响应，不能屏蔽新拥塞。
    delta = empty_window()
    delta.update(
        requests=3,
        rate_limited=3,
        demand=True,
        sample_seconds=2.3,
        cohorts={row["window"]["epoch"]: {"requests": 3, "rate_limited": 3}},
    )
    repo.now += timedelta(seconds=2.3)
    repo.observe(provider_id, "test", revision=1, prompt_sha256="a" * 64, delta=delta)
    assert row["state"]["current"] == 250


@pytest.mark.parametrize("pending_items", [0, 182])
def test_refresh_reserves_physical_requests_instead_of_waiting_work(monkeypatch, pending_items):
    """派发 182 个 Future 但实际 HTTP 为零时必须恢复许可，不能保留幽灵占用。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    fence = JobExecutionFence(job_id=uuid4(), lease_token=uuid4())
    observed = []

    class Repository(_MemoryCapacityRepository):
        """读取正式反馈提交的物理占用，存储仅为隔离替身。"""

        def reserve(self, provider_id, model, **kwargs):
            """真实在途为零，等待工作数不应占据共享容量。"""
            observed.append(kwargs["occupied"])
            return super().reserve(provider_id, model, **kwargs)

    monkeypatch.setattr(
        feedback_module,
        "PostgresAnalysisCapacityRepository",
        lambda session: Repository(session, base, fence.job_id),
    )
    monkeypatch.setattr(
        feedback_module,
        "PostgresJobRepository",
        lambda session: SimpleNamespace(lock_current_execution=lambda fence: None),
    )
    from aima_ugc.bootstrap import analysis_high_throughput_planner

    monkeypatch.setattr(
        analysis_high_throughput_planner,
        "schedule_high_throughput_analysis_run_shards",
        lambda *a, **kw: None,
    )
    runtime = SimpleNamespace(
        database=SimpleNamespace(new_session=lambda: _MemorySession(row)),
        logger=logging.getLogger("test.physical_reservation"),
        settings=SimpleNamespace(analysis_run_max_in_flight_jobs=8),
        job_window=lambda *a, **kw: 8,
    )
    provider = ProviderConfig(
        id=uuid4(),
        provider="test",
        provider_kind="llm",
        display_name="测试",
        base_url="https://example.invalid/v1",
        secret_ref="providers/test/key",
        enabled=True,
        model="test",
    )
    feedback = feedback_module.AnalysisCapacityFeedback(
        runtime, provider=provider, prompt_sha256="a" * 64, run_id=uuid4()
    )
    feedback.refresh(fence, demand=False, pending_items=pending_items, force=True)
    assert observed == [0]
    assert (feedback.target > 0) == bool(pending_items)


def test_late_rate_rejections_cannot_repeatedly_lower_new_send_rate():
    """RPS 收紧同样切换发送阶段；旧速率的迟到拒绝不能再次压低新 RPS。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["state"] = asdict(CapacityState(current=100))
    repo = _MemoryCapacityRepository(_MemorySession(row), base)
    provider_id = uuid4()
    rates = []
    for index in range(3):
        repo.now = base + timedelta(seconds=(index + 1) * 2)
        delta = empty_window()
        delta.update(
            started=20 if index == 0 else 0,
            requests=3,
            rate_limited=3,
            rate_only_limited=3,
            demand=True,
            sample_seconds=2,
            cohorts={0: {"requests": 3, "rate_limited": 3, "rate_only_limited": 3}},
        )
        repo.observe(provider_id, "test", revision=1, prompt_sha256="a" * 64, delta=delta)
        rates.append(row["state"]["rps"])
    assert rates == [7.0] * 3
    delta["started"] = 10
    delta["cohorts"] = {
        row["window"]["epoch"]: {
            "requests": 3,
            "rate_limited": 3,
            "rate_only_limited": 3,
        }
    }
    repo.now += timedelta(seconds=2)
    repo.observe(provider_id, "test", revision=1, prompt_sha256="a" * 64, delta=delta)
    # 没有成熟当前结果的两段窗未关闭；本次新发送率按完整六秒窗口计算。
    assert row["state"]["rps"] == pytest.approx(10 / 6 * 0.7)


def test_healthy_rate_recovery_preserves_long_latency_cohort_maturity():
    """健康 RPS 恢复不能反复切换阶段，尚在途的同并发请求仍能提供成熟证据。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["state"] = asdict(CapacityState(current=100, rps=7))
    repo = _MemoryCapacityRepository(_MemorySession(row), base)
    rates = []
    for index in range(2):
        repo.now = base + timedelta(seconds=(index + 1) * 2)
        delta = empty_window()
        delta.update(
            started=20,
            requests=8,
            persisted=8,
            demand=True,
            local_limited=True,
            sample_seconds=2,
            busy_seconds=200,
            cohorts={0: {"requests": 8}},
        )
        diagnostics = {}
        repo.observe(
            uuid4(),
            "test",
            revision=1,
            prompt_sha256="a" * 64,
            delta=delta,
            diagnostics=diagnostics,
        )
        assert row["window"]["epoch"] == 0 and diagnostics["mature_cohort"]
        rates.append(row["state"]["rps"])
    assert rates == pytest.approx([8.05, 9.2575])


def test_idle_shard_does_not_dilute_available_send_rate(monkeypatch):
    """已归还 C 的退避分片不能仍分走 RPS；生产反馈消费 Owner 的原子速率份额。"""
    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    row = _profile(base)
    row["state"] = asdict(CapacityState(current=1, rps=10))
    fence = JobExecutionFence(job_id=uuid4(), lease_token=uuid4())

    class Repository(_MemoryCapacityRepository):
        """只替换数据库边界，模拟另一退避片仍有有效 Job Lease。"""

        def active_shards(self, *_args):
            """退避 Job 与 ready Job 都 running，不能按 Job 数均分速率。"""
            return (uuid4(), fence.job_id)

        def reserved_rps(self, *_args, **_kwargs):
            """Owner 已原子将空闲速率交给唯一可发送片。"""
            return 10

    monkeypatch.setattr(
        feedback_module,
        "PostgresAnalysisCapacityRepository",
        lambda session: Repository(session, base, fence.job_id),
    )
    monkeypatch.setattr(
        feedback_module,
        "PostgresJobRepository",
        lambda session: SimpleNamespace(lock_current_execution=lambda _fence: None),
    )
    from aima_ugc.bootstrap import analysis_high_throughput_planner

    monkeypatch.setattr(
        analysis_high_throughput_planner,
        "schedule_high_throughput_analysis_run_shards",
        lambda *a, **kw: None,
    )
    runtime = SimpleNamespace(
        database=SimpleNamespace(new_session=lambda: _MemorySession(row)),
        logger=logging.getLogger("test.rps_sharing"),
        settings=SimpleNamespace(analysis_run_max_in_flight_jobs=8),
        job_window=lambda *a, **kw: 8,
    )
    provider = ProviderConfig(
        id=uuid4(),
        provider="test",
        provider_kind="llm",
        display_name="测试",
        base_url="https://example.invalid/v1",
        secret_ref="providers/test/key",
        enabled=True,
        model="test",
    )
    feedback = feedback_module.AnalysisCapacityFeedback(
        runtime, provider=provider, prompt_sha256="a" * 64, run_id=uuid4()
    )
    feedback.refresh(fence, demand=True, force=True, pending_items=8)
    assert feedback.target == 1 and feedback.rps == 10
