"""隔离 PostgreSQL 中的新容量协议、跨 Run 分配与正式 Worker 黄金链。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_capacity import (
    PostgresAnalysisCapacityRepository,
    empty_window,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.bootstrap.analysis_capacity import AnalysisCapacityFeedback
from aima_ugc.bootstrap.worker import create_collection_job_registry, create_job_worker
from aima_ugc.contracts.administration import (
    ProviderConfigCreateRequest,
    ProviderConfigUpdateRequest,
)
from aima_ugc.modules.administration import AdministrationConflict
from aima_ugc.modules.analysis.adaptive_capacity import CapacityState
from aima_ugc.modules.analysis.content_analysis_job import CONTENT_ANALYSIS_JOB_TYPE
from aima_ugc.modules.analysis.tables import (
    analysis_content_runs_table as runs,
)
from aima_ugc.modules.analysis.tables import (
    analysis_llm_capacity_profiles_table as profiles,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.platform.capacity import ResourceSnapshot
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from sqlalchemy import func, select, update

from tests.integration.content.test_analysis_provider_concurrency import (
    _client,
    _ConcurrentFakeLLM,
    _controlled_http,
    _create_run,
    _drain,
    _runtime,
    _seed_contents,
    _seed_provider,
)


@pytest.fixture
def runtime(tmp_path):
    value = _runtime(tmp_path)
    try:
        yield value
    finally:
        value.close()


def test_cold_adaptive_run_ignores_old_manual_provider_fields_and_persists_success(runtime) -> None:
    _seed_provider(runtime, max_concurrency=4)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=30)
    run_id = _create_run(client, ids, runtime, key=str(uuid4()), legacy=False)
    llm = _ConcurrentFakeLLM(max_concurrency=10)
    assert _drain(runtime, llm, worker_id="adaptive-cold") == 2
    assert llm.peak_active == 10
    assert len(llm.item_sizes) == 30
    result = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert result["stats"]["succeeded"] == 30
    assert result["shard_size"] == 600
    with runtime.database.engine.begin() as connection:
        snapshot = connection.execute(
            select(runs.c.runtime_config_snapshot).where(runs.c.id == UUID(run_id))
        ).scalar_one()
        assert snapshot["capacity_mode"] == "adaptive.v1"
        assert snapshot["max_concurrency"] == 256
        assert snapshot["max_retries"] == 3
        assert connection.execute(select(profiles.c.window)).scalar_one()["persisted"] == 30


def test_two_sessions_advance_one_window_and_old_revision_cannot_overwrite(
    runtime, monkeypatch
) -> None:
    provider_id = uuid4()
    session = runtime.database.new_session()
    with session.begin():
        repository = PostgresAnalysisCapacityRepository(session)
        repository.ensure(provider_id, "model", revision=1, prompt_sha256="a" * 64)
        start = repository.get(provider_id, "model")["window_started_at"]
    session.close()
    monkeypatch.setattr(
        PostgresAnalysisCapacityRepository, "_now", lambda _self: start + timedelta(seconds=10)
    )
    delta = {
        **empty_window(),
        "persisted": 100,
        "requests": 100,
        "started": 100,
        "busy_seconds": 100.0,
        "demand": True,
    }
    delta["latency"][4] = 100
    for _ in range(2):
        session = runtime.database.new_session()
        with session.begin():
            row = PostgresAnalysisCapacityRepository(session).observe(
                provider_id, "model", revision=1, prompt_sha256="a" * 64, delta=delta
            )
            assert row["state"]["current"] == 20
        session.close()
    session = runtime.database.new_session()
    with session.begin():
        repository = PostgresAnalysisCapacityRepository(session)
        assert repository.get(provider_id, "model")["state"]["current"] == 20
        warmed = repository.ensure(provider_id, "model", revision=2, prompt_sha256="a" * 64)
        stale = repository.observe(
            provider_id, "model", revision=1, prompt_sha256="a" * 64, delta=delta
        )
        assert stale["revision"] == 2
        assert stale["state"]["current"] == warmed.current
        assert stale["window"]["persisted"] == 0
    session.close()


def test_preview_create_and_idempotent_retry_survive_learning_updates(runtime) -> None:
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime)
    targets = {"scope": "selected", "content_ids": [str(value) for value in ids]}
    preview = client.post("/api/v1/analysis/content-runs/preview", json={"targets": targets}).json()
    # 首次 preview 没有学习写入；创建之前加入历史反馈也不应使确认失效。
    session = runtime.database.new_session()
    from aima_ugc.bootstrap.runtime_config import active_llm_provider

    with session.begin():
        provider = active_llm_provider(session, runtime.settings)
        repository = PostgresAnalysisCapacityRepository(session)
        repository.ensure(
            provider.id,
            provider.model,
            revision=provider.revision,
            prompt_sha256=preview["prompt_sha256"],
        )
        session.execute(
            update(profiles).values(
                state=asdict(
                    CapacityState(current=100, last_safe=100, throughput_ewma=20, latency_p95=12)
                )
            )
        )
    session.close()
    body = {
        "client_idempotency_key": str(uuid4()),
        "targets": targets,
        "expected_target_count": len(ids),
        "expected_configuration_hash": preview["configuration_hash"],
        "run_intent": "manual_reanalysis",
    }
    created = client.post("/api/v1/analysis/content-runs", json=body)
    assert created.status_code == 202
    with runtime.database.engine.begin() as connection:
        run = (
            connection.execute(select(runs).where(runs.c.id == UUID(created.json()["run_id"])))
            .mappings()
            .one()
        )
        assert run["shard_size"] == 6000
        assert run["runtime_config_snapshot"]["timeout_seconds"] == 41
        connection.execute(
            update(profiles).values(
                state=asdict(CapacityState(current=500, throughput_ewma=100, latency_p95=30))
            )
        )
    assert client.post("/api/v1/analysis/content-runs", json=body).json() == created.json()
    with runtime.database.engine.begin() as connection:
        assert connection.execute(select(runs.c.shard_size)).scalar_one() == 6000


def _worker(runtime):
    return create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(runtime=runtime),
        worker_id="adaptive-planner",
        lease_seconds=120,
        retry_delay_seconds=0,
    )


def test_cross_run_shares_ignore_queued_and_expired_lease_and_allow_zero(runtime) -> None:
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime)
    run_ids = [_create_run(client, ids, runtime, key=str(uuid4()), legacy=False) for _ in range(2)]
    with runtime.database.engine.begin() as connection:
        connection.execute(update(profiles).values(state=asdict(CapacityState(current=512))))
    worker = _worker(runtime)
    assert worker.run_once() and worker.run_once()
    fences = []
    for index in range(2):
        session = runtime.database.new_session()
        with session.begin():
            job = PostgresJobRepository(session).claim_next(
                supported_job_types=(CONTENT_ANALYSIS_JOB_TYPE,),
                worker_id=f"adaptive-share-{index}",
                lease_seconds=120,
            )
            assert job is not None and job.lease_token is not None
            fences.append(JobExecutionFence(job_id=job.id, lease_token=job.lease_token))
        session.close()
    session = runtime.database.new_session()
    from aima_ugc.bootstrap.runtime_config import active_llm_provider

    with session.begin():
        provider = active_llm_provider(session, runtime.settings)
        row = PostgresAnalysisCapacityRepository(session).get(provider.id, provider.model)
        session.execute(update(profiles).values(state=asdict(CapacityState(current=1, rps=2))))
        assert (
            len(
                PostgresAnalysisCapacityRepository(session).active_shards(
                    provider.id, provider.model
                )
            )
            == 2
        )
    session.close()
    feedback = [
        AnalysisCapacityFeedback(
            runtime, provider=provider, prompt_sha256=row["prompt_sha256"], run_id=UUID(run_id)
        )
        for run_id in run_ids
    ]
    for value, fence in zip(feedback, fences, strict=True):
        value.refresh(fence, demand=True, force=True)
    assert sorted(value.target for value in feedback) == [0, 1]
    assert sorted(value.rps for value in feedback) == [0.0, 1.0]
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table)
            .where(jobs_table.c.id == fences[0].job_id)
            .values(lease_expires_at=row["updated_at"] - timedelta(seconds=1))
        )
    session = runtime.database.new_session()
    assert (
        len(PostgresAnalysisCapacityRepository(session).active_shards(provider.id, provider.model))
        == 1
    )
    session.close()
    with pytest.raises(LeaseLostError):
        feedback[0].refresh(fences[0], demand=True, force=True)


def test_terminal_callback_releases_capacity_to_waiting_run(runtime) -> None:
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime)
    first, second = [
        _create_run(client, ids, runtime, key=str(uuid4()), legacy=False) for _ in range(2)
    ]
    worker = _worker(runtime)
    assert worker.run_once() and worker.run_once()
    assert client.get(f"/api/v1/analysis/content-runs/{second}").json()["shards"] == []
    llm = _ConcurrentFakeLLM(max_concurrency=8)
    assert _drain(runtime, llm, worker_id="adaptive-waiting") == 2
    assert client.get(f"/api/v1/analysis/content-runs/{first}").json()["status"] == "succeeded"
    assert client.get(f"/api/v1/analysis/content-runs/{second}").json()["status"] == "succeeded"


def test_llm_update_rejects_manual_fields_from_stored_kind_and_collection_keeps_them(
    runtime,
) -> None:
    admin = Principal(
        principal_id="capacity-admin",
        display_name="管理员",
        role="administrator",
        source="development",
    )
    service = PostgresAdministrationHttpService(runtime)
    llm = service.create_provider_config(
        ProviderConfigCreateRequest(
            provider_kind="llm",
            provider="fake",
            display_name="模型",
            base_url="https://example.invalid/v1",
            model="model",
            api_key="fake",
        ),
        principal=admin,
        request_id="create",
    )
    assert llm.max_concurrency is None
    assert llm.adaptive_capacity.current_concurrency == 10
    with pytest.raises(AdministrationConflict, match="自动"):
        service.update_provider_config(
            llm.id,
            ProviderConfigUpdateRequest(
                display_name="模型", base_url=llm.base_url, model="model", max_concurrency=20
            ),
            principal=admin,
            request_id="reject",
        )
    service.update_provider_config(
        llm.id,
        ProviderConfigUpdateRequest(display_name="模型2", base_url=llm.base_url, model="model"),
        principal=admin,
        request_id="save",
    )
    collection = service.create_provider_config(
        ProviderConfigCreateRequest(
            provider_kind="collection",
            provider="fake-collection",
            display_name="采集",
            base_url="https://example.invalid",
            api_key="fake",
            max_concurrency=7,
            max_rps=2,
        ),
        principal=admin,
        request_id="collection",
    )
    assert collection.max_concurrency == 7 and collection.max_rps == 2


def test_running_shard_expands_job_window_without_changing_frozen_ranges(runtime) -> None:
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=30)
    run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
    # 用小的冻结范围验证运行中扩窗，不为了测试制造几千条业务数据。
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(runs).where(runs.c.id == run_id).values(shard_size=10, shard_count=3)
        )
    worker = _worker(runtime)
    assert worker.run_once()
    session = runtime.database.new_session()
    from aima_ugc.bootstrap.runtime_config import active_llm_provider

    with session.begin():
        provider = active_llm_provider(session, runtime.settings)
        row = PostgresAnalysisCapacityRepository(session).get(provider.id, provider.model)
        job = PostgresJobRepository(session).claim_next(
            supported_job_types=(CONTENT_ANALYSIS_JOB_TYPE,),
            worker_id="growing-shard",
            lease_seconds=120,
        )
        fence = JobExecutionFence(job_id=job.id, lease_token=job.lease_token)
        session.execute(update(profiles).values(state=asdict(CapacityState(current=600))))
    session.close()
    feedback = AnalysisCapacityFeedback(
        runtime, provider=provider, prompt_sha256=row["prompt_sha256"], run_id=run_id
    )
    feedback.refresh(fence, demand=True, force=True)
    feedback.refresh(fence, demand=True, force=True)
    from aima_ugc.modules.analysis.tables import analysis_content_requests_table

    with runtime.database.engine.begin() as connection:
        requests = (
            connection.execute(
                select(analysis_content_requests_table).where(
                    analysis_content_requests_table.c.run_id == run_id
                )
            )
            .mappings()
            .all()
        )
        assert len(requests) == 2
        assert sorted(value["shard_no"] for value in requests) == [0, 1]
        assert (
            connection.execute(
                select(jobs_table.c.status).where(jobs_table.c.id == job.id)
            ).scalar_one()
            == "running"
        )
        assert (
            connection.execute(select(runs.c.shard_size).where(runs.c.id == run_id)).scalar_one()
            == 10
        )


def test_adaptive_real_http_feedback_counts_attempts_but_not_stale_success(runtime) -> None:
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=2)
    run_id = _create_run(client, ids, runtime, key=str(uuid4()), legacy=False)
    worker = _worker(runtime)
    assert worker.run_once()
    with _controlled_http(expected=2, block_all=True) as (arrived, release, _bodies, adapters):
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(worker.run_once)
            try:
                assert arrived.wait(4)
                with runtime.database.engine.begin() as connection:
                    connection.execute(
                        update(contents_table)
                        .where(contents_table.c.id == ids[0])
                        .values(current_version=contents_table.c.current_version + 1)
                    )
            finally:
                release.set()
            assert result.result(timeout=5)
        assert adapters[0].request_metrics()["http_requests"] == 2
    state = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert state["stats"]["succeeded"] == 1 and state["stats"]["stale"] == 1
    with runtime.database.engine.begin() as connection:
        observation = connection.execute(select(profiles.c.window)).scalar_one()
        assert observation["requests"] == 2 and observation["started"] == 2
        assert observation["persisted"] == 1


def test_zero_database_headroom_keeps_durable_initial_and_terminal_progress(
    runtime, monkeypatch
) -> None:
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=20)
    run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(runs).where(runs.c.id == run_id).values(shard_size=10, shard_count=2)
        )
    monkeypatch.setattr(PostgresJobRepository, "database_headroom", lambda _: 0)
    worker = _worker(runtime)
    assert worker.run_once()
    state = client.get(f"/api/v1/analysis/content-runs/{run_id}").json()
    assert len(state["shards"]) == 1
    # 即使 terminal 也遇到零余量，保留一个可领取分片；原 Run 无须人工重新启动。
    assert _drain(runtime, _ConcurrentFakeLLM(max_concurrency=10), worker_id="zero-headroom") == 2
    assert client.get(f"/api/v1/analysis/content-runs/{run_id}").json()["stats"]["succeeded"] == 20


def test_legacy_run_retains_snapshot_and_releases_waiting_adaptive_run(runtime) -> None:
    _seed_provider(runtime, max_concurrency=4)
    client = _client(runtime)
    ids = _seed_contents(client, runtime)
    legacy = _create_run(client, ids, runtime, key=str(uuid4()), legacy=True)
    adaptive = _create_run(client, ids, runtime, key=str(uuid4()), legacy=False)
    worker = _worker(runtime)
    assert worker.run_once() and worker.run_once()
    assert client.get(f"/api/v1/analysis/content-runs/{adaptive}").json()["shards"] == []
    with runtime.database.engine.begin() as connection:
        old = connection.execute(
            select(runs.c.runtime_config_snapshot).where(runs.c.id == UUID(legacy))
        ).scalar_one()
        assert old["max_concurrency"] == 4 and "capacity_mode" not in old
    assert _drain(runtime, _ConcurrentFakeLLM(max_concurrency=4), worker_id="legacy-drain") == 2
    assert client.get(f"/api/v1/analysis/content-runs/{adaptive}").json()["status"] == "succeeded"


def test_machine_cpu_memory_and_pressure_bound_dynamic_analysis_window(runtime, monkeypatch):
    """服务商容量充足时，低 CPU/小内存仍限制投放；内存压力阻止扩窗并可恢复。"""

    from aima_ugc.bootstrap.analysis_high_throughput_planner import (
        schedule_high_throughput_analysis_run_shards,
    )
    from aima_ugc.bootstrap.runtime import PlatformRuntime
    from aima_ugc.modules.analysis.tables import analysis_content_requests_table

    mib = 1024 * 1024
    resources = ResourceSnapshot(1, 1024 * mib, 900 * mib, "test_low_cpu")
    monkeypatch.setattr(PlatformRuntime, "worker_resources", lambda _: resources)
    runtime.settings = runtime.settings.model_copy(update={"analysis_run_max_in_flight_jobs": 8})
    _seed_provider(runtime)
    client = _client(runtime)
    ids = _seed_contents(client, runtime, row_count=60)
    run_id = UUID(_create_run(client, ids, runtime, key=str(uuid4()), legacy=False))
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(runs).where(runs.c.id == run_id).values(shard_size=10, shard_count=6)
        )
        connection.execute(update(profiles).values(state=asdict(CapacityState(current=2048))))
    assert _worker(runtime).run_once()
    with runtime.database.engine.begin() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(analysis_content_requests_table))
            == 1
        )
    for candidate, expected in (
        (ResourceSnapshot(12, 2 * 1024 * mib, 1800 * mib, "test_small_memory"), 2),
        (ResourceSnapshot(12, 8 * 1024 * mib, 300 * mib, "test_memory_pressure"), 2),
        (ResourceSnapshot(12, 8 * 1024 * mib, 7 * 1024 * mib, "test_recovered"), 6),
    ):
        resources = candidate
        with runtime.database.new_session() as session, session.begin():
            schedule_high_throughput_analysis_run_shards(
                session,
                run_id=run_id,
                max_in_flight=runtime.job_window("analysis", ceiling=8),
                request_id=None,
            )
            assert (
                session.scalar(select(func.count()).select_from(analysis_content_requests_table))
                == expected
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(jobs_table)
                    .where(
                        jobs_table.c.job_type == CONTENT_ANALYSIS_JOB_TYPE,
                        jobs_table.c.cancel_requested_at.is_not(None),
                    )
                )
                == 0
            )
