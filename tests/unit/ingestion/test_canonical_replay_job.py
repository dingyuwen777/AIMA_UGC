from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.canonical_replay_worker import (
    PostgresCanonicalReplayJobExecutor,
    _new_replay_batch_tuner,
    _replay_batch_tiers,
)
from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_JOB_PAYLOAD_VERSION,
    CANONICAL_REPLAY_JOB_TYPE,
    CanonicalReplayJobHandler,
    CanonicalReplayJobPayload,
    register_canonical_replay_job,
)
from aima_ugc.platform.jobs import JobExecutionFence, JobHandlerResult, JobRegistry
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, ProgrammingError


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[CanonicalReplayJobPayload, JobExecutionFence]] = []

    def execute(self, *, payload, fence, context):  # type: ignore[no-untyped-def]
        del context
        self.calls.append((payload, fence))
        return JobHandlerResult.succeeded({"run_id": str(payload.run_id)})


class _Context:
    def __init__(self, *, cancelled: bool = False) -> None:
        self.fence = JobExecutionFence(job_id=uuid4(), lease_token="lease-token")
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

    assert result.outcome == "succeeded"
    assert executor.calls == [(payload, active.fence)]

    cancelled = handler(payload, _Context(cancelled=True))  # type: ignore[arg-type]
    assert cancelled.outcome == "cancelled"
    assert len(executor.calls) == 1


def test_replay_job_registration_uses_current_payload_contract() -> None:
    registry = JobRegistry()
    handler = CanonicalReplayJobHandler(_Executor())

    register_canonical_replay_job(registry, handler)

    definition = registry.get(CANONICAL_REPLAY_JOB_TYPE)
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


@pytest.mark.parametrize(
    ("error", "outcome", "error_code"),
    [
        (
            ProgrammingError("INSERT", {}, RuntimeError("cardinality violation")),
            "failed",
            "canonical_replay_persistence_invalid",
        ),
        (
            OperationalError("INSERT", {}, RuntimeError("connection lost")),
            "retry",
            "canonical_replay_transient_error",
        ),
    ],
)
def test_replay_persistence_errors_distinguish_permanent_from_transient(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    outcome: str,
    error_code: str,
) -> None:
    """确定性 SQL 错误应及时失败，只有运行时故障才进入退避重试。"""

    executor = PostgresCanonicalReplayJobExecutor(
        SimpleNamespace(logger=logging.getLogger("replay-error-test"))  # type: ignore[arg-type]
    )

    def fail_load(*args: object, **kwargs: object) -> None:
        """模拟预检前的数据库错误，避免测试复制 Job 状态机。"""

        del args, kwargs
        raise error

    monkeypatch.setattr(executor, "_load_execution", fail_load)
    context = _Context()
    result = executor.execute(
        payload=CanonicalReplayJobPayload(run_id=uuid4()),
        fence=context.fence,
        context=context,  # type: ignore[arg-type]
    )

    assert result.outcome == outcome
    assert result.error_code == error_code


def test_replay_default_fast_batch_starts_from_small_measured_tier() -> None:
    """1000 行冻结上限不能再次从大事务起步；先用约八分之一批次验证墙钟。"""

    tiers = _replay_batch_tiers(1000)

    assert tiers == (62, 125, 250, 500, 1000)
    assert tiers[1] == 125


def test_replay_shards_share_the_same_small_batch_tuner() -> None:
    """父/子 Replay 共用 3 秒墙钟控制；分片不能退回固定 1000 行大事务。"""

    tuner = _new_replay_batch_tuner(1000)

    assert tuner is not None
    selected, reason, previous = tuner.choose(
        __import__("aima_ugc.platform.capacity", fromlist=["ResourceSnapshot"]).ResourceSnapshot(
            4.8,
            12 * 1024**3,
            11 * 1024**3,
            "cgroup_v2",
        )
    )
    assert (selected, reason, previous) == (125, "measured_throughput", None)
