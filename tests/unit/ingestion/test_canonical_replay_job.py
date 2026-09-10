from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel

from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
    CANONICAL_REPLAY_JOB_TYPE,
    CanonicalReplayJobHandler,
    CanonicalReplayJobPayload,
    register_canonical_replay_job,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[CanonicalReplayJobPayload, JobExecutionFence]] = []

    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        del context
        self.calls.append((payload, fence))
        return JobHandlerResult.succeeded({"run_id": str(payload.run_id)})


class _Context:
    def __init__(self, *, cancelled: bool = False) -> None:
        self.fence = JobExecutionFence(job_id=uuid4(), worker_id="worker", fencing_token=3)
        self._cancelled = cancelled

    def heartbeat(self, *, progress=None):  # type: ignore[no-untyped-def]
        del progress

    def cancel_requested(self) -> bool:
        return self._cancelled


def test_replay_payload_is_versioned_and_forbids_extra_fields() -> None:
    run_id = uuid4()
    payload = CanonicalReplayJobPayload(run_id=run_id)

    assert payload.model_dump(mode="json") == {
        "schema_version": CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
        "run_id": str(run_id),
    }
    assert CANONICAL_REPLAY_JOB_TYPE == "ingestion.canonical-replay.v1"


def test_replay_handler_delegates_with_current_fence_and_short_circuits_cancel() -> None:
    executor = _Executor()
    handler = CanonicalReplayJobHandler(executor)
    payload = CanonicalReplayJobPayload(run_id=uuid4())
    active = _Context()

    result = handler(payload, active)  # type: ignore[arg-type]

    assert result.status == "succeeded"
    assert executor.calls == [(payload, active.fence)]

    cancelled = handler(payload, _Context(cancelled=True))  # type: ignore[arg-type]
    assert cancelled.status == "cancelled"
    assert len(executor.calls) == 1


def test_replay_job_registration_uses_current_payload_contract() -> None:
    registry = JobRegistry()
    handler = CanonicalReplayJobHandler(_Executor())

    register_canonical_replay_job(registry, handler)

    definition = registry.get(CANONICAL_REPLAY_JOB_TYPE)
    assert definition is not None
    assert definition.payload_version == CANONICAL_REPLAY_JOB_PAYLOAD_VERSION
    assert definition.payload_model is CanonicalReplayJobPayload
    assert definition.retry_on_timeout is True

    class _WrongPayload(BaseModel):
        value: str

    try:
        handler(_WrongPayload(value="wrong"), _Context())  # type: ignore[arg-type]
    except TypeError as exc:
        assert "Replay" in str(exc)
    else:  # pragma: no cover - 明确要求失败关闭
        raise AssertionError("错误 Payload 必须失败关闭")
