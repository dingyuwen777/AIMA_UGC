from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from aima_ugc.adapters.persistence.postgres.import_batch_queries import (
    PostgresImportBatchQueryRepository,
)
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.ingestion.import_batch_cursor import ImportBatchCursorPosition
from aima_ugc.modules.ingestion.import_job import IMPORT_JOB_PAYLOAD_VERSION, IMPORT_JOB_TYPE
from aima_ugc.modules.ingestion.query import ImportBatchReadQuery
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.storage.tables import artifacts_table
from sqlalchemy import insert


def _insert_batch(
    session,  # type: ignore[no-untyped-def]
    *,
    created_at: datetime,
    status: str,
    stage: str,
    rows_ingested: int,
    finished_at: datetime | None,
) -> tuple[UUID, UUID]:
    artifact_id = uuid4()
    batch_id = uuid4()
    job_id = uuid4()
    session.execute(
        insert(artifacts_table).values(
            id=artifact_id,
            kind="file-import.raw",
            storage_backend="local",
            storage_key=f"stage8c-query-test/{artifact_id}",
            content_type="application/octet-stream",
            sha256="0" * 64,
            byte_size=0,
            retention_class="raw",
            storage_status="linked",
            created_at=created_at,
            stored_at=created_at,
            linked_at=created_at,
        )
    )
    session.execute(
        insert(jobs_table).values(
            id=job_id,
            job_type=IMPORT_JOB_TYPE,
            payload_version=IMPORT_JOB_PAYLOAD_VERSION,
            payload={},
            result=None,
            status=status,
            internal_idempotency_key=f"stage8c-query-test:{job_id}",
            request_id="stage8c-query-test",
            priority=0,
            attempt=(0 if status == "queued" else 1),
            lease_takeover_count=0,
            max_attempts=10,
            timeout_seconds=1800,
            progress=(100 if status == "succeeded" else 0),
            available_at=created_at,
            started_at=(created_at if status != "queued" else None),
            finished_at=finished_at,
            error_code=("invalid_import" if status == "failed" else None),
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.execute(
        insert(processing_import_batches_table).values(
            id=batch_id,
            input_artifact_id=artifact_id,
            job_id=job_id,
            status=(status if status in {"succeeded", "failed"} else "processing"),
            stats={
                "stage": stage,
                "source_filename": f"{stage}.xlsx",
                "rows_seen": rows_ingested + 1,
                "rows_ingested": rows_ingested,
            },
            error_summary=("invalid_import" if status == "failed" else None),
            created_at=created_at,
            started_at=(created_at if status != "queued" else None),
            finished_at=finished_at,
        )
    )
    return batch_id, job_id


def _query(
    *,
    status: str | None = None,
    identifier: UUID | None = None,
    position: ImportBatchCursorPosition | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 20,
) -> ImportBatchReadQuery:
    return ImportBatchReadQuery(
        identifier=identifier,
        status=status,
        stage=None,
        created_from=created_from,
        created_to=created_to,
        position=position,
        limit=limit,
    )


def test_postgres_batch_list_cursor_filters_and_summary_roll_back_fixture() -> None:
    runtime = create_worker_runtime(settings=load_settings())
    session = runtime.database.new_session()
    transaction = session.begin()
    try:
        day_start = datetime(2099, 8, 21, tzinfo=UTC)
        created = (
            _insert_batch(
                session,
                created_at=day_start + timedelta(hours=4),
                status="queued",
                stage="queued",
                rows_ingested=0,
                finished_at=None,
            ),
            _insert_batch(
                session,
                created_at=day_start + timedelta(hours=3),
                status="succeeded",
                stage="succeeded",
                rows_ingested=7,
                finished_at=day_start + timedelta(hours=5),
            ),
            _insert_batch(
                session,
                created_at=day_start + timedelta(hours=2),
                status="failed",
                stage="failed",
                rows_ingested=0,
                finished_at=day_start + timedelta(hours=5),
            ),
            _insert_batch(
                session,
                created_at=day_start - timedelta(days=1),
                status="succeeded",
                stage="succeeded",
                rows_ingested=99,
                finished_at=day_start - timedelta(hours=1),
            ),
        )
        repository = PostgresImportBatchQueryRepository(session)
        first = repository.list_batches(
            _query(
                created_from=day_start - timedelta(days=2),
                created_to=day_start + timedelta(days=1),
                limit=2,
            )
        )
        second = repository.list_batches(
            _query(
                created_from=day_start - timedelta(days=2),
                created_to=day_start + timedelta(days=1),
                position=ImportBatchCursorPosition(
                    created_at=first[-1].created_at,
                    batch_id=first[-1].batch_id,
                ),
            )
        )
        succeeded = repository.list_batches(
            _query(
                status="succeeded",
                created_from=day_start - timedelta(days=2),
                created_to=day_start + timedelta(days=1),
            )
        )
        by_job = repository.list_batches(_query(identifier=created[2][1]))
        summary = repository.summary(
            today_start_utc=day_start,
            tomorrow_start_utc=day_start + timedelta(days=1),
        )

        assert [record.batch_id for record in first] == [created[0][0], created[1][0]]
        assert [record.batch_id for record in second] == [created[2][0], created[3][0]]
        assert {record.batch_id for record in succeeded} == {created[1][0], created[3][0]}
        assert by_job[0].status == "failed"
        assert by_job[0].error_summary == "invalid_import"
        assert summary.processing_count == 1
        assert summary.completed_today_count == 1
        assert summary.rows_ingested_today == 7
    finally:
        transaction.rollback()
        session.close()
        runtime.close()
