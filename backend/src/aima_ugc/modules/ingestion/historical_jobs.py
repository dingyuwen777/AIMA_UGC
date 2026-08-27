"""Stage 12 Historical Campaign 的版本化持久 Job。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs import (
    JobExecutionFence,
    JobHandlerResult,
    JobRecord,
    JobRegistry,
)
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol

HISTORICAL_DISCOVER_JOB_TYPE = "ingestion.historical-discover.v1"
HISTORICAL_SNAPSHOT_JOB_TYPE = "ingestion.historical-snapshot.v1"
HISTORICAL_IMPORT_CHUNK_JOB_TYPE = "ingestion.historical-import-chunk.v1"
HISTORICAL_JOB_PRIORITY = -20
HISTORICAL_JOB_MAX_ATTEMPTS = 5
HISTORICAL_DISCOVER_TIMEOUT_SECONDS = 1800
HISTORICAL_SNAPSHOT_TIMEOUT_SECONDS = 7200
HISTORICAL_IMPORT_TIMEOUT_SECONDS = 3600


class HistoricalDiscoverJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ingestion.historical-discover.v1"] = "ingestion.historical-discover.v1"
    campaign_id: UUID


class HistoricalSnapshotJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ingestion.historical-snapshot.v1"] = "ingestion.historical-snapshot.v1"
    campaign_item_id: UUID


class HistoricalImportChunkJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ingestion.historical-import-chunk.v1"] = (
        "ingestion.historical-import-chunk.v1"
    )
    batch_id: UUID
    chunk_item_id: UUID


class HistoricalJobExecutor(Protocol):
    def discover(
        self,
        *,
        payload: HistoricalDiscoverJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...

    def snapshot(
        self,
        *,
        payload: HistoricalSnapshotJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...

    def import_chunk(
        self,
        *,
        payload: HistoricalImportChunkJobPayload,
        fence: JobExecutionFence,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult: ...


class _HistoricalJobHandler:
    def __init__(self, executor: HistoricalJobExecutor, operation: str) -> None:
        self._executor = executor
        self._operation = operation

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        if self._operation == "discover" and isinstance(payload, HistoricalDiscoverJobPayload):
            return self._executor.discover(
                payload=payload,
                fence=context.fence,
                context=context,
            )
        if self._operation == "snapshot" and isinstance(payload, HistoricalSnapshotJobPayload):
            return self._executor.snapshot(
                payload=payload,
                fence=context.fence,
                context=context,
            )
        if self._operation == "import_chunk" and isinstance(
            payload, HistoricalImportChunkJobPayload
        ):
            return self._executor.import_chunk(
                payload=payload,
                fence=context.fence,
                context=context,
            )
        raise TypeError("Historical Job Handler 收到错误 Payload 类型")


def register_historical_jobs(
    registry: JobRegistry,
    executor: HistoricalJobExecutor,
    *,
    terminal_callback: Callable[[Session, JobRecord], None] | None = None,
) -> None:
    registry.register(
        job_type=HISTORICAL_DISCOVER_JOB_TYPE,
        payload_version=HISTORICAL_DISCOVER_JOB_TYPE,
        payload_model=HistoricalDiscoverJobPayload,
        handler=_HistoricalJobHandler(executor, "discover"),
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
    registry.register(
        job_type=HISTORICAL_SNAPSHOT_JOB_TYPE,
        payload_version=HISTORICAL_SNAPSHOT_JOB_TYPE,
        payload_model=HistoricalSnapshotJobPayload,
        handler=_HistoricalJobHandler(executor, "snapshot"),
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )
    registry.register(
        job_type=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
        payload_version=HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
        payload_model=HistoricalImportChunkJobPayload,
        handler=_HistoricalJobHandler(executor, "import_chunk"),
        retry_on_timeout=True,
        terminal_callback=terminal_callback,
    )


__all__ = [
    "HISTORICAL_DISCOVER_JOB_TYPE",
    "HISTORICAL_DISCOVER_TIMEOUT_SECONDS",
    "HISTORICAL_IMPORT_CHUNK_JOB_TYPE",
    "HISTORICAL_IMPORT_TIMEOUT_SECONDS",
    "HISTORICAL_JOB_MAX_ATTEMPTS",
    "HISTORICAL_JOB_PRIORITY",
    "HISTORICAL_SNAPSHOT_JOB_TYPE",
    "HISTORICAL_SNAPSHOT_TIMEOUT_SECONDS",
    "HistoricalDiscoverJobPayload",
    "HistoricalImportChunkJobPayload",
    "HistoricalJobExecutor",
    "HistoricalSnapshotJobPayload",
    "register_historical_jobs",
]
