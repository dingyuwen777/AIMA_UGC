"""Historical Campaign 取消对活动 Job 的 PostgreSQL 回归。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.historical_cancellation import (
    PostgresHistoricalCancellationRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.adapters.persistence.postgres.jobs import PostgresJobRepository
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_JOB_MAX_ATTEMPTS,
    HISTORICAL_JOB_PRIORITY,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
    HISTORICAL_SNAPSHOT_TIMEOUT_SECONDS,
    HistoricalSnapshotJobPayload,
)
from aima_ugc.modules.ingestion.historical_tables import historical_import_campaign_items_table
from aima_ugc.platform.config import load_settings
from sqlalchemy import update


def test_cancel_requests_running_snapshot_after_item_becomes_ready(tmp_path) -> None:
    """Item 已提交 ready、Job 尚未落终态时，取消仍必须命中这个 running Snapshot Job。"""

    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
            "historical_import_root": None,
        }
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )

        campaign_id = uuid4()
        session = runtime.database.new_session()
        try:
            with session.begin():
                campaigns = PostgresHistoricalImportRepository(session)
                campaigns.create_campaign(
                    campaign_id=campaign_id,
                    client_idempotency_key=f"snapshot-cancel-window-{uuid4()}",
                    root_relative_path="",
                    recursive=False,
                    profile_snapshot={},
                    keyword_pack_snapshot={},
                    source_kind="local_upload",
                    ingestion_policy="standard_observation",
                    declared_file_count=1,
                    initial_status="snapshotting",
                )
                source = campaigns.insert_local_source_items(
                    campaign_id=campaign_id,
                    files=(("local.xlsx", 1),),
                )[0]
                source_id = source["id"]
                payload = HistoricalSnapshotJobPayload(campaign_item_id=source_id)
                job = PostgresJobRepository(session).enqueue(
                    job_type=HISTORICAL_SNAPSHOT_JOB_TYPE,
                    payload_version=HISTORICAL_SNAPSHOT_JOB_TYPE,
                    payload=payload.model_dump(mode="json"),
                    internal_idempotency_key=f"snapshot-cancel-window:{source_id}",
                    request_id=None,
                    priority=HISTORICAL_JOB_PRIORITY,
                    max_attempts=HISTORICAL_JOB_MAX_ATTEMPTS,
                    timeout_seconds=HISTORICAL_SNAPSHOT_TIMEOUT_SECONDS,
                )
        finally:
            session.close()

        session = runtime.database.new_session()
        try:
            with session.begin():
                claimed = PostgresJobRepository(session).claim_next(
                    supported_job_types=(HISTORICAL_SNAPSHOT_JOB_TYPE,),
                    worker_id="snapshot-cancel-window-worker",
                    lease_seconds=120,
                )
                assert claimed is not None
                assert claimed.id == job.id
                assert claimed.status == "running"
        finally:
            session.close()

        # Snapshot handler 的业务事务已经把 Item 提交为 ready，
        # 但 Durable Job 结果仍处于 running；这是 handler 返回与结果落库之间的真实窗口。
        session = runtime.database.new_session()
        try:
            with session.begin():
                session.execute(
                    update(historical_import_campaign_items_table)
                    .where(historical_import_campaign_items_table.c.id == source_id)
                    .values(status="ready", job_id=job.id)
                )
        finally:
            session.close()

        session = runtime.database.new_session()
        try:
            with session.begin():
                PostgresHistoricalCancellationRepository(session).begin_cancel(campaign_id)
        finally:
            session.close()

        session = runtime.database.new_session()
        try:
            with session.begin():
                PostgresHistoricalCancellationRepository(session).request_job_cancellations(
                    campaign_id
                )
        finally:
            session.close()

        session = runtime.database.new_session()
        try:
            with session.begin():
                current = PostgresJobRepository(session).get(job.id)
                assert current is not None
                assert current.status == "running"
                assert current.cancel_requested_at is not None
        finally:
            session.close()
    finally:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        runtime.close()
