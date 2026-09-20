"""声音广场投影回填 Job Contract 与取消边界。"""

from __future__ import annotations

from aima_ugc.modules.content.read_model_job import (
    VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION,
    VOICE_PLAZA_PROJECTION_JOB_TYPE,
    VoicePlazaProjectionJobHandler,
    VoicePlazaProjectionJobPayload,
    register_voice_plaza_projection_job,
)
from aima_ugc.platform.jobs import JobHandlerResult, JobRegistry


class _Executor:
    def __init__(self) -> None:
        self.called = False

    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        self.called = True
        assert payload.schema_version == VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION
        assert payload.generation == 1
        assert fence is context.fence
        return JobHandlerResult.succeeded({"projected_count": 10})


class _Context:
    fence = object()

    def __init__(self, *, cancelled: bool = False) -> None:
        self._cancelled = cancelled

    def cancel_requested(self) -> bool:
        return self._cancelled


def test_projection_job_registers_retryable_versioned_payload() -> None:
    registry = JobRegistry()
    executor = _Executor()
    register_voice_plaza_projection_job(
        registry,
        VoicePlazaProjectionJobHandler(executor),
    )

    definition = registry.get(VOICE_PLAZA_PROJECTION_JOB_TYPE)
    assert definition.payload_version == VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION
    assert definition.retry_on_timeout is True
    payload = registry.validate_payload(
        job_type=VOICE_PLAZA_PROJECTION_JOB_TYPE,
        payload_version=VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION,
        payload={
            "schema_version": VOICE_PLAZA_PROJECTION_JOB_PAYLOAD_VERSION,
            "generation": 1,
        },
    )
    result = definition.handler(payload, _Context())  # type: ignore[arg-type]

    assert result.outcome == "succeeded"
    assert executor.called is True


def test_projection_job_stops_before_executor_when_cancelled() -> None:
    executor = _Executor()

    result = VoicePlazaProjectionJobHandler(executor)(
        VoicePlazaProjectionJobPayload(generation=1),
        _Context(cancelled=True),  # type: ignore[arg-type]
    )

    assert result.outcome == "cancelled"
    assert executor.called is False
