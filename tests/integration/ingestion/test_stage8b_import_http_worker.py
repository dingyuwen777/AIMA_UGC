from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from aima_ugc.adapters.persistence.postgres.collection_targets import PostgresCollectionTargetReader
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.brand_vehicle_http import PostgresBrandVehicleHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.import_worker import PostgresImportJobExecutor
from aima_ugc.bootstrap.worker import create_collection_job_registry, create_job_worker, create_worker_runtime
from aima_ugc.contracts.brand_vehicle import BrandCreateRequest
from aima_ugc.modules.content.tables import content_metric_observations_table, content_versions_table, contents_table
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.ingestion.import_job import (
    BRAND_VEHICLE_IMPORT_JOB_TYPE,
    BrandVehicleImportJobPayload,
)
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
    sheet.append(["媒体名称（中文）", "标题", "内文", "作者", "出版日期", "原文链接"])
    sheet.append([
        "小红书",
        "爱玛新品发布",
        "与品牌无关的补充正文",
        "官方账号",
        "2026-08-20 10:00:00",
        "https://www.xiaohongshu.com/explore/stage8b-content-1",
    ])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _principal() -> Principal:
    return Principal(
        principal_id="stage3-import-admin",
        display_name="Stage3 Import 管理员",
        role="administrator",
        source="development",
    )


def _configure_and_upload(client: TestClient, runtime) -> Response:  # type: ignore[no-untyped-def]
    brand = PostgresBrandVehicleHttpService(runtime).create_brand(
        BrandCreateRequest(
            code="AIMA-STAGE3-IMPORT",
            display_name="爱玛",
            role="owned",
            aliases=("爱玛",),
        ),
        principal=_principal(),
        request_id="stage3-import-brand",
    )
    created = client.post(
        "/api/v1/import-batches",
        files=[
            (
                "file",
                (
                    "stage8b.xlsx",
                    _xlsx(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("brand_ids", (None, str(brand.id))),
        ],
    )
    assert created.status_code == 202
    return created


def _truncate(runtime) -> None:  # type: ignore[no-untyped-def]
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, vehicle_brands, accounts "
            "RESTART IDENTITY CASCADE"
        )


def test_http_upload_worker_and_status_query_use_stage3_brand_filter(tmp_path) -> None:
    settings = load_settings().model_copy(update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"})
    runtime = create_worker_runtime(settings=settings)
    _truncate(runtime)
    try:
        service = PostgresImportHttpService(runtime)
        client = TestClient(create_app(import_service=service))
        created = _configure_and_upload(client, runtime)

        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage3-import-worker",
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
                    platforms=("xiaohongshu",),
                )
        finally:
            session.close()
        assert len(supplement_targets) == 1
        assert supplement_targets[0].external_content_id == "stage8b-content-1"

        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 1
            assert connection.scalar(select(func.count()).select_from(content_versions_table)) == 1
            assert connection.scalar(select(func.count()).select_from(content_metric_observations_table)) == 1
            persisted_batch = connection.execute(select(processing_import_batches_table)).mappings().one()
            persisted_job = connection.execute(select(jobs_table)).mappings().one()
            persisted_artifact = connection.execute(select(artifacts_table)).mappings().one()
        assert persisted_batch["job_id"] == persisted_job["id"]
        assert persisted_batch["status"] == "succeeded"
        assert persisted_artifact["storage_status"] == "linked"
        snapshot = persisted_batch["stats"]["filter_snapshot"]
        assert snapshot["schema_version"] == "brand-vehicle-filter.v1"
        assert snapshot["search_semantics"] == "not_applicable"
        assert persisted_job["payload"]["filter_snapshot"] == snapshot
        assert persisted_job["job_type"] == BRAND_VEHICLE_IMPORT_JOB_TYPE
        assert "keyword_selection" not in persisted_job["payload"]
    finally:
        _truncate(runtime)
        runtime.close()


def test_unavailable_source_artifact_fails_job_and_batch_without_content(tmp_path) -> None:
    settings = load_settings().model_copy(update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"})
    runtime = create_worker_runtime(settings=settings)
    _truncate(runtime)
    try:
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        created = _configure_and_upload(client, runtime)
        with runtime.database.engine.begin() as connection:
            connection.execute(update(artifacts_table).values(storage_status="error"))

        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage3-unavailable-artifact",
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
        _truncate(runtime)
        runtime.close()


def test_import_retry_after_business_commit_is_fenced_and_does_not_duplicate_content(tmp_path: Path) -> None:
    settings = load_settings().model_copy(update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"})
    runtime = create_worker_runtime(settings=settings)
    _truncate(runtime)
    try:
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        created = _configure_and_upload(client, runtime)
        session = runtime.database.new_session()
        try:
            with session.begin():
                first_job = PostgresJobRepository(session).claim_next(
                    supported_job_types=(BRAND_VEHICLE_IMPORT_JOB_TYPE,),
                    worker_id="stage3-first-attempt",
                    lease_seconds=120,
                )
        finally:
            session.close()
        assert first_job is not None and first_job.lease_token is not None
        first_fence = JobExecutionFence(job_id=first_job.id, lease_token=first_job.lease_token)
        first_result = PostgresImportJobExecutor(runtime).execute(
            payload=BrandVehicleImportJobPayload.model_validate(first_job.payload),
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
                    supported_job_types=(BRAND_VEHICLE_IMPORT_JOB_TYPE,),
                    worker_id="stage3-retry-attempt",
                    lease_seconds=120,
                )
        finally:
            session.close()
        assert retry_job is not None and retry_job.lease_token is not None
        retry_fence = JobExecutionFence(job_id=retry_job.id, lease_token=retry_job.lease_token)
        with pytest.raises(LeaseLostError):
            PostgresImportJobExecutor(runtime).execute(
                payload=BrandVehicleImportJobPayload.model_validate(first_job.payload),
                fence=first_fence,
                context=_ExecutionContext(first_fence),
            )
        retry_result = PostgresImportJobExecutor(runtime).execute(
            payload=BrandVehicleImportJobPayload.model_validate(retry_job.payload),
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
        _truncate(runtime)
        runtime.close()
