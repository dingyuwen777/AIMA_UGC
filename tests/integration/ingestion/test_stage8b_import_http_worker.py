from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.collection_targets import PostgresCollectionTargetReader
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.import_worker import PostgresImportJobExecutor
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.modules.content.tables import (
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_TYPE, ImportJobPayload
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from fastapi.testclient import TestClient
from httpx import Response
from openpyxl import Workbook
from sqlalchemy import func, select, update


class _ExecutionContext:
    def __init__(self, fence: JobExecutionFence) -> None:
        self._fence = fence

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        del progress

    def cancel_requested(self) -> bool:
        return False


def _xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(
        [
            "媒体名称（中文）",
            "标题",
            "内文",
            "作者",
            "出版日期",
            "原文链接",
        ]
    )
    sheet.append(
        [
            "小红书",
            "爱玛新品发布",
            "与品牌无关的补充正文",
            "官方账号",
            "2026-08-20 10:00:00",
            "https://www.xiaohongshu.com/explore/stage8b-content-1",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _configure_and_upload(client: TestClient) -> Response:
    pack = client.post(
        "/api/v1/keyword-packs",
        json={"name": f"Stage8B 全局相关性 {uuid4()}"},
    )
    assert pack.status_code == 201
    pack_id = pack.json()["id"]
    keyword = client.post(
        f"/api/v1/keyword-packs/{pack_id}/keywords",
        json={"text": "爱玛", "priority": 10},
    )
    assert keyword.status_code == 201
    configured = client.put(
        "/api/v1/relevance-config",
        json={"keyword_pack_id": pack_id},
    )
    assert configured.status_code == 200
    created = client.post(
        "/api/v1/import-batches",
        files={
            "file": (
                "stage8b.xlsx",
                _xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert created.status_code == 202
    return created


def test_http_upload_worker_and_status_query_use_formal_stage8a_ingestion(tmp_path) -> None:
    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    try:
        service = PostgresImportHttpService(runtime)
        client = TestClient(create_app(import_service=service))
        created = _configure_and_upload(client)

        registry = create_collection_job_registry(runtime=runtime)
        worker = create_job_worker(
            runtime=runtime,
            registry=registry,
            worker_id="stage8b-import-worker",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert worker.run_once() is True
        assert worker.run_once() is False

        batch = client.get(f"/api/v1/import-batches/{created.json()['batch_id']}")
        job = client.get(f"/api/v1/jobs/{created.json()['job_id']}")
        assert batch.status_code == job.status_code == 200
        assert batch.json()["status"] == batch.json()["stage"] == "succeeded"
        assert batch.json()["stats"]["rows_seen"] == 1
        assert batch.json()["stats"]["rows_ingested"] == 1
        assert job.json()["status"] == "succeeded"
        assert job.json()["attempt"] == 1

        session = runtime.database.new_session()
        try:
            with session.begin():
                supplement_targets = PostgresCollectionTargetReader(session).list_batch_targets(
                    batch_id=UUID(created.json()["batch_id"]),
                    platforms=("xhs",),
                )
        finally:
            session.close()
        assert len(supplement_targets) == 1
        assert supplement_targets[0].platform == "xhs"
        assert supplement_targets[0].external_content_id == "stage8b-content-1"

        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            assert connection.scalar(select(func.count()).select_from(content_versions_table)) == 1
            assert (
                connection.scalar(
                    select(func.count()).select_from(content_metric_observations_table)
                )
                == 1
            )
            persisted_batch = (
                connection.execute(select(processing_import_batches_table)).mappings().one()
            )
            persisted_job = connection.execute(select(jobs_table)).mappings().one()
            persisted_artifact = connection.execute(select(artifacts_table)).mappings().one()
        assert persisted_batch["job_id"] == persisted_job["id"]
        assert persisted_batch["status"] == "succeeded"
        assert persisted_artifact["storage_status"] == "linked"
        assert persisted_batch["stats"]["relevance"]["effective_keywords"] == ["爱玛"]
        assert persisted_job["payload"]["relevance"] == persisted_batch["stats"]["relevance"]
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()


def test_unavailable_source_artifact_fails_job_and_batch_without_content(tmp_path) -> None:
    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    try:
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        created = _configure_and_upload(client)
        with runtime.database.engine.begin() as connection:
            connection.execute(update(artifacts_table).values(storage_status="error"))

        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage8b-unavailable-artifact",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert worker.run_once() is True

        batch = client.get(f"/api/v1/import-batches/{created.json()['batch_id']}")
        job = client.get(f"/api/v1/jobs/{created.json()['job_id']}")
        assert batch.json()["status"] == batch.json()["stage"] == "failed"
        assert batch.json()["error_summary"] == "invalid_import"
        assert job.json()["status"] == "failed"
        assert job.json()["error_code"] == "invalid_import"
        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 0
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()


def test_import_retry_after_business_commit_is_fenced_and_does_not_duplicate_content(
    tmp_path: Path,
) -> None:
    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
        )
    try:
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        created = _configure_and_upload(client)
        session = runtime.database.new_session()
        try:
            with session.begin():
                first_job = PostgresJobRepository(session).claim_next(
                    supported_job_types=(IMPORT_JOB_TYPE,),
                    worker_id="stage8b-first-attempt",
                    lease_seconds=120,
                )
        finally:
            session.close()
        assert first_job is not None and first_job.lease_token is not None
        first_fence = JobExecutionFence(
            job_id=first_job.id,
            lease_token=first_job.lease_token,
        )
        first_result = PostgresImportJobExecutor(runtime).execute(
            payload=ImportJobPayload.model_validate(first_job.payload),
            fence=first_fence,
            context=_ExecutionContext(first_fence),
        )
        assert first_result.outcome == "succeeded"

        with runtime.database.engine.begin() as connection:
            connection.execute(
                update(jobs_table)
                .where(jobs_table.c.id == first_job.id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        session = runtime.database.new_session()
        try:
            with session.begin():
                retry_job = PostgresJobRepository(session).claim_next(
                    supported_job_types=(IMPORT_JOB_TYPE,),
                    worker_id="stage8b-retry-attempt",
                    lease_seconds=120,
                )
        finally:
            session.close()
        assert retry_job is not None and retry_job.lease_token is not None
        retry_fence = JobExecutionFence(
            job_id=retry_job.id,
            lease_token=retry_job.lease_token,
        )
        with pytest.raises(LeaseLostError):
            PostgresImportJobExecutor(runtime).execute(
                payload=ImportJobPayload.model_validate(first_job.payload),
                fence=first_fence,
                context=_ExecutionContext(first_fence),
            )
        retry_result = PostgresImportJobExecutor(runtime).execute(
            payload=ImportJobPayload.model_validate(retry_job.payload),
            fence=retry_fence,
            context=_ExecutionContext(retry_fence),
        )
        assert retry_result.outcome == "succeeded"

        session = runtime.database.new_session()
        try:
            with session.begin():
                PostgresJobRepository(session).succeed(
                    job_id=retry_job.id,
                    lease_token=retry_job.lease_token,
                    result=retry_result.result,
                )
        finally:
            session.close()
        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            assert connection.scalar(select(func.count()).select_from(content_versions_table)) == 1
            batch = connection.execute(select(processing_import_batches_table)).mappings().one()
            assert str(batch["id"]) == created.json()["batch_id"]
            assert batch["status"] == "succeeded"
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()
