"""Historical Campaign Job 取消后的终态收敛。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.historical_cancellation import (
    PostgresHistoricalCancellationRepository,
)
from aima_ugc.adapters.persistence.postgres.historical_import import (
    PostgresHistoricalImportRepository,
)
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_DISCOVER_JOB_TYPE,
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
    HISTORICAL_SNAPSHOT_JOB_TYPE,
    HistoricalDiscoverJobPayload,
    HistoricalImportChunkJobPayload,
    HistoricalSnapshotJobPayload,
)
from aima_ugc.platform.jobs import JobRecord

from .historical_import_worker import historical_job_terminal_callback


def historical_cancellation_terminal_callback(session: Session, job: JobRecord) -> None:
    """先执行既有终态逻辑，再在取消 Job 全部收敛后结束 Campaign。"""

    historical_job_terminal_callback(session, job)
    if job.status != "cancelled":
        return
    campaign_id = _campaign_id_for_job(session, job)
    if campaign_id is None:
        return
    PostgresHistoricalCancellationRepository(session).settle_cancel(campaign_id)


def _campaign_id_for_job(session: Session, job: JobRecord) -> UUID | None:
    if job.job_type == HISTORICAL_DISCOVER_JOB_TYPE:
        return HistoricalDiscoverJobPayload.model_validate(job.payload).campaign_id

    repository = PostgresHistoricalImportRepository(session)
    if job.job_type == HISTORICAL_SNAPSHOT_JOB_TYPE:
        payload = HistoricalSnapshotJobPayload.model_validate(job.payload)
        item = repository.get_item(payload.campaign_item_id)
    elif job.job_type == HISTORICAL_IMPORT_CHUNK_JOB_TYPE:
        payload = HistoricalImportChunkJobPayload.model_validate(job.payload)
        item = repository.get_item(payload.chunk_item_id)
    else:
        return None
    return cast(UUID, item["campaign_id"]) if item is not None else None


__all__ = ["historical_cancellation_terminal_callback"]