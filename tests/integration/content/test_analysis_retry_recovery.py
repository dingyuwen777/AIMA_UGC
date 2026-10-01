"""专用 PostgreSQL 与本地 HTTP 中的正式打标恢复、探活和停止回归。"""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.llm import OpenAICompatibleContentLabelingLLM
from aima_ugc.adapters.persistence.postgres.analysis import PostgresAnalysisRepository
from aima_ugc.adapters.persistence.postgres.analysis_batch import PostgresAnalysisBatchRepository
from aima_ugc.adapters.persistence.postgres.analysis_capacity import (
    PostgresAnalysisCapacityRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_recovery import (
    AnalysisRetryWrite,
    PostgresAnalysisRecoveryRepository,
    TransportObservation,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState
from aima_ugc.modules.analysis.content_analysis_job import CONTENT_ANALYSIS_JOB_TYPE
from aima_ugc.modules.analysis.tables import (
    analysis_content_request_items_table as items,
)
from aima_ugc.modules.analysis.tables import analysis_content_requests_table as requests
from aima_ugc.modules.analysis.tables import (
    analysis_content_runs_table as runs,
)
from aima_ugc.modules.analysis.tables import (
    analysis_llm_capacity_profiles_table as profiles,
)
from aima_ugc.platform.jobs import JobExecutionContext, JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import event, func, select, text, update

from tests.integration.content.test_analysis_adaptive_capacity import _worker
from tests.integration.content.test_analysis_adaptive_capacity import runtime as runtime
from tests.integration.content.test_analysis_provider_concurrency import (
    _client,
    _controlled_http,
    _create_run,
    _seed_contents,
    _seed_provider,
    _valid_response,
)


def _planned(runtime, *, rows=8, shards=1, recovery_mode="recovery.v2"):
    """经真实 HTTP 创建及 Planner 投放；缩小冻结范围仅为多 Shard 测试夹具。"""

    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=rows)
    run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
    if recovery_mode != "recovery.v2":
        with runtime.database.engine.begin() as connection:
            snapshot = dict(
                connection.execute(
                    select(runs.c.runtime_config_snapshot).where(runs.c.id == run_id)
                ).scalar_one()
            )
            snapshot["recovery_mode"] = recovery_mode
            connection.execute(
                update(runs).where(runs.c.id == run_id).values(runtime_config_snapshot=snapshot)
            )
    if shards > 1:
        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(shard_size=rows // shards, shard_count=shards)
            )
            connection.execute(update(profiles).values(state=asdict(CapacityState(current=512))))
    worker = _worker(runtime)
    assert worker.run_once()
    return client, run_id, worker


def _claim(runtime, worker_id="recovery-claim"):
    """认领生产 Shard Job，以真实 Fence 读取当前冻结工作项。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            job = PostgresJobRepository(session).claim_next(
                supported_job_types=(CONTENT_ANALYSIS_JOB_TYPE,),
                worker_id=worker_id,
                lease_seconds=120,
            )
            assert job is not None and job.lease_token is not None
            fence = JobExecutionFence(job.id, job.lease_token)
            work = PostgresAnalysisRepository(session).load_pending(
                UUID(job.payload["request_id"]), limit=20
            )
            return fence, work
    finally:
        session.close()


def _persist_valid_work(session, fence, work_item):
    """测试夹具复用正式 Service/Validator 和 Owner，提交一条真实成功事实。"""
    from aima_ugc.adapters.persistence.postgres.analysis_batch import AnalysisSuccessWrite
    from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
        PostgresAnalysisSchemeRepository,
    )
    from aima_ugc.modules.analysis import (
        ContentLabelingService,
        FakeContentLabelingLLM,
        FrozenPromptTaxonomyLoader,
    )
    from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version

    run = PostgresAnalysisRepository(session).get_run(work_item.analysis_run_id)
    version = PostgresAnalysisSchemeRepository(session).get_version(
        run["analysis_scheme_version_id"]
    )
    identity = work_item.configuration_identity
    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(prompt_taxonomy_from_version(version)),
        llm=FakeContentLabelingLLM(
            responses=[_valid_response()],
            provider_name=identity.model_provider,
            model_name=identity.model,
        ),
    )
    result = service.label_contents([work_item.content], max_validation_retries=0).items[0]
    assert result.analysis_status == "succeeded"
    summary = PostgresAnalysisBatchRepository(session).persist_batch(
        fence=fence, successes=[AnalysisSuccessWrite(work_item, result.analysis)], failures=[]
    )
    assert summary.succeeded == 1


@contextmanager
def _http(monkeypatch, respond):
    """只在 127.0.0.1 的系统分配端口提供脚本响应，复用真实 Adapter/Transport Retry。"""

    lock = Lock()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            """不打印模型正文或测试连接信息。"""

        def do_POST(self):
            """读取正式 Adapter 的用户 JSON，按调用者场景返回 HTTP/模型输出。"""

            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.loads(body["messages"][1]["content"])
            with lock:
                calls.append(payload)
            code, result = respond(payload)
            data = (
                result
                if isinstance(result, bytes)
                else json.dumps({"choices": [{"message": {"content": result}}]}).encode()
            )
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    class Server(ThreadingHTTPServer):
        # 脚本响应可以等待并发屏障，记录锁和监听队列不能人为串行化物理请求。
        request_queue_size = 256

    server = Server(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def factory(**kwargs):
        """仅替换外部 origin，冻结配置、物理审计与生产业务实现仍真实执行。"""

        kwargs["base_url"] = f"http://127.0.0.1:{server.server_port}/v1"
        return OpenAICompatibleContentLabelingLLM(**kwargs)

    monkeypatch.setattr(
        "aima_ugc.bootstrap.analysis_concurrent_worker.OpenAICompatibleContentLabelingLLM", factory
    )
    try:
        yield calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_validation_exceeds_old_limit_then_succeeds_without_repeating_success(runtime, monkeypatch):
    """第七轮才合法的内容持续修复；同批第一轮成功内容不能重复发送。"""

    client, run_id, worker = _planned(runtime, rows=2)
    monkeypatch.setattr(
        "aima_ugc.adapters.persistence.postgres.analysis_recovery.retry_delay_seconds",
        lambda _count: 0,
    )
    counts = Counter()

    def respond(payload):
        """固定一条内容前六次不合规，另一条立即成功。"""

        title = payload["items"][0]["title"]
        counts[title] += 1
        return 200, "bad-json" if title.endswith("0") and counts[title] <= 6 else _valid_response()

    with _http(monkeypatch, respond) as calls:
        assert worker.run_once()
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "succeeded" and result["stats"]["succeeded"] == 2
    assert sorted(counts.values()) == [1, 7]
    repairs = [call for call in calls if "previous_validation_error_codes" in call]
    assert len(repairs) == 6
    assert all(call["previous_validation_error_codes"] == ["invalid_json"] for call in repairs)
    with runtime.database.engine.begin() as connection:
        rows = connection.execute(
            select(items.c.status, items.c.retry_count, items.c.validation_failure_started_at)
        ).all()
        assert rows == [("succeeded", 0, None), ("succeeded", 0, None)]
        # 成功来自业务结果；退出清空短尾窗，派生状态不得遗留容量持有者。
        assert connection.execute(select(profiles.c.window)).scalar_one()["reservations"] == {}
        assert (
            connection.execute(
                select(jobs_table.c.attempt).where(
                    jobs_table.c.job_type == CONTENT_ANALYSIS_JOB_TYPE
                )
            ).scalar_one()
            == 1
        )


def test_large_mixed_run_only_finishes_after_all_targets_are_successful(runtime, monkeypatch):
    """201条分三片，稀疏六轮格式错误保持pending，成功项不重发，末片也全部入库。"""
    client, run_id, worker = _planned(runtime, rows=201, shards=3)
    monkeypatch.setattr(
        "aima_ugc.adapters.persistence.postgres.analysis_recovery.retry_delay_seconds",
        lambda _count: 0,
    )
    counts = Counter()
    checked_pending = []

    def respond(payload):
        """最终合法响应返回前，经真实API核验父任务仍未成功完成。"""
        title = payload["items"][0]["title"]
        counts[title] += 1
        if title == "Provider Concurrency 0":
            if counts[title] <= 6:
                return 200, "bad-json"
            state = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
            assert state["status"] != "succeeded" and state["stats"]["pending"] > 0
            checked_pending.append(True)
        return 200, _valid_response()

    with _http(monkeypatch, respond):
        for _ in range(3):
            assert worker.run_once()
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert checked_pending == [True]
    assert result["status"] == "succeeded"
    assert result["stats"] == dict(pending=0, succeeded=201, failed=0, stale=0, cancelled=0)
    assert sorted(counts.values()) == [1] * 200 + [7]
    with runtime.database.engine.begin() as connection:
        assert connection.execute(select(profiles.c.window)).scalar_one()["reservations"] == {}


def test_transport_exhaustion_stays_pending_then_probe_recovers(runtime, monkeypatch):
    """五次物理 503 耗尽后仍 pending，第六次探活成功继续原 Item，不消耗 Job attempt。"""

    client, run_id, worker = _planned(runtime, rows=1)
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying._retry_delay_seconds", lambda _attempt: 0)
    monkeypatch.setattr(
        "aima_ugc.adapters.persistence.postgres.analysis_recovery.retry_delay_seconds",
        lambda _count: 0,
    )
    attempts = 0

    def respond(_payload):
        """在首次恢复轮次读取已持久 pending，而非把失败伪装成成功。"""

        nonlocal attempts
        attempts += 1
        if attempts == 6:
            with runtime.database.engine.begin() as connection:
                row = connection.execute(select(items)).mappings().one()
                assert (
                    row["status"] == "pending"
                    and row["error_code"] is None
                    and row["retry_kind"] == "transport"
                )
        return (503, "") if attempts <= 5 else (200, _valid_response())

    with _http(monkeypatch, respond):
        assert worker.run_once()
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "succeeded" and result["stats"]["failed"] == 0 and attempts == 6
    with runtime.database.engine.begin() as connection:
        row = connection.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
        assert (
            row["transport_failure_started_at"] is None
            and row["last_transport_success_at"] is not None
        )


def test_validation_window_survives_transport_failure_and_restart(runtime, monkeypatch):
    """Transport 成功不能清掉问题 Item 的窗口；新 Session 读起点且五分钟停止父 Run。"""

    _, run_id, _ = _planned(runtime, rows=2)
    # 此用例验证历史 v1，不把新 v2 的持续格式修复改回整批停止。
    with runtime.database.engine.begin() as connection:
        snapshot = dict(
            connection.execute(
                select(runs.c.runtime_config_snapshot).where(runs.c.id == run_id)
            ).scalar_one()
        )
        snapshot["recovery_mode"] = "recovery.v1"
        connection.execute(
            update(runs).where(runs.c.id == run_id).values(runtime_config_snapshot=snapshot)
        )
    fence, work = _claim(runtime)
    session = runtime.database.new_session()
    try:
        with session.begin():
            repository = PostgresAnalysisRecoveryRepository(session)
            start = repository._now()
            repository.defer(
                fence=fence, retries=[AnalysisRetryWrite(work[0], "validation", ("invalid_json",))]
            )
        with session.begin():
            persisted = PostgresAnalysisRepository(session).load_pending(
                work[0].request_id, limit=2
            )[0]
            PostgresAnalysisRecoveryRepository(session).defer(
                fence=fence, retries=[AnalysisRetryWrite(persisted, "transport", ("timeout",))]
            )
            row = (
                session.execute(select(items).where(items.c.content_id == work[0].content_id))
                .mappings()
                .one()
            )
            assert row["retry_count"] == 2 and row["validation_failure_started_at"] >= start
            failure_at = row["validation_failure_started_at"]
    finally:
        session.close()
    session = runtime.database.new_session()
    try:
        monkeypatch.setattr(
            PostgresAnalysisRecoveryRepository,
            "_now",
            lambda _self: failure_at + timedelta(seconds=299),
        )
        with session.begin():
            assert PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence,
                run_id=run_id,
                observation=TransportObservation(success_at=failure_at + timedelta(seconds=299)),
            ) == (None, False)
        monkeypatch.setattr(
            PostgresAnalysisRecoveryRepository,
            "_now",
            lambda _self: failure_at + timedelta(seconds=300),
        )
        with session.begin():
            error, _ = PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence,
                run_id=run_id,
                observation=TransportObservation(success_at=failure_at + timedelta(seconds=299)),
            )
            assert error == "llm_validation_unhealthy"
            assert PostgresAnalysisRepository(session).refresh_run(run_id) == "failed"
    finally:
        session.close()


def test_shared_transport_orders_feedback_and_claims_only_one_probe(runtime, monkeypatch):
    """跨 Shard 迟到错误不覆盖新的 2xx，同一 Run 的探活必须互斥且可在 Lease 过期后接管。"""

    _, run_id, _ = _planned(runtime, shards=2)
    first, _ = _claim(runtime, "probe-a")
    second, _ = _claim(runtime, "probe-b")
    session = runtime.database.new_session()
    try:
        with session.begin():
            repo = PostgresAnalysisRecoveryRepository(session)
            now = repo._now()
            assert repo.refresh(
                fence=first,
                run_id=run_id,
                observation=TransportObservation(failure_started_at=now, last_failure_at=now),
            ) == (None, True)
            assert repo.claim_probe(fence=first, run_id=run_id) == (True, True)
            assert repo.claim_probe(fence=second, run_id=run_id) == (False, True)
        with session.begin():
            repo = PostgresAnalysisRecoveryRepository(session)
            assert repo.refresh(
                fence=second,
                run_id=run_id,
                observation=TransportObservation(success_at=now + timedelta(seconds=1)),
            ) == (None, False)
            assert repo.refresh(
                fence=first,
                run_id=run_id,
                observation=TransportObservation(failure_started_at=now, last_failure_at=now),
            ) == (None, False)
            assert repo.refresh(
                fence=first,
                run_id=run_id,
                observation=TransportObservation(
                    failure_started_at=now + timedelta(seconds=2),
                    last_failure_at=now + timedelta(seconds=2),
                ),
            ) == (None, True)
            assert repo.claim_probe(fence=first, run_id=run_id) == (True, True)
        with session.begin():
            session.execute(
                update(jobs_table)
                .where(jobs_table.c.id == first.job_id)
                .values(lease_expires_at=now - timedelta(seconds=1))
            )
            assert PostgresAnalysisRecoveryRepository(session).claim_probe(
                fence=second, run_id=run_id
            ) == (True, True)
        with pytest.raises(LeaseLostError), session.begin():
            PostgresAnalysisRecoveryRepository(session).refresh(fence=first, run_id=run_id)
    finally:
        session.close()


def test_transport_health_stops_at_five_minutes_without_waiting_for_logical_result(
    runtime, monkeypatch
):
    """物理首错先持久化，逻辑结果尚未完成也触发五分钟停止，其他 Run 不受影响。"""

    client, run_id, _ = _planned(runtime)
    fence, work = _claim(runtime)
    other_run_id = UUID(
        _create_run(
            client, [item.content_id for item in work], runtime, key=str(uuid4()), legacy=False
        )
    )
    session = runtime.database.new_session()
    try:
        with session.begin():
            start = session.scalar(select(func.clock_timestamp()))
            PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence,
                run_id=run_id,
                observation=TransportObservation(failure_started_at=start, last_failure_at=start),
            )
        monkeypatch.setattr(
            PostgresAnalysisRecoveryRepository, "_now", lambda _self: start + timedelta(seconds=299)
        )
        with session.begin():
            assert PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence, run_id=run_id
            ) == (None, True)
        monkeypatch.setattr(
            PostgresAnalysisRecoveryRepository, "_now", lambda _self: start + timedelta(seconds=300)
        )
        with session.begin():
            assert (
                PostgresAnalysisRecoveryRepository(session).refresh(
                    fence=fence,
                    run_id=run_id,
                    observation=TransportObservation(
                        failure_started_at=start + timedelta(seconds=300),
                        last_failure_at=start + timedelta(seconds=300),
                    ),
                )[0]
                == "llm_transport_unavailable"
            )
            repo = PostgresAnalysisRepository(session)
            assert repo.refresh_run(run_id) == "failed"
            assert (
                repo.complete_plan_terminal(run_id=run_id, job_status="succeeded", error_code=None)
                == "failed"
            )
            assert repo.get_run(other_run_id)["status"] == "queued"
    finally:
        session.close()


def test_systemic_failure_stops_siblings_and_unscheduled_shards(runtime):
    """两个运行 Shard 的认证失败停止父 Run，尚未投放的第三 Shard 也不能再发送。"""

    client, run_id, worker = _planned(runtime, rows=12, shards=3)
    with _controlled_http(expected=8, block_all=True, status=401) as (
        arrived,
        release,
        bodies,
        _adapters,
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(value.run_once) for value in (worker, _worker(runtime))]
            try:
                assert arrived.wait(5)
            finally:
                release.set()
            assert all(future.result(timeout=5) for future in futures)
        # Runtime 可能还领取已有队列；已经失败的 Run 绝不创建后续 Shard。
        for _ in range(4):
            if not worker.run_once():
                break
        assert len(bodies) == 8
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "failed" and result["error_code"] == "llm_http_401"
    assert result["stats"]["pending"] == 0 and result["stats"]["failed"] == 12


@pytest.mark.parametrize("stop_kind", ["cancel", "lease", "deadline"])
def test_new_recovery_http_wait_respects_cancel_fence_and_deadline(runtime, monkeypatch, stop_kind):
    """新恢复协议等待物理回包期间也轮询控制，失权后不重试或提交成功结果。"""

    client, run_id, worker = _planned(runtime, rows=2)
    observed = Event()
    original = JobExecutionContext.cancel_requested

    def observe(context):
        """只观测正式控制入口，不替代取消、租约和 Deadline 判定。"""

        try:
            cancelled = original(context)
        except LeaseLostError:
            observed.set()
            raise
        if cancelled:
            observed.set()
        return cancelled

    monkeypatch.setattr(JobExecutionContext, "cancel_requested", observe)
    original_lock = PostgresJobRepository.lock_current_execution

    def observe_lock(repository, fence):
        """取消也可能先由下一次业务短事务的 Fence 拦截，观测同一停止边界。"""

        try:
            return original_lock(repository, fence)
        except LeaseLostError:
            observed.set()
            raise

    monkeypatch.setattr(PostgresJobRepository, "lock_current_execution", observe_lock)
    with _controlled_http(
        expected=2, block_all=True, status=200 if stop_kind == "lease" else 503
    ) as (arrived, release, bodies, _adapters):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker.run_once)
            try:
                assert arrived.wait(4)
                if stop_kind == "cancel":
                    assert (
                        client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code
                        == 200
                    )
                else:
                    column = "lease_expires_at" if stop_kind == "lease" else "attempt_deadline_at"
                    expiration = {column: text("statement_timestamp() - interval '1 second'")}
                    if stop_kind == "deadline":
                        expiration.update(
                            attempt_started_at=text("statement_timestamp() - interval '2 seconds'"),
                            lease_expires_at=text("statement_timestamp() - interval '1 second'"),
                        )
                    with runtime.database.engine.begin() as connection:
                        connection.execute(
                            update(jobs_table)
                            .where(
                                jobs_table.c.status == "running",
                                jobs_table.c.job_type == CONTENT_ANALYSIS_JOB_TYPE,
                            )
                            .values(**expiration)
                        )
                assert observed.wait(3)
            finally:
                release.set()
            assert future.result(timeout=5)
        assert len(bodies) == 2
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["stats"]["succeeded"] == 0
    if stop_kind == "cancel":
        assert result["status"] == "cancelled" and result["stats"]["cancelled"] == 2


def test_future_retry_does_not_block_cancel_or_occupy_http_threads(runtime, monkeypatch):
    """全是未来 ready-at 的 pending 仍响应取消，退避期间没有物理发送。"""

    client, run_id, worker = _planned(runtime, rows=2)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(items).values(
                retry_kind="validation",
                retry_count=1,
                validation_error_codes=["invalid_json"],
                validation_failure_started_at=func.clock_timestamp(),
                retry_not_before=func.clock_timestamp() + text("interval '30 seconds'"),
            )
        )
    polled = Event()
    original = PostgresAnalysisRepository.load_pending_page

    def observe(repository, *args, **kwargs):
        """确认生产 ready-at 分页已经开始等待，再从公开 HTTP 取消。"""

        result = original(repository, *args, **kwargs)
        if kwargs.get("recovery"):
            polled.set()
        return result

    monkeypatch.setattr(PostgresAnalysisRepository, "load_pending_page", observe)
    with _http(monkeypatch, lambda _payload: (200, _valid_response())) as calls:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker.run_once)
            assert polled.wait(3)
            assert client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code == 200
            assert future.result(timeout=4)
        assert calls == []
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "cancelled" and result["stats"]["cancelled"] == 2


@pytest.mark.parametrize("bad_output", [b"broken-json", b'{"choices":[]}', "", ["wrong-type"]])
def test_http_200_output_errors_use_validation_recovery(runtime, monkeypatch, bad_output):
    """2xx 外层/空内容/类型错误偶发后可恢复，不能误判认证错误或 Transport 故障。"""

    client, run_id, worker = _planned(runtime, rows=1)
    monkeypatch.setattr(
        "aima_ugc.adapters.persistence.postgres.analysis_recovery.retry_delay_seconds",
        lambda _count: 0,
    )
    attempts = 0

    def respond(_payload):
        """第二次发送前核实 Validation 窗口已持久且 Job attempt 未被消耗。"""

        nonlocal attempts
        attempts += 1
        if attempts == 2:
            with runtime.database.engine.begin() as connection:
                row = connection.execute(select(items)).mappings().one()
                assert row["retry_kind"] == "validation"
                assert row["validation_failure_started_at"] is not None
                assert connection.scalar(select(runs.c.transport_failure_started_at)) is None
        return 200, bad_output if attempts == 1 else _valid_response()

    with _http(monkeypatch, respond):
        assert worker.run_once()
    assert attempts == 2
    assert client.get(f"/api/v1/analysis/content-runs/{run_id}").json()["status"] == "succeeded"


def test_continuous_empty_http_200_stops_validation_window(runtime, monkeypatch):
    """历史 v1 空输出保持五分钟停止，不能用新要求改写冻结 Snapshot。"""

    client, run_id, worker = _planned(runtime, rows=1, recovery_mode="recovery.v1")
    original = PostgresAnalysisRecoveryRepository.defer

    def age_window(repository, **kwargs):
        """在专用库推进 Item 测试起点，不修改系统时钟或真实 Job Deadline。"""

        original(repository, **kwargs)
        repository._session.execute(
            update(items).values(
                validation_failure_started_at=func.clock_timestamp()
                - text("interval '300 seconds'"),
                retry_not_before=func.clock_timestamp() + text("interval '30 seconds'"),
            )
        )

    monkeypatch.setattr(PostgresAnalysisRecoveryRepository, "defer", age_window)
    with _http(monkeypatch, lambda _payload: (200, "")) as calls:
        assert worker.run_once()
        assert len(calls) == 1
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["error_code"] == "llm_validation_unhealthy"
    assert result["stats"]["pending"] == 0 and result["stats"]["failed"] == 1


def test_concurrent_cancel_and_health_refresh_use_job_then_run_lock_order(runtime):
    """Worker 已锁 Job、取消正等该 Job 时，Worker 仍可锁 Run 并有界提交。"""

    _, run_id, _ = _planned(runtime, rows=2)
    fence, _ = _claim(runtime)
    locked = Event()
    cancel_waiting = Event()

    def observe(_connection, _cursor, statement, parameters, _context, _many):
        """用实际 SQL 的锁等待位置构造过去 Job/Run 死锁的交错时序。"""

        if (
            current_thread().name.startswith("recovery-cancel")
            and "FOR UPDATE" in statement
            and str(fence.job_id) in str(parameters)
        ):
            cancel_waiting.set()

    def health():
        """持有正式 Fence 的 Job 行锁后，等取消开始抢锁再进入健康刷新。"""

        with runtime.database.new_session() as session, session.begin():
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
            PostgresJobRepository(session).lock_current_execution(fence)
            locked.set()
            assert cancel_waiting.wait(3)
            assert PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence, run_id=run_id
            ) == (None, False)

    def cancel():
        """与 HTTP 入口相同的 Owner 方法和短事务，不绕开取消实现。"""

        assert locked.wait(3)
        with runtime.database.new_session() as session, session.begin():
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
            PostgresAnalysisRepository(session).request_run_cancel(run_id)

    event.listen(runtime.database.engine, "before_cursor_execute", observe)
    try:
        with (
            ThreadPoolExecutor(max_workers=1) as health_pool,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="recovery-cancel") as cancel_pool,
        ):
            first = health_pool.submit(health)
            second = cancel_pool.submit(cancel)
            first.result(timeout=6)
            second.result(timeout=6)
    finally:
        event.remove(runtime.database.engine, "before_cursor_execute", observe)
    with runtime.database.engine.begin() as connection:
        assert connection.scalar(select(runs.c.cancel_requested_at)) is not None
        assert (
            connection.scalar(
                select(jobs_table.c.cancel_requested_at).where(jobs_table.c.id == fence.job_id)
            )
            is not None
        )


def test_success_batch_reads_only_its_own_pending_identities(runtime, monkeypatch):
    """错开成功结果仍按时间/尾部批量提交，每次幂等读取只涉及当前批次。"""

    client, run_id, worker = _planned(runtime, rows=80)
    batches = []
    reads = []
    original = PostgresAnalysisBatchRepository.persist_batch

    def persist(repository, **kwargs):
        """只记录生产批次大小，保留真实版本、配置、幂等和成功写入。"""

        batches.append(len(kwargs["successes"]))
        return original(repository, **kwargs)

    def read_rows(_connection, cursor, statement, _parameters, _context, _many):
        """读取 SQL 返回数证明不加载整片 pending，避免只检查构造的 Query。"""

        if statement.startswith(
            "SELECT analysis_content_request_items.request_id, "
            "analysis_content_request_items.content_id"
        ):
            reads.append(cursor.rowcount)

    def respond(_payload):
        """错开物理完成，逐次强刷会明显增加事务数量。"""

        sleep(0.015)
        return 200, _valid_response()

    monkeypatch.setattr(PostgresAnalysisBatchRepository, "persist_batch", persist)
    event.listen(runtime.database.engine, "after_cursor_execute", read_rows)
    try:
        with _http(monkeypatch, respond):
            assert worker.run_once()
    finally:
        event.remove(runtime.database.engine, "after_cursor_execute", read_rows)
    assert sum(batches) == 80 and 1 < len(batches) < 20
    assert reads == batches
    assert client.get(f"/api/v1/analysis/content-runs/{run_id}").json()["stats"]["succeeded"] == 80


@pytest.mark.parametrize("success_first", [True, False])
def test_success_between_failure_spans_keeps_exact_new_window(runtime, success_first):
    """另一个 Shard 的成功位于同窗多次失败之间，首错不能跳到最后一次错误。"""

    _, run_id, _ = _planned(runtime, shards=2)
    first, _ = _claim(runtime, "order-a")
    second, _ = _claim(runtime, "order-b")
    with runtime.database.new_session() as session:
        start = PostgresAnalysisRecoveryRepository(session)._now()
    failure = TransportObservation(
        failure_spans=tuple(
            (start + timedelta(seconds=index), start + timedelta(seconds=index))
            for index in (0, 2, 3)
        )
    )
    success = TransportObservation(success_at=start + timedelta(seconds=1))
    observations = (
        ((second, success), (first, failure))
        if success_first
        else ((first, failure), (second, success))
    )
    for fence, observation in observations:
        with runtime.database.new_session() as session, session.begin():
            PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence,
                run_id=run_id,
                observation=observation,
            )
    for _ in range(2):
        with runtime.database.new_session() as session, session.begin():
            assert PostgresAnalysisRecoveryRepository(session).refresh(
                fence=first,
                run_id=run_id,
            ) == (None, True)
            assert session.scalar(select(runs.c.transport_failure_started_at)) == (
                start + timedelta(seconds=2)
            )


def test_persisted_failure_overflow_survives_late_success_and_stops(runtime, monkeypatch):
    """高频失败压缩后跨 Session 合并迟到成功，健康轮询不能遗失窗口或延期停止。"""

    _, run_id, _ = _planned(runtime, shards=2, recovery_mode="recovery.v1")
    first, _ = _claim(runtime, "overflow-a")
    second, _ = _claim(runtime, "overflow-b")
    with runtime.database.new_session() as session:
        start = PostgresAnalysisRecoveryRepository(session)._now()
    with runtime.database.new_session() as session, session.begin():
        PostgresAnalysisRecoveryRepository(session).refresh(
            fence=first,
            run_id=run_id,
            observation=TransportObservation(
                failure_spans=tuple(
                    (start + timedelta(milliseconds=i), start + timedelta(milliseconds=i))
                    for i in range(6000)
                )
            ),
        )
        assert len(session.scalar(select(runs.c.transport_failure_spans))) <= 4096
    success_at = start + timedelta(seconds=1)
    with runtime.database.new_session() as session, session.begin():
        assert PostgresAnalysisRecoveryRepository(session).refresh(
            fence=second,
            run_id=run_id,
            observation=TransportObservation(success_at=success_at),
        ) == (None, True)
        failure_at = session.scalar(select(runs.c.transport_failure_started_at))
        assert success_at < failure_at <= success_at + timedelta(milliseconds=1)
    for _ in range(2):
        with runtime.database.new_session() as session, session.begin():
            assert PostgresAnalysisRecoveryRepository(session).refresh(
                fence=first,
                run_id=run_id,
            ) == (None, True)
            assert session.scalar(select(runs.c.transport_failure_started_at)) == failure_at
    monkeypatch.setattr(
        PostgresAnalysisRecoveryRepository, "_now", lambda _: failure_at + timedelta(seconds=300)
    )
    with runtime.database.new_session() as session, session.begin():
        assert (
            PostgresAnalysisRecoveryRepository(session).refresh(
                fence=first,
                run_id=run_id,
            )[0]
            == "llm_transport_unavailable"
        )


def test_failed_run_list_tracks_queued_and_running_execution_until_settled(runtime):
    """真实列表不带 Shard 明细，仍能指示收尾；关联 Job 全终态后才停止刷新。"""

    client, run_id, _ = _planned(runtime, shards=2)
    first, _ = _claim(runtime)
    with runtime.database.new_session() as session, session.begin():
        PostgresAnalysisRecoveryRepository(session).refresh(
            fence=first,
            run_id=run_id,
            stop_error="llm_validation_unhealthy",
        )
    response = client.get("/api/v1/analysis/content-runs").json()["items"][0]
    assert response["status"] == "failed" and response["shards"] == []
    assert response["execution_settling"] is True and response["stats"]["pending"] == 0
    with runtime.database.new_session() as session, session.begin():
        PostgresJobRepository(session).fail_permanent(
            job_id=first.job_id,
            lease_token=first.lease_token,
            error_code="llm_validation_unhealthy",
        )
    assert (
        client.get("/api/v1/analysis/content-runs").json()["items"][0]["execution_settling"] is True
    )
    second, _ = _claim(runtime, "queued-sibling")
    with runtime.database.new_session() as session, session.begin():
        PostgresJobRepository(session).fail_permanent(
            job_id=second.job_id,
            lease_token=second.lease_token,
            error_code="llm_validation_unhealthy",
        )
    response = client.get("/api/v1/analysis/content-runs").json()["items"][0]
    assert response["execution_settling"] is False and response["shards"] == []


@pytest.mark.parametrize("revision", ["0076_analysis_llm_capacity", "0077_analysis_retry_recovery"])
@pytest.mark.parametrize("job_status", ["queued", "running"])
def test_downgrade_rejects_failed_run_with_unsettled_jobs(
    runtime, monkeypatch, revision, job_status
):
    """父 Run 已失败但还有排队/运行 Shard，仍不能删除恢复或容量状态。"""

    _, run_id, _ = _planned(runtime, rows=2)
    if job_status == "running":
        _claim(runtime)
    path = Path(__file__).resolve().parents[3] / f"migrations/versions/20260930_{revision}.py"
    spec = spec_from_file_location("test_downgrade", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(runs)
            .where(runs.c.id == run_id)
            .values(status="failed", error_code="llm_validation_unhealthy")
        )
        monkeypatch.setattr(module.op, "get_bind", lambda: connection)
        with pytest.raises(RuntimeError, match="未结束"):
            module.downgrade()


def test_parent_stop_is_terminal_with_queued_sibling_and_inflight_http(runtime):
    """停止即时投影 pending=0，随后仍保存合法在途结果，排队 sibling 不能再发送。"""

    client, run_id, worker = _planned(runtime, rows=4, shards=2)
    with _controlled_http(expected=2, block_all=True) as (arrived, release, bodies, _adapters):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker.run_once)
            try:
                assert arrived.wait(4)
                with runtime.database.new_session() as session, session.begin():
                    job = (
                        session.execute(
                            select(jobs_table).where(
                                jobs_table.c.status == "running",
                                jobs_table.c.job_type == CONTENT_ANALYSIS_JOB_TYPE,
                            )
                        )
                        .mappings()
                        .one()
                    )
                    PostgresAnalysisRecoveryRepository(session).refresh(
                        fence=JobExecutionFence(job["id"], job["lease_token"]),
                        run_id=run_id,
                        stop_error="llm_validation_unhealthy",
                    )
                immediate = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
                assert immediate["status"] == "failed"
                assert immediate["stats"]["pending"] == 0 and immediate["stats"]["failed"] == 4
                assert sorted(shard["status"] for shard in immediate["shards"]) == [
                    "queued",
                    "running",
                ]
            finally:
                release.set()
            assert future.result(timeout=5)
        assert worker.run_once()
        assert len(bodies) == 2
    final = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert final["status"] == "failed" and final["stats"]["pending"] == 0
    assert final["stats"]["succeeded"] == 2 and final["stats"]["failed"] == 2


def test_v2_old_validation_error_keeps_retrying_and_unscheduled_contents_finish(
    runtime, monkeypatch
):
    """超过五分钟的格式错误仍能修复；第三片未投放数据也全部成功，不重发成功项。"""
    client, run_id, worker = _planned(runtime, rows=12, shards=3)
    with runtime.database.engine.begin() as connection:
        first = connection.execute(
            select(items.c.content_id).order_by(items.c.ordinal).limit(1)
        ).scalar_one()
        connection.execute(
            update(items)
            .where(items.c.content_id == first)
            .values(
                validation_failure_started_at=func.clock_timestamp() - timedelta(minutes=10),
                validation_error_codes=["invalid_json"],
                retry_count=7,
                retry_kind="validation",
            )
        )
    monkeypatch.setattr(
        "aima_ugc.adapters.persistence.postgres.analysis_recovery.retry_delay_seconds",
        lambda _count: 0,
    )
    counts = Counter()

    def respond(payload):
        """一条继续返回无效输出后恢复，其他内容始终合法。"""
        title = payload["items"][0]["title"]
        counts[title] += 1
        return 200, "bad-json" if title == "Provider Concurrency 0" and counts[
            title
        ] <= 2 else _valid_response()

    with _http(monkeypatch, respond) as calls:
        for _ in range(3):
            assert worker.run_once()
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "succeeded"
    assert result["stats"] == dict(pending=0, succeeded=12, failed=0, stale=0, cancelled=0)
    assert len(calls) == 14 and sorted(counts.values()) == [1] * 11 + [3]
    with runtime.database.engine.begin() as connection:
        assert (
            connection.execute(
                select(runs.c.runtime_config_snapshot).where(runs.c.id == run_id)
            ).scalar_one()["recovery_mode"]
            == "recovery.v2"
        )
        assert (
            connection.execute(
                select(func.count()).select_from(items).where(items.c.status == "pending")
            ).scalar_one()
            == 0
        )


def test_v2_single_network_error_and_local_wait_cannot_prove_five_minute_outage(
    runtime, monkeypatch
):
    """只有又发生真实发送错误才能证明连续五分钟不可达，本地等待不是证据。"""
    _, run_id, _ = _planned(runtime, rows=2)
    fence, _ = _claim(runtime)
    with runtime.database.new_session() as session:
        repository = PostgresAnalysisRecoveryRepository(session)
        with session.begin():
            now = repository._now()
            assert repository.refresh(
                fence=fence,
                run_id=run_id,
                observation=TransportObservation(failure_started_at=now, last_failure_at=now),
            ) == (None, True)
        monkeypatch.setattr(
            PostgresAnalysisRecoveryRepository, "_now", lambda _self: now + timedelta(seconds=301)
        )
        with session.begin():
            assert repository.refresh(fence=fence, run_id=run_id) == (None, True)
        with session.begin():
            assert repository.refresh(
                fence=fence,
                run_id=run_id,
                observation=TransportObservation(
                    failure_started_at=now + timedelta(seconds=301),
                    last_failure_at=now + timedelta(seconds=301),
                ),
            ) == ("llm_transport_unavailable", True)


@pytest.mark.parametrize("rollback", [False, True])
def test_v2_deadline_exhaustion_continues_same_items_without_repeating_success(
    runtime, monkeypatch, rollback
):
    """三次 Attempt 耗尽只结束执行周期，持久恢复项由同 Request 后继 Job 接续。"""
    from aima_ugc.bootstrap.analysis_high_throughput_planner import (
        create_high_throughput_analysis_job_terminal_callback,
    )
    from aima_ugc.bootstrap.worker import create_collection_job_registry
    from aima_ugc.platform.jobs.worker import JobReaper

    client, run_id, worker = _planned(runtime, rows=3)
    fence, work = _claim(runtime)
    with runtime.database.new_session() as session, session.begin():
        _persist_valid_work(session, fence, work[2])
        PostgresAnalysisRecoveryRepository(session).defer(
            fence=fence, retries=[AnalysisRetryWrite(work[0], "validation", ("invalid_json",))]
        )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == fence.job_id)
            .values(
                attempt=3,
                attempt_deadline_at=func.clock_timestamp() - timedelta(seconds=1),
                attempt_started_at=func.clock_timestamp() - timedelta(seconds=1801),
                lease_expires_at=func.clock_timestamp() - timedelta(seconds=2),
            )
        )
        connection.execute(update(items).values(retry_not_before=None))
    reaper = JobReaper(
        session_factory=runtime.database.new_session,
        registry=create_collection_job_registry(runtime=runtime),
        retry_delay_seconds=0,
    )
    if rollback:
        original_enqueue = PostgresJobRepository.enqueue

        def fail_after_enqueue(repository, **kwargs):
            """正式后继已插入但未切换 Request 时注入失败，验证整个终态事务回滚。"""
            successor = original_enqueue(repository, **kwargs)
            if kwargs["internal_idempotency_key"].startswith("content-analysis-continuation:"):
                raise RuntimeError("continuation transaction rollback")
            return successor

        with monkeypatch.context() as patch:
            patch.setattr(PostgresJobRepository, "enqueue", fail_after_enqueue)
            with pytest.raises(RuntimeError, match="continuation transaction rollback"):
                reaper.run_once()
        with runtime.database.new_session() as session, session.begin():
            assert session.scalar(select(requests.c.job_id)) == fence.job_id
            assert PostgresJobRepository(session).get(fence.job_id).status == "running"
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(jobs_table)
                    .where(
                        jobs_table.c.internal_idempotency_key.like(
                            "content-analysis-continuation:%"
                        )
                    )
                )
                == 0
            )
    assert reaper.run_once()
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert (
        result["status"] == "running"
        and result["stats"]["pending"] == 2
        and result["stats"]["succeeded"] == 1
        and result["stats"]["failed"] == 0
    )
    with runtime.database.new_session() as session, session.begin():
        old_job = PostgresJobRepository(session).get(fence.job_id)
        successor_id = session.scalar(
            select(requests.c.job_id).where(requests.c.id == work[0].request_id)
        )
        assert successor_id != fence.job_id
        assert PostgresJobRepository(session).get(successor_id).attempt == 0
        # 重复的旧终态回调不能终结 successor 的 pending，也不能再创建后继。
        create_high_throughput_analysis_job_terminal_callback(runtime)(session, old_job)
        assert (
            session.scalar(select(requests.c.job_id).where(requests.c.id == work[0].request_id))
            == successor_id
        )
        assert (
            session.scalar(
                select(func.count()).select_from(items).where(items.c.status == "pending")
            )
            == 2
        )
        with pytest.raises(LeaseLostError):
            PostgresJobRepository(session).lock_current_execution(fence)
    with _http(monkeypatch, lambda _payload: (200, _valid_response())) as calls:
        assert worker.run_once()
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "succeeded" and result["stats"]["succeeded"] == 3
    assert len(calls) == 2
    assert all(payload["items"][0]["title"] != work[2].content.title for payload in calls)


def test_two_shards_drain_late_429_after_shrink_and_all_contents_finish(runtime, monkeypatch):
    """真实 HTTP/PG 缩容后排队 Retry 不占许可；两片恢复且成功内容不重发。"""
    from aima_ugc.bootstrap.analysis_capacity import AnalysisCapacityFeedback

    client, run_id, _ = _planned(runtime, rows=20, shards=2)
    with runtime.database.engine.begin() as connection:
        connection.execute(update(profiles).values(state=asdict(CapacityState(current=10))))
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying._retry_delay_seconds", lambda _attempt: 0)
    arrived, release = Event(), Event()
    lock = Lock()
    attempts = 0
    feedbacks = []
    original = AnalysisCapacityFeedback.admit

    def admit(feedback, stop_event):
        """观察正式反馈实例，不替换其物理许可或调度逻辑。"""
        with lock:
            if feedback not in feedbacks:
                feedbacks.append(feedback)
        original(feedback, stop_event)

    def respond(_payload):
        """首批同时在途请求迟到拒绝，后续实际请求全部合法。"""
        nonlocal attempts
        with lock:
            attempts += 1
            count = attempts
            if count == 10:
                arrived.set()
        if count <= 10:
            assert release.wait(10)
            return 429, ""
        return 200, _valid_response()

    monkeypatch.setattr(AnalysisCapacityFeedback, "admit", admit)
    with _http(monkeypatch, respond) as calls, ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_worker(runtime).run_once) for _ in range(2)]
        try:
            assert arrived.wait(6), (
                f"两个分片未达到初始物理容量：attempts={attempts} "
                f"targets={[v.target for v in feedbacks]}"
            )
            with runtime.database.engine.begin() as connection:
                window = dict(connection.execute(select(profiles.c.window)).scalar_one())
                window["epoch"] += 1
                connection.execute(
                    update(profiles).values(state=asdict(CapacityState(current=2)), window=window)
                )
            until = monotonic() + 5
            while monotonic() < until and any(value.target > 1 for value in feedbacks):
                sleep(0.05)
            assert len(feedbacks) == 2 and all(value.target <= 1 for value in feedbacks)
            release.set()
            until = monotonic() + 15
            while monotonic() < until and not all(value.done() for value in futures):
                sleep(0.05)
            assert all(value.done() for value in futures), "缩容排空后等待任务仍阻塞共享许可"
            assert all(value.result() for value in futures)
        except BaseException as error:
            release.set()
            try:
                assert (
                    client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code == 200
                )
            except Exception as cleanup_error:
                error.add_note(f"本次测试 Run 清理失败：{cleanup_error!r}")
            raise
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "succeeded" and result["stats"]["succeeded"] == 20
    assert result["stats"]["failed"] == result["stats"]["pending"] == 0
    assert len(calls) == 30


@pytest.mark.parametrize("rps", [None, 10.0])
def test_v2_format_backoff_at_capacity_one_does_not_block_ready_shard(runtime, monkeypatch, rps):
    """格式长期退避不空占 C=1；其他正常分片在其恢复和 Deadline 之前成功。"""
    client, run_id, _ = _planned(runtime, rows=8, shards=2)
    with runtime.database.new_session() as session, session.begin():
        # active_shards 按 Job UUID 分配余数，正式 Worker 认领前先冻结该分片的退避事实。
        idle_request = session.scalar(select(requests.c.id).order_by(requests.c.job_id).limit(1))
        session.execute(update(profiles).values(state=asdict(CapacityState(current=1, rps=rps))))
        session.execute(
            update(items)
            .where(items.c.request_id == idle_request)
            .values(
                retry_kind="validation",
                retry_count=20,
                validation_error_codes=["invalid_json"],
                validation_failure_started_at=func.clock_timestamp() - timedelta(minutes=10),
                retry_not_before=func.clock_timestamp() + timedelta(hours=1),
            )
        )
    observed_rates, sent_at = [], []
    original_rate = PostgresAnalysisCapacityRepository.reserved_rps

    def observe_rate(repository, *args, **kwargs):
        """观测生产短事务速率，不替代任何准入或持久分配。"""
        result = original_rate(repository, *args, **kwargs)
        observed_rates.append(result)
        return result

    def respond(_payload):
        """记录真实 HTTP 到达间隔，合法输出继续经过正式 Validator 和入库。"""
        sent_at.append(monotonic())
        return 200, _valid_response()

    monkeypatch.setattr(PostgresAnalysisCapacityRepository, "reserved_rps", observe_rate)
    with (
        _http(monkeypatch, respond) as calls,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [pool.submit(_worker(runtime).run_once) for _ in range(2)]
        try:
            until = monotonic() + 8
            while monotonic() < until:
                result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
                if result["stats"]["succeeded"] == 4:
                    break
                sleep(0.05)
            assert result["status"] == "running" and result["stats"]["succeeded"] == 4
            assert result["stats"]["pending"] == 4 and result["stats"]["failed"] == 0
            assert len(calls) == 4
            if rps is not None:
                assert rps in observed_rates, "退避分片仍稀释正常分片的可用 RPS"
                assert all(b - a >= 0.09 for a, b in zip(sent_at, sent_at[1:], strict=False))
        finally:
            assert client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code == 200
        assert all(future.result(timeout=4) for future in futures)


@pytest.mark.parametrize("boundary", ["legacy", "cancel", "network", "auth"])
def test_deadline_continuation_respects_legacy_cancel_and_stopped_run(runtime, boundary):
    """接续不能改变旧协议，不能复活取消、真实断网或系统硬错误已停止的 Run。"""
    from aima_ugc.bootstrap.worker import create_collection_job_registry
    from aima_ugc.platform.jobs.worker import JobReaper

    client, run_id, _ = _planned(
        runtime, rows=2, recovery_mode="recovery.v1" if boundary == "legacy" else "recovery.v2"
    )
    fence, _ = _claim(runtime)
    if boundary == "cancel":
        assert client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code == 200
    elif boundary in {"network", "auth"}:
        with runtime.database.new_session() as session, session.begin():
            PostgresAnalysisRecoveryRepository(session).refresh(
                fence=fence,
                run_id=run_id,
                stop_error="llm_transport_unavailable" if boundary == "network" else "llm_http_401",
            )
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == fence.job_id)
            .values(
                attempt=3,
                attempt_deadline_at=func.clock_timestamp() - timedelta(seconds=1),
                attempt_started_at=func.clock_timestamp() - timedelta(seconds=1801),
                lease_expires_at=func.clock_timestamp() - timedelta(seconds=2),
            )
        )
    assert JobReaper(
        session_factory=runtime.database.new_session,
        registry=create_collection_job_registry(runtime=runtime),
        retry_delay_seconds=0,
    ).run_once()
    with runtime.database.new_session() as session, session.begin():
        assert session.scalar(select(requests.c.job_id)) == fence.job_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(jobs_table)
                .where(
                    jobs_table.c.internal_idempotency_key.like("content-analysis-continuation:%")
                )
            )
            == 0
        )
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == ("cancelled" if boundary == "cancel" else "failed")


@pytest.mark.parametrize("reaper_first", [False, True])
def test_v2_successor_and_cancel_api_race_preserves_results_and_cancels_current_job(
    runtime, monkeypatch, reaper_first
):
    """正式 Cancel 与后继绑定交错，集合复核必须取消新身份且不重发旧成功。"""
    from aima_ugc.bootstrap.worker import create_collection_job_registry
    from aima_ugc.platform.jobs.worker import JobReaper

    client, run_id, _ = _planned(runtime, rows=3)
    fence, work = _claim(runtime)
    with runtime.database.new_session() as session, session.begin():
        _persist_valid_work(session, fence, work[2])
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == fence.job_id)
            .values(
                attempt=3,
                attempt_deadline_at=func.clock_timestamp() - timedelta(seconds=1),
                attempt_started_at=func.clock_timestamp() - timedelta(seconds=1801),
                lease_expires_at=func.clock_timestamp() - timedelta(seconds=2),
            )
        )
    created, cancel_waiting = Event(), Event()
    original = PostgresJobRepository.enqueue

    def enqueue(repository, **kwargs):
        """后继尚未提交时让 Cancel 读取旧集合并真实等待其 Job 行锁。"""
        successor = original(repository, **kwargs)
        if kwargs["internal_idempotency_key"].startswith("content-analysis-continuation:"):
            created.set()
            assert cancel_waiting.wait(3)
        return successor

    def observe(_connection, _cursor, statement, parameters, _context, _many):
        """观察实际 Cancel SQL，不使用睡眠猜测是否发生锁竞争。"""
        if (
            "FOR UPDATE" in statement
            and str(fence.job_id) in str(parameters)
            and not current_thread().name.startswith("continuation-reaper")
        ):
            cancel_waiting.set()

    reaper = JobReaper(
        session_factory=runtime.database.new_session,
        registry=create_collection_job_registry(runtime=runtime),
        retry_delay_seconds=0,
    )
    event.listen(runtime.database.engine, "before_cursor_execute", observe)
    try:
        if reaper_first:
            monkeypatch.setattr(PostgresJobRepository, "enqueue", enqueue)
            with ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="continuation-reaper"
            ) as pool:
                future = pool.submit(reaper.run_once)
                assert created.wait(3)
                assert (
                    client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code == 200
                )
                assert future.result(timeout=5)
            assert cancel_waiting.is_set()
        else:
            assert client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code == 200
            assert reaper.run_once()
    finally:
        event.remove(runtime.database.engine, "before_cursor_execute", observe)
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["status"] == "cancelled"
    assert result["stats"] == dict(pending=0, succeeded=1, failed=0, stale=0, cancelled=2)
    with runtime.database.new_session() as session, session.begin():
        current_id = session.scalar(select(requests.c.job_id))
        assert PostgresJobRepository(session).get(current_id).status == "cancelled"
        assert (current_id != fence.job_id) == reaper_first
