"""正式 Collection Run Job Payload 与 Handler 契约测试。"""

from uuid import uuid4

import pytest
from aima_ugc.modules.collection.collection_run_job import (
    COLLECTION_RUN_JOB_TYPE,
    COLLECTION_RUN_PAYLOAD_VERSION,
    CollectionRunJobHandler,
    CollectionRunJobPayload,
    register_collection_run_job,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry
from pydantic import ValidationError


class _FakeContext:
    def __init__(self, *, cancelled: bool = False) -> None:
        self._fence = JobExecutionFence(job_id=uuid4(), lease_token="lease-token")
        self._cancelled = cancelled
        self.progress: list[int] = []

    @property
    def fence(self) -> JobExecutionFence:
        return self._fence

    def heartbeat(self, *, progress: int) -> None:
        self.progress.append(progress)

    def cancel_requested(self) -> bool:
        return self._cancelled


class _FakeExecutor:
    def __init__(self) -> None:
        self.fences: list[JobExecutionFence] = []

    def execute(self, *, fence: JobExecutionFence, context: _FakeContext) -> JobHandlerResult:
        self.fences.append(fence)
        context.heartbeat(progress=80)
        return JobHandlerResult.succeeded({"job_id": str(fence.job_id)})


def test_collection_run_job_payload_contains_only_stable_schema_identity() -> None:
    payload = CollectionRunJobPayload()

    assert payload.model_dump(mode="json") == {"schema_version": "collection.run.v1"}


def test_collection_run_job_payload_rejects_unconstrained_run_or_secret_fields() -> None:
    with pytest.raises(ValidationError):
        CollectionRunJobPayload.model_validate(
            {
                "schema_version": "collection.run.v1",
                "run_id": "019c0000-0000-7000-8000-000000000001",
            }
        )

    with pytest.raises(ValidationError):
        CollectionRunJobPayload.model_validate(
            {
                "schema_version": "collection.run.v1",
                "token": "must-not-be-here",
            }
        )


def test_collection_run_job_handler_uses_current_job_fence_and_registry() -> None:
    registry = JobRegistry()
    executor = _FakeExecutor()
    handler = CollectionRunJobHandler(executor)
    register_collection_run_job(registry, handler)
    context = _FakeContext()

    definition = registry.get(COLLECTION_RUN_JOB_TYPE)
    result = definition.handler(CollectionRunJobPayload(), context)

    assert definition.payload_version == COLLECTION_RUN_PAYLOAD_VERSION
    assert executor.fences == [context.fence]
    assert result == JobHandlerResult.succeeded({"job_id": str(context.fence.job_id)})
    assert context.progress == [80]


def test_collection_run_job_handler_cancels_before_business_execution() -> None:
    executor = _FakeExecutor()
    handler = CollectionRunJobHandler(executor)
    context = _FakeContext(cancelled=True)

    result = handler(CollectionRunJobPayload(), context)

    assert result == JobHandlerResult.cancelled()
    assert executor.fences == []
