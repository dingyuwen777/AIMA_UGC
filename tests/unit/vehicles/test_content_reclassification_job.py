from __future__ import annotations

from uuid import uuid4

from aima_ugc.modules.vehicles.content_reclassification import (
    CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION,
    CONTENT_RECLASSIFICATION_JOB_TYPE,
    ContentReclassificationJobHandler,
    ContentReclassificationJobPayload,
    register_content_reclassification_job,
)
from aima_ugc.platform.jobs import JobHandlerResult, JobRegistry


class _Executor:
    """记录 Handler 是否把正式 Fence 与 Context 原样交给执行器。"""

    def __init__(self) -> None:
        self.called = False

    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        self.called = True
        assert payload.run_id == _RUN_ID
        assert fence is context.fence
        return JobHandlerResult.succeeded({"run_id": str(payload.run_id)})


class _Context:
    """只实现 Job Handler 需要的最小执行上下文。"""

    fence = object()

    def __init__(self, *, cancelled: bool = False) -> None:
        self._cancelled = cancelled

    def cancel_requested(self) -> bool:
        return self._cancelled


_RUN_ID = uuid4()


def test_reclassification_job_registers_versioned_retryable_payload() -> None:
    registry = JobRegistry()
    executor = _Executor()

    register_content_reclassification_job(
        registry,
        ContentReclassificationJobHandler(executor),
    )

    definition = registry.get(CONTENT_RECLASSIFICATION_JOB_TYPE)
    assert definition.payload_version == CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION
    assert definition.retry_on_timeout is True
    payload = registry.validate_payload(
        job_type=CONTENT_RECLASSIFICATION_JOB_TYPE,
        payload_version=CONTENT_RECLASSIFICATION_JOB_PAYLOAD_VERSION,
        payload={
            "schema_version": "vehicles.content-reclassification.v1",
            "run_id": str(_RUN_ID),
        },
    )
    result = definition.handler(payload, _Context())  # type: ignore[arg-type]
    assert result.outcome == "succeeded"
    assert executor.called is True


def test_reclassification_job_stops_before_executor_when_cancelled() -> None:
    executor = _Executor()
    handler = ContentReclassificationJobHandler(executor)

    result = handler(
        ContentReclassificationJobPayload(run_id=_RUN_ID),
        _Context(cancelled=True),  # type: ignore[arg-type]
    )

    assert result.outcome == "cancelled"
    assert executor.called is False
