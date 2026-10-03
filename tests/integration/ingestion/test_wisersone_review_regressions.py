"""独立审查的取消传播、前置恢复与清理竞争反例。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID

import pytest
from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.historical_import_worker import PostgresHistoricalImportJobExecutor
from aima_ugc.bootstrap.wisersone_cleanup import cleanup_wisersone_files
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
)
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaigns_table
from aima_ugc.modules.ingestion.wisersone_tables import wisersone_downloads_table
from aima_ugc.platform.jobs import JobHandlerResult
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import func, select, update

from .test_wisersone_workflow import _create
from .test_wisersone_workflow import workflow as workflow


def _campaign(workflow):
    runtime, _, client, brand, new_worker, tick = workflow
    result = _create(client, brand)
    worker = new_worker()
    tick(worker)
    tick(worker)
    result = client.get(f"/api/v1/wisersone-downloads/{result['id']}").json()
    assert result["campaign_id"]
    return runtime, client, worker, tick, result


def _settle(client, worker, tick, download_id, expected):
    for _ in range(30):
        result = client.get(f"/api/v1/wisersone-downloads/{download_id}").json()
        if result["status"] in expected:
            return result
        tick(worker)
    pytest.fail(f"下载未收敛到 {expected}：{result}")


def test_cancel_intent_survives_interrupted_parent_job_cancellation(workflow, monkeypatch):
    runtime, client, _, tick, created = _campaign(workflow)
    original = PostgresJobRepository.request_cancel

    def interrupted(*args, **kwargs):
        raise OSError("模拟 HTTP 在取消意图提交后退出")

    monkeypatch.setattr(PostgresJobRepository, "request_cancel", interrupted)
    with pytest.raises(OSError):
        client.post(f"/api/v1/wisersone-downloads/{created['id']}/cancel")
    monkeypatch.setattr(PostgresJobRepository, "request_cancel", original)
    worker = workflow[4]()
    _settle(client, worker, tick, created["id"], {"cancelled"})
    with runtime.database.engine.connect() as connection:
        assert (
            connection.scalar(
                select(historical_import_campaigns_table.c.status).where(
                    historical_import_campaigns_table.c.id == UUID(created["campaign_id"])
                )
            )
            == "cancelled"
        )
        assert connection.scalar(select(func.count()).select_from(contents_table)) == 0
    assert workflow[1].submissions == 1


@pytest.mark.parametrize("stage", ["discover", "snapshot"])
def test_preflight_infrastructure_failure_resumes_same_campaign(workflow, monkeypatch, stage):
    runtime, client, worker, tick, created = _campaign(workflow)
    job_type = HISTORICAL_DISCOVER_JOB_TYPE if stage == "discover" else HISTORICAL_SNAPSHOT_JOB_TYPE
    if stage == "snapshot":
        tick(worker)  # discovery 创建同一个 Source Item
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(jobs_table).where(jobs_table.c.job_type == job_type).values(max_attempts=1)
        )
    if stage == "discover":
        from aima_ugc.modules.ingestion.historical_directory import HistoricalDirectoryBrowser

        target, method = HistoricalDirectoryBrowser, "discover_xlsx"
    else:
        target, method = PostgresHistoricalImportJobExecutor, "_bound_source_artifact"
    original = getattr(target, method)

    def broken(*args, **kwargs):
        raise OSError("模拟可恢复的存储故障")

    monkeypatch.setattr(target, method, broken)
    _settle(client, worker, tick, created["id"], {"failed"})
    monkeypatch.setattr(target, method, original)
    response = client.post(f"/api/v1/wisersone-downloads/{created['id']}/retry")
    assert response.status_code == 200, response.text
    result = _settle(client, workflow[4](), tick, created["id"], {"succeeded"})
    assert result["campaign_id"] == created["campaign_id"]
    assert workflow[1].submissions == 1


def _failed_chunks(workflow, monkeypatch):
    runtime, client, worker, tick, created = _campaign(workflow)
    original = PostgresHistoricalImportJobExecutor.import_chunk
    monkeypatch.setattr(
        PostgresHistoricalImportJobExecutor,
        "import_chunk",
        lambda *args, **kwargs: JobHandlerResult.failed("historical_chunk_io_failed"),
    )
    _settle(client, worker, tick, created["id"], {"failed", "partial_failed"})
    monkeypatch.setattr(PostgresHistoricalImportJobExecutor, "import_chunk", original)
    past = beijing_now() - timedelta(days=8)
    with runtime.database.engine.begin() as connection:
        connection.execute(
            update(wisersone_downloads_table)
            .where(wisersone_downloads_table.c.id == UUID(created["id"]))
            .values(finished_at=past)
        )
        connection.execute(
            update(historical_import_campaigns_table)
            .where(historical_import_campaigns_table.c.id == UUID(created["campaign_id"]))
            .values(finished_at=past)
        )
    return runtime, client, worker, tick, created


def test_retry_holds_shared_admission_against_ttl_claim(workflow, monkeypatch):
    runtime, client, _, _, created = _failed_chunks(workflow, monkeypatch)
    entered, release, cleanup_started = Event(), Event(), Event()
    original = PostgresHistoricalImportRepository.prepare_failed_retry

    def blocked(self, campaign_id):
        entered.set()
        assert release.wait(10)
        return original(self, campaign_id)

    monkeypatch.setattr(PostgresHistoricalImportRepository, "prepare_failed_retry", blocked)

    def cleanup():
        cleanup_started.set()
        return cleanup_wisersone_files(runtime)

    with ThreadPoolExecutor(max_workers=2) as pool:
        retry = pool.submit(client.post, f"/api/v1/wisersone-downloads/{created['id']}/retry")
        assert entered.wait(10)
        deletion = pool.submit(cleanup)
        assert cleanup_started.wait(10)
        try:
            # SKIP LOCKED 直接跳过恢复持有的下载行，不能认领原文件删除。
            assert deletion.result(timeout=10) == 0
        finally:
            release.set()
        assert retry.result(timeout=10).status_code == 200
        assert deletion.result(timeout=10) == 0
    published = runtime.settings.wisersone_input_dir / created["id"] / "wisersone_last24h.xlsx"
    assert published.exists()
