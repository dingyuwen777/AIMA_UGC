from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from aima_ugc.modules.ingestion.brand_vehicle_filter import BrandVehicleFilterSnapshot
from aima_ugc.modules.ingestion.import_job import (
    IMPORT_JOB_MAX_ATTEMPTS,
    IMPORT_JOB_PAYLOAD_VERSION,
    IMPORT_JOB_TIMEOUT_SECONDS,
    IMPORT_JOB_TYPE,
    ImportJobHandler,
    ImportJobPayload,
    register_import_job,
)
from aima_ugc.modules.ingestion.historical_jobs import (
    HISTORICAL_IMPORT_CHUNK_JOB_TYPE,
    HistoricalImportChunkJobPayload,
)
from aima_ugc.modules.vehicles.brand_vehicle import BrandVehicleCatalogSnapshot
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry
from pydantic import ValidationError


@dataclass
class _Context:
    cancelled: bool = False

    @property
    def fence(self) -> JobExecutionFence:
        return JobExecutionFence(job_id=uuid4(), lease_token="lease")

    def heartbeat(self, *, progress: int) -> None:
        del progress

    def cancel_requested(self) -> bool:
        return self.cancelled


class _Executor:
    def __init__(self) -> None:
        self.fences: list[JobExecutionFence] = []
        self.payloads: list[ImportJobPayload] = []

    def execute(
        self,
        *,
        payload: ImportJobPayload,
        fence: JobExecutionFence,
        context: _Context,
    ) -> JobHandlerResult:
        del context
        self.payloads.append(payload)
        self.fences.append(fence)
        return JobHandlerResult.succeeded({"batch_id": "batch-1"})


def _payload() -> ImportJobPayload:
    return ImportJobPayload(
        filter_snapshot=BrandVehicleFilterSnapshot(
            catalog=BrandVehicleCatalogSnapshot(
                catalog_version=3,
                filter_scope="all_active",
                selected_brand_ids=(),
                brands=(),
                brand_aliases=(),
                vehicles=(),
                vehicle_aliases=(),
            )
        ),
    )


def test_import_job_contract_freezes_brand_vehicle_filter_snapshot() -> None:
    assert IMPORT_JOB_TYPE == "ingestion.import-excel.v2"
    assert IMPORT_JOB_PAYLOAD_VERSION == "ingestion.import-excel.v2"
    assert IMPORT_JOB_TIMEOUT_SECONDS == 1800
    assert IMPORT_JOB_MAX_ATTEMPTS == 10
    payload = _payload()

    assert payload.schema_version == "ingestion.import-excel.v2"
    assert payload.filter_snapshot.catalog.catalog_version == 3


def test_import_job_contract_rejects_legacy_v1_payload() -> None:
    with pytest.raises(ValidationError):
        ImportJobPayload.model_validate(
            {
                "schema_version": "ingestion.import-excel.v1",
                "relevance": {
                    "schema_version": "relevance-snapshot.v1",
                    "keyword_pack_id": str(uuid4()),
                    "keyword_pack_version": 3,
                    "config_version": 2,
                    "effective_keywords": ["爱玛"],
                },
            }
        )


def test_historical_chunk_job_cleanly_switches_to_pure_canonical_v2() -> None:
    assert HISTORICAL_IMPORT_CHUNK_JOB_TYPE == "ingestion.historical-import-chunk.v2"
    payload = HistoricalImportChunkJobPayload(batch_id=uuid4(), chunk_item_id=uuid4())
    assert payload.schema_version == "ingestion.historical-import-chunk.v2"

    with pytest.raises(ValidationError):
        HistoricalImportChunkJobPayload.model_validate(
            {
                "schema_version": "ingestion.historical-import-chunk.v1",
                "batch_id": str(uuid4()),
                "chunk_item_id": str(uuid4()),
            }
        )


def test_import_job_handler_uses_fence_identity_and_honours_cancellation() -> None:
    executor = _Executor()
    handler = ImportJobHandler(executor)

    payload = _payload()
    cancelled = handler(payload, _Context(cancelled=True))
    succeeded = handler(payload, _Context())

    assert cancelled == JobHandlerResult.cancelled()
    assert succeeded.outcome == "succeeded"
    assert len(executor.fences) == 1
    assert executor.payloads == [payload]


def test_import_job_registers_on_shared_runtime_and_retries_timeout() -> None:
    registry = JobRegistry()
    register_import_job(registry, ImportJobHandler(_Executor()))

    definition = registry.get(IMPORT_JOB_TYPE)

    assert definition.payload_version == IMPORT_JOB_PAYLOAD_VERSION
    assert definition.retry_on_timeout is True
