"""数据库 Provider 驱动的正式 Analysis 并发与批量持久化集成回归。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import Event, Lock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select

from aima_ugc.adapters.llm.openai_compatible import OpenAICompatibleLLMError
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.bootstrap.analysis_concurrent_worker import (
    ConcurrentPostgresContentAnalysisJobExecutor,
)
from aima_ugc.bootstrap.analysis_worker import (
    PostgresContentAnalysisPlanJobExecutor,
    create_analysis_job_terminal_callback,
)
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.modules.analysis import (
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
)
from aima_ugc.modules.analysis.content_analysis_job import (
    ContentAnalysisJobHandler,
    ContentAnalysisPlanJobHandler,
    register_content_analysis_job,
)
from aima_ugc.modules.analysis.schemes import prompt_taxonomy_from_version
from aima_ugc.modules.analysis.tables import (
    analysis_content_results_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs import JobRegistry


class _ConcurrentFakeLLM:
    """Canary 立即成功，后续请求阻塞到指定并发峰值后统一释放。"""

    provider_name = "fake-db"
    model_name = "fake-content-labeler-v1"

    def __init__(self, *, max_concurrency: int, fail_parallel_call: int | None = None) -> None:
        """创建线程安全 Fake；可让 Canary 后第 N 个并行调用返回非重试 Transport 错误。"""

        self._max_concurrency = max_concurrency
        self._fail_parallel_call = fail_parallel_call
        self._release = Event()
        self._lock = Lock()
        self._calls = 0
        self._parallel_calls = 0
        self._active = 0
        self.peak_active = 0
        self.item_sizes: list[int] = []

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """记录请求粒度和实际并发；只有第一条 Canary 不参加阻塞。"""

        with self._lock:
            self._calls += 1
            call_no = self._calls
            self.item_sizes.append(len(request.items))
            if call_no > 1:
                self._parallel_calls += 1
                parallel_call_no = self._parallel_calls
                self._active += 1
                self.peak_active = max(self.peak_active, self._active)
                if self.peak_active >= self._max_concurrency:
                    self._release.set()
            else:
                parallel_call_no = 0

        if call_no > 1:
            assert self._release.wait(timeout=5)
        try:
            if parallel_call_no == self._fail_parallel_call:
                raise OpenAICompatibleLLMError(
                    "fake bad request",
                    error_code="http_400",
                    retryable=False,
                    status_code=400,
                )
            return ContentLabelingLLMResponse(raw_text=_valid_response())
        finally:
            if call_no > 1:
                with self._lock:
                    self._active -= 1


def _valid_response() -> str:
    """返回当前测试 Scheme 已有的稳定 V3 合法结果。"""

    return (
        '{"items":[{"item_no":1,"relevance":"relevant",'
        '"voice_type":"真实用户发声","sentiment":"负面",'
        '"labels":[{"primary_label":"骑行性能","secondary_label":"舒适性"}]}]}'
    )


def _xlsx(row_count: int = 8) -> bytes:
    """生成足以观察并发的固定 Excel Content Fixture。"""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    for index in range(row_count):
        sheet.append(
            [
                "小红书",
                f"Provider Concurrency {index}",
                f"爱玛第 {index} 条并发测试内容",
                f"用户 {index}",
                f"2026-09-04 01:{index:02d}:00",
                f"https://www.xiaohongshu.com/explore/provider-concurrency-{index}",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _runtime(tmp_path: Path):  # type: ignore[no-untyped-def]
    """创建不依赖真实 LLM Secret 的隔离 PostgreSQL Runtime。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
            "analysis_run_max_in_flight_jobs": 2,
        }
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts, audit_events "
            "RESTART IDENTITY CASCADE"
        )
    return runtime


def _seed_provider(runtime, *, max_concurrency: int = 4) -> None:  # type: ignore[no-untyped-def]
    """直接通过 System Owner Repository 写入正式默认 LLM Provider 配置。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="fake-db",
                    provider_kind="llm",
                    display_name="并发集成 Fake",
                    base_url="https://fake.example/v1",
                    model="fake-content-labeler-v1",
                    secret_ref="providers/tests/fake.key",
                    timeout_seconds=45,
                    max_retries=0,
                    max_concurrency=max_concurrency,
                    max_rps=None,
                    is_default=True,
                    enabled=True,
                )
            )
    finally:
        session.close()


def _client(runtime) -> TestClient:  # type: ignore[no-untyped-def]
    """使用正式 Import/Content Service 构造测试 HTTP Client。"""

    return TestClient(
        create_app(
            import_service=PostgresImportHttpService(runtime),
            content_service=PostgresContentHttpService(
                runtime,
                cursor_signing_secret=b"provider-concurrency-content-cursor-key",
            ),
        )
    )


def _seed_contents(client: TestClient, runtime) -> tuple[UUID, ...]:  # type: ignore[no-untyped-def]
    """通过正式 Excel Import + Worker 链写入八条 Content。"""

    pack = client.post("/api/v1/keyword-packs", json={"name": f"Concurrency {uuid4()}"})
    assert pack.status_code == 201
    keyword = client.post(
        f"/api/v1/keyword-packs/{pack.json()['id']}/keywords",
        json={"text": "爱玛", "priority": 10},
    )
    assert keyword.status_code == 201
    uploaded = client.post(
        "/api/v1/import-batches",
        files=[
            (
                "file",
                (
                    "analysis-provider-concurrency.xlsx",
                    _xlsx(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("keyword_pack_ids", (None, pack.json()["id"])),
        ],
    )
    assert uploaded.status_code == 202
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(runtime=runtime),
        worker_id="analysis-provider-concurrency-import",
        lease_seconds=120,
        retry_delay_seconds=0,
    )
    assert worker.run_once() is True
    with runtime.database.engine.begin() as connection:
        return tuple(
            connection.execute(select(contents_table.c.id).order_by(contents_table.c.id))
            .scalars()
            .all()
        )


def _analysis_registry(runtime, llm: _ConcurrentFakeLLM) -> JobRegistry:  # type: ignore[no-untyped-def]
    """注册真实 Planner + 新并发 Executor，仅把外部 LLM Port 替换为线程安全 Fake。"""

    session = runtime.database.new_session()
    try:
        with session.begin():
            version = PostgresAnalysisSchemeRepository(session).get_active_version()
            assert version is not None
            taxonomy = prompt_taxonomy_from_version(version)
    finally:
        session.close()
    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=llm,
    )
    registry = JobRegistry()
    callback = create_analysis_job_terminal_callback(runtime)
    register_content_analysis_job(
        registry,
        ContentAnalysisJobHandler(
            ConcurrentPostgresContentAnalysisJobExecutor(
                runtime,
                service_factory=lambda: (service, lambda: None, 0, 4),
            )
        ),
        terminal_callback=callback,
        planner_handler=ContentAnalysisPlanJobHandler(
            PostgresContentAnalysisPlanJobExecutor(runtime)
        ),
        planner_terminal_callback=callback,
    )
    return registry


def _create_run(client: TestClient, content_ids: tuple[UUID, ...], *, key: str) -> str:
    """从公开 Preview/Create 入口创建 selected Analysis Run 并返回 Run ID。"""

    targets = {"scope": "selected", "content_ids": [str(item) for item in content_ids]}
    preview = client.post("/api/v1/analysis/content-runs/preview", json={"targets": targets})
    assert preview.status_code == 200
    assert preview.json()["shard_size"] == 80
    assert preview.json()["shard_count"] == 1
    created = client.post(
        "/api/v1/analysis/content-runs",
        json={
            "client_idempotency_key": key,
            "targets": targets,
            "expected_target_count": len(content_ids),
            "expected_configuration_hash": preview.json()["configuration_hash"],
            "run_intent": "manual_reanalysis",
        },
    )
    assert created.status_code == 202
    return str(created.json()["run_id"])


def _drain(runtime, llm: _ConcurrentFakeLLM, *, worker_id: str) -> int:  # type: ignore[no-untyped-def]
    """执行 Planner + 单 Shard，限制 Job 数防止调度失控。"""

    worker = create_job_worker(
        runtime=runtime,
        registry=_analysis_registry(runtime, llm),
        worker_id=worker_id,
        lease_seconds=120,
        retry_delay_seconds=0,
    )
    count = 0
    while worker.run_once():
        count += 1
        if count > 4:
            raise AssertionError("Provider 并发测试出现异常 Job 扩张")
    return count


def test_db_provider_drives_concurrency_shard_and_batch_persistence(tmp_path: Path) -> None:
    """正式 DB Provider 自动 Shard，Canary 后达到配置并发且八条结果完整落库。"""

    runtime = _runtime(tmp_path)
    try:
        _seed_provider(runtime, max_concurrency=4)
        client = _client(runtime)
        content_ids = _seed_contents(client, runtime)
        assert len(content_ids) == 8
        run_id = _create_run(client, content_ids, key="provider-concurrency-success")

        llm = _ConcurrentFakeLLM(max_concurrency=4)
        assert _drain(runtime, llm, worker_id="provider-concurrency-success") == 2
        assert llm.peak_active == 4
        assert llm.item_sizes == [1] * 8

        run = client.get(f"/api/v1/analysis/content-runs/{run_id}")
        assert run.status_code == 200
        assert run.json()["status"] == "succeeded"
        assert run.json()["shard_size"] == 80
        assert run.json()["stats"] == {
            "pending": 0,
            "succeeded": 8,
            "failed": 0,
            "stale": 0,
            "cancelled": 0,
        }
        with runtime.database.engine.begin() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_results_table)
                )
                == 8
            )
            snapshot = connection.execute(
                select(analysis_content_runs_table.c.runtime_config_snapshot).where(
                    analysis_content_runs_table.c.id == UUID(run_id)
                )
            ).scalar_one()
            assert snapshot["max_concurrency"] == 4
    finally:
        runtime.close()


def test_parallel_transport_error_only_fails_one_content(tmp_path: Path) -> None:
    """Canary 后单条非重试 Transport 错误只终结对应 Content，不重跑整个 Shard。"""

    runtime = _runtime(tmp_path)
    try:
        _seed_provider(runtime, max_concurrency=4)
        client = _client(runtime)
        content_ids = _seed_contents(client, runtime)
        run_id = _create_run(client, content_ids, key="provider-concurrency-one-failure")

        llm = _ConcurrentFakeLLM(max_concurrency=4, fail_parallel_call=2)
        assert _drain(runtime, llm, worker_id="provider-concurrency-failure") == 2
        assert llm.peak_active == 4
        assert llm.item_sizes == [1] * 8

        run = client.get(f"/api/v1/analysis/content-runs/{run_id}")
        assert run.status_code == 200
        assert run.json()["status"] == "partial_failed"
        assert run.json()["stats"] == {
            "pending": 0,
            "succeeded": 7,
            "failed": 1,
            "stale": 0,
            "cancelled": 0,
        }
        with runtime.database.engine.begin() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_results_table)
                )
                == 7
            )
    finally:
        runtime.close()
