"""隔离 PG/HTTP 验证分片尾部衔接与真实可发送需求。"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis import PostgresAnalysisRepository
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.modules.analysis.tables import (
    analysis_content_request_items_table as items,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_requests_table as requests,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_runs_table as runs,
)
from aima_ugc.modules.system.tables import provider_configs_table
from aima_ugc.platform.capacity import ResourceSnapshot
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import select, update

from tests.integration.content.test_analysis_adaptive_capacity import _worker
from tests.integration.content.test_analysis_provider_concurrency import (
    _client,
    _controlled_http,
    _create_run,
    _runtime,
    _seed_contents,
    _seed_provider,
)
from tests.integration.jobs.test_worker_process_lifecycle import _stop_owned_test_process


@pytest.fixture
def runtime(tmp_path):
    """复用正式测试 Runtime 的隔离与清理边界。"""
    value = _runtime(tmp_path)
    try:
        yield value
    finally:
        value.close()


def test_ready_demand_excludes_inflight_buffered_and_future_retry(runtime):
    """pending 不等于可发送：排除已发项、未来退避项，同时保留提前恢复语义。"""
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=8)
    run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
    assert _worker(runtime).run_once()
    with runtime.database.new_session() as session, session.begin():
        request_id = session.scalar(select(requests.c.id).where(requests.c.run_id == run_id))
        repo = PostgresAnalysisRepository(session)
        assert repo.has_ready(request_id, excluded_content_ids=())
        assert not repo.has_ready(request_id, excluded_content_ids=ids)
        now = beijing_now()
        session.execute(
            update(items)
            .where(items.c.content_id == ids[0])
            .values(
                retry_kind="transport",
                retry_not_before=now + timedelta(minutes=1),
                last_retry_at=now,
            )
        )
        assert not repo.has_ready(request_id, excluded_content_ids=ids[1:])
        session.execute(
            update(runs)
            .where(runs.c.id == run_id)
            .values(last_transport_success_at=now + timedelta(seconds=1))
        )
        assert repo.has_ready(request_id, excluded_content_ids=ids[1:])


def test_next_shards_finish_while_previous_shard_waits_for_one_slow_request(runtime, monkeypatch):
    """真实 Planner/Worker/HTTP/Validator/PG 接通，慢尾请求不阻止下一片工作。"""
    monkeypatch.setattr(
        PlatformRuntime,
        "worker_resources",
        lambda _: ResourceSnapshot(12, 32 * 1024**3, 12 * 1024**3, "test_host"),
    )
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=36)
    run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(runs).where(runs.c.id == run_id).values(shard_size=12, shard_count=3)
        )
    first, second = _worker(runtime), _worker(runtime)
    assert first.run_once()
    assert len(client.get(f"/api/v1/analysis/content-runs/{run_id}").json()["shards"]) == 2

    def drain_second():
        """同一正式 Worker 在第一片未完成时继续领取后续分片。"""
        count = 0
        while second.run_once():
            count += 1
            assert count <= 2
        return count

    with _controlled_http(expected=35) as (arrived, release, bodies, adapters):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_done = pool.submit(first.run_once)
            try:
                try:
                    deadline = monotonic() + 3
                    while not bodies and monotonic() < deadline:
                        Event().wait(0.01)
                    assert bodies, "第一片没有开始发送请求"
                    second_done = pool.submit(drain_second)
                    assert arrived.wait(8), "下一分片仍被前一片的慢尾请求阻塞"
                    deadline = monotonic() + 3
                    while monotonic() < deadline:
                        state = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
                        if state["stats"]["succeeded"] >= 24:
                            break
                        Event().wait(0.02)
                    assert state["stats"]["succeeded"] >= 24
                    assert state["stats"]["pending"] >= 1
                    assert not first_done.done()
                finally:
                    release.set()
                assert first_done.result(timeout=8)
                assert second_done.result(timeout=8) == 2
            except BaseException as error:
                # 所有行为断言都先释放 HTTP、取消本 Run，再进入执行器等待。
                try:
                    assert (
                        client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code
                        == 200
                    )
                except Exception as cleanup_error:
                    error.add_note(f"本次测试 Run 取消失败：{cleanup_error!r}")
                raise
        assert len(bodies) == len(ids)
        assert sum(adapter.request_metrics()["http_requests"] for adapter in adapters) == len(ids)
        assert all(set(body) == {"model", "messages", "response_format"} for body in bodies)
    state = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert state["status"] == "succeeded"
    assert state["stats"]["succeeded"] == 36 and state["stats"]["failed"] == 0


@pytest.mark.parametrize("failure_stage", ["first_send", "cross_shard"])
def test_failed_tail_assertion_releases_http_and_cancels_before_executor_wait(
    runtime, monkeypatch, failure_stage
):
    """真实 Worker 仍在运行时注入行为失败，证明清理先于线程池退出且保留原断言。"""
    real_http = _controlled_http
    released = []
    real_executor = ThreadPoolExecutor

    @contextmanager
    def fail_observation(**kwargs):
        """只改变测试观测，不替换生产调度、HTTP、取消或持久化实现。"""
        with real_http(**kwargs) as (arrived, release, bodies, adapters):
            released.append(release)
            if failure_stage == "first_send":
                yield arrived, release, [], adapters
            else:

                class RejectedArrival:
                    """让跨片行为断言失败，实际请求仍由真实 Fake HTTP 阻塞。"""

                    def wait(self, timeout):
                        """等待一条实际请求，确保错误发生时确有在途工作。"""
                        assert bodies
                        return False

                yield RejectedArrival(), release, bodies, adapters

    class CheckedExecutor(real_executor):
        """退出前读取正式取消状态，防止用执行器等待掩盖清理顺序。"""

        def __exit__(self, exc_type, exc_value, traceback):
            """先证明释放和取消已提交，再让真实线程执行器回收 Worker。"""
            if exc_type is not None:
                assert released[0].is_set()
                with runtime.database.engine.begin() as connection:
                    assert connection.scalar(select(runs.c.cancel_requested_at)) is not None
            return super().__exit__(exc_type, exc_value, traceback)

    module = sys.modules[__name__]
    monkeypatch.setattr(module, "_controlled_http", fail_observation)
    monkeypatch.setattr(module, "ThreadPoolExecutor", CheckedExecutor)
    message = "第一片没有开始发送请求" if failure_stage == "first_send" else "下一分片"
    started = monotonic()
    with pytest.raises(AssertionError, match=message):
        test_next_shards_finish_while_previous_shard_waits_for_one_slow_request(
            runtime, monkeypatch
        )
    assert monotonic() - started < 10
    with runtime.database.engine.begin() as connection:
        assert not connection.scalar(
            select(jobs_table.c.id).where(jobs_table.c.status == "running")
        )


def test_real_worker_entrypoint_starts_multiple_processes_and_finishes_run(runtime):
    """正式模块入口实际创建子进程，稳定 Lease 身份穿过 venv 启动器。"""
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=36)

    def set_endpoint(url):
        """创建 Run 前冻结测试端点，子进程也使用同一真实本地 HTTP 服务。"""
        with runtime.database.engine.begin() as connection:
            connection.execute(update(provider_configs_table).values(base_url=url))

    with _controlled_http(expected=10, block_all=True, endpoint_ready=set_endpoint) as (
        arrived,
        release,
        bodies,
        _adapters,
    ):
        run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(runs).where(runs.c.id == run_id).values(shard_size=12, shard_count=3)
            )
        environment = dict(os.environ)
        environment.update(
            AIMA_DATA_DIR=str(runtime.settings.data_dir),
            AIMA_LOG_DIR=str(runtime.settings.log_dir),
            AIMA_EXTERNAL_SECRET_DIR=str(runtime.settings.external_secret_root),
        )
        environment.pop("_AIMA_WORKER_LEASE_OWNER", None)
        process = subprocess.Popen(
            [sys.executable, "-B", "-m", "aima_ugc.entrypoints.worker_main"],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
        )
        owned_group = os.getpgid(process.pid) if os.name != "nt" else None
        original_error = None
        try:
            assert arrived.wait(10), "实际 Worker 入口没有发送请求"
            deadline = monotonic() + 8
            owners = set()
            while monotonic() < deadline:
                with runtime.database.engine.begin() as connection:
                    owners = set(
                        connection.execute(
                            select(jobs_table.c.lease_owner).where(
                                jobs_table.c.job_type == "analysis.content-label.v1",
                                jobs_table.c.status == "running",
                            )
                        ).scalars()
                    )
                if len(owners) >= 2:
                    break
                Event().wait(0.05)
            assert len(owners) >= 2
            assert all(len(owner.rsplit(":", 1)[-1]) == 32 for owner in owners)
            release.set()
            deadline = monotonic() + 15
            while monotonic() < deadline:
                state = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
                if state["status"] == "succeeded":
                    break
                assert process.poll() is None
                Event().wait(0.05)
            assert state["status"] == "succeeded"
            assert state["stats"]["succeeded"] == len(ids)
            assert len(bodies) == len(ids)
        except BaseException as error:
            original_error = error
            raise
        finally:
            release.set()
            if original_error is not None:
                try:
                    assert (
                        client.post(f"/api/v1/analysis/content-runs/{run_id}/cancel").status_code
                        == 200
                    )
                except Exception as cleanup_error:
                    original_error.add_note(f"本次测试 Run 取消失败：{cleanup_error!r}")
            try:
                _stop_owned_test_process(process, owned_group=owned_group)
            except Exception as cleanup_error:
                if original_error is None:
                    raise
                original_error.add_note(f"本次测试进程回收失败：{cleanup_error!r}")
