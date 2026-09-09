"""Data Import Campaign 预检与执行取消的 PostgreSQL 回归。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.historical_import_http import PostgresHistoricalImportHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.platform.config import load_settings
from fastapi.testclient import TestClient
from openpyxl import Workbook


def _xlsx() -> bytes:
    """生成一行可稳定导入的最小 Excel。"""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    sheet.append(
        [
            "小红书",
            "爱玛取消回归",
            "取消并发不能让 Worker 崩溃",
            "测试用户",
            "2026-09-09 10:00:00",
            "https://www.xiaohongshu.com/explore/cancel-regression",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _keyword_pack(client: TestClient) -> str:
    """创建导入所需的最小词包。"""

    created = client.post("/api/v1/keyword-packs", json={"name": f"取消回归 {uuid4()}"})
    assert created.status_code == 201
    pack_id = created.json()["id"]
    added = client.post(
        f"/api/v1/keyword-packs/{pack_id}/keywords",
        json={"text": "爱玛", "priority": 10},
    )
    assert added.status_code == 201
    return pack_id


def _create_local_campaign(client: TestClient, payload: bytes) -> str:
    """创建、上传并 finalize 一个本地 Excel Campaign，使其进入预检。"""

    pack_id = _keyword_pack(client)
    created = client.post(
        "/api/v1/data-import-campaigns/local",
        json={
            "client_idempotency_key": f"cancel-regression-{uuid4()}",
            "files": [{"relative_path": "local.xlsx", "byte_size": len(payload)}],
            "keyword_pack_ids": [pack_id],
            "ingestion_policy": "standard_observation",
        },
    )
    assert created.status_code == 201
    campaign_id = created.json()["campaign_id"]
    item_id = created.json()["upload_items"][0]["item_id"]
    uploaded = client.put(
        f"/api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content",
        files={
            "file": (
                "local.xlsx",
                payload,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert uploaded.status_code == 200
    finalized = client.post(f"/api/v1/data-import-campaigns/{campaign_id}/finalize")
    assert finalized.status_code == 202
    assert finalized.json()["status"] == "snapshotting"
    return campaign_id


def _runtime(tmp_path: Path):
    """创建使用真实 PostgreSQL 的隔离 Worker Runtime。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
            "historical_import_root": None,
            "historical_chunk_rows": 100,
            "historical_max_in_flight_jobs": 1,
        }
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    return runtime


def _client(runtime) -> TestClient:
    """返回接入真实 Historical/Import Service 的测试客户端。"""

    return TestClient(
        create_app(
            historical_import_service=PostgresHistoricalImportHttpService(runtime),
            import_service=PostgresImportHttpService(runtime),
        )
    )


def _cleanup(runtime) -> None:
    """清理 PostgreSQL 回归数据并关闭 Runtime。"""

    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    runtime.close()


def test_local_campaign_can_cancel_during_snapshot_preflight(tmp_path: Path) -> None:
    """本地 Excel finalize 后的 snapshotting 预检必须可以直接取消。"""

    runtime = _runtime(tmp_path)
    try:
        client = _client(runtime)
        campaign_id = _create_local_campaign(client, _xlsx())

        cancelled = client.post(f"/api/v1/data-import-campaigns/{campaign_id}/cancel")

        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["finished_at"] is not None
        items = client.get(f"/api/v1/data-import-campaigns/{campaign_id}/items").json()["items"]
        assert items
        assert all(item["status"] == "cancelled" for item in items)
    finally:
        _cleanup(runtime)


def test_running_import_cancel_does_not_deadlock_worker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """并发取消不得形成 Campaign→Job 与 Job→Campaign 的锁序死锁。"""

    runtime = _runtime(tmp_path)
    try:
        client = _client(runtime)
        campaign_id = _create_local_campaign(client, _xlsx())
        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="cancel-regression-worker",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert worker.run_once() is True
        ready = client.get(f"/api/v1/data-import-campaigns/{campaign_id}").json()
        assert ready["status"] == "ready"
        started = client.post(f"/api/v1/data-import-campaigns/{campaign_id}/start")
        assert started.status_code == 200
        assert started.json()["status"] == "queued"

        campaign_lock_window = Event()
        cancel_reached_job = Event()
        original_mark_chunk_running = PostgresHistoricalImportRepository.mark_chunk_running
        original_request_cancel = PostgresJobRepository.request_cancel

        def coordinated_mark_chunk_running(self, item_id: UUID) -> None:
            """暂停在 Worker 已锁 Job、尚未申请 Item/Campaign 锁的反向锁序窗口。"""

            campaign_lock_window.set()
            if not cancel_reached_job.wait(timeout=10):
                raise AssertionError("取消请求未进入 Job 锁阶段")
            original_mark_chunk_running(self, item_id)

        def coordinated_request_cancel(self, job_id: UUID):
            """记录取消事务即将申请 Job 锁的时点。"""

            cancel_reached_job.set()
            return original_request_cancel(self, job_id)

        monkeypatch.setattr(
            PostgresHistoricalImportRepository,
            "mark_chunk_running",
            coordinated_mark_chunk_running,
        )
        monkeypatch.setattr(
            PostgresJobRepository,
            "request_cancel",
            coordinated_request_cancel,
        )

        worker_errors: list[BaseException] = []
        cancel_errors: list[BaseException] = []
        cancel_status: list[int] = []
        cancel_states: list[str] = []

        def run_worker() -> None:
            """在独立线程执行真实 Import Chunk Worker。"""

            try:
                assert worker.run_once() is True
            except BaseException as exc:  # pragma: no cover - 失败内容由断言统一报告
                worker_errors.append(exc)

        def request_cancel() -> None:
            """在 Worker 持有 Job 锁时通过真实 HTTP 入口并发请求取消。"""

            try:
                response = client.post(f"/api/v1/data-import-campaigns/{campaign_id}/cancel")
                cancel_status.append(response.status_code)
                cancel_states.append(response.json()["status"])
            except BaseException as exc:  # pragma: no cover - 失败内容由断言统一报告
                cancel_errors.append(exc)

        worker_thread = Thread(target=run_worker, name="cancel-regression-worker-thread")
        worker_thread.start()
        assert campaign_lock_window.wait(timeout=10)
        cancel_thread = Thread(target=request_cancel, name="cancel-regression-http-thread")
        cancel_thread.start()

        worker_thread.join(timeout=15)
        cancel_thread.join(timeout=15)
        assert not worker_thread.is_alive(), "Worker 未在限定时间内收敛"
        assert not cancel_thread.is_alive(), "取消请求未在限定时间内收敛"
        assert worker_errors == []
        assert cancel_errors == []
        assert cancel_status == [200]
        assert cancel_states == ["cancelling"]

        campaign = client.get(f"/api/v1/data-import-campaigns/{campaign_id}").json()
        assert campaign["status"] == "cancelled"
        assert campaign["finished_at"] is not None
    finally:
        _cleanup(runtime)
