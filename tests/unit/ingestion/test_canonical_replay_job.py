from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.canonical_replay_worker import (
    PostgresCanonicalReplayJobExecutor,
    _new_replay_batch_tuner,
    _partition_resolved_batch,
    _replay_batch_tiers,
    _ReplayScanBatchController,
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


def test_replay_default_fast_batch_keeps_pressure_tier_but_starts_at_quarter_batch() -> None:
    """保留 62 行压力档；正常资源从 250 行起步，减少既有内容的固定 SQL 往返。"""

    tiers = _replay_batch_tiers(1000)

    assert tiers == (62, 125, 250, 500, 1000)
    assert tiers[0] == 62


def test_replay_batch_tiers_can_grow_beyond_persisted_hint() -> None:
    """Replay 的持久值仅是起始提示；资源与实测收益决定真实上界。"""

    tiers = _replay_batch_tiers(1000, allow_resource_growth=True)

    assert tiers[:5] == (62, 125, 250, 500, 1000)
    assert tiers[-1] > 2000


def test_replay_tuner_promotes_past_persisted_hint_on_faster_machine() -> None:
    """高资源机器只有在相邻大批次实测更快时才继续超过 1000。"""

    tuner = _new_replay_batch_tuner(1000, allow_resource_growth=True)
    resources = __import__(
        "aima_ugc.platform.capacity", fromlist=["ResourceSnapshot"]
    ).ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")

    assert tuner is not None
    for size, duration_ms in ((250, 600), (500, 700), (1000, 900)):
        for _ in range(3):
            assert tuner.choose(resources)[0] == size
            tuner.succeeded(size=size, rows=size, duration_ms=duration_ms)

    assert tuner.choose(resources)[:2] == (2000, "throughput_probe")


def test_replay_tuner_starts_old_one_row_task_at_its_hint_then_can_grow() -> None:
    """旧任务的极小提示不能突跳，但成功样本可以解除历史保守值。"""

    tuner = _new_replay_batch_tuner(1, allow_resource_growth=True)
    resources = __import__(
        "aima_ugc.platform.capacity", fromlist=["ResourceSnapshot"]
    ).ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")

    assert tuner is not None
    for _ in range(3):
        assert tuner.choose(resources)[0] == 1
        tuner.succeeded(size=1, rows=1, duration_ms=10)

    assert tuner.choose(resources)[:2] == (2, "throughput_probe")


def test_replay_shards_share_the_same_measured_batch_tuner() -> None:
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
    assert (selected, reason, previous) == (250, "measured_throughput", None)

    for _ in range(3):
        tuner.succeeded(size=250, rows=250, duration_ms=600)
        selected, _, _ = tuner.choose(
            __import__(
                "aima_ugc.platform.capacity", fromlist=["ResourceSnapshot"]
            ).ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")
        )
    assert selected == 500
    for _ in range(3):
        tuner.succeeded(size=500, rows=500, duration_ms=1100)
        selected, reason, _ = tuner.choose(
            __import__(
                "aima_ugc.platform.capacity", fromlist=["ResourceSnapshot"]
            ).ResourceSnapshot(16, 64 * 1024**3, 48 * 1024**3, "cgroup_v2")
        )
    assert (selected, reason) == (1000, "throughput_probe")


@pytest.mark.parametrize(
    ("sampled_rows", "matched_rows", "expected_scan_rows"),
    [
        (100, 80, 157),
        (100, 25, 500),
        (100, 5, 2500),
        (100, 0, 4000),
    ],
)
def test_low_hit_replay_expands_scan_without_expanding_matched_transaction(
    sampled_rows: int,
    matched_rows: int,
    expected_scan_rows: int,
) -> None:
    """低命中只扩大只读扫描，数据库目标批量仍保持 125 条命中记录。"""

    controller = _ReplayScanBatchController(
        max_scan_rows=4000,
        sampled_rows=sampled_rows,
        matched_rows=matched_rows,
    )

    assert controller.choose(matched_target_rows=125) == expected_scan_rows


def test_replay_scan_controller_tracks_recent_hit_ratio() -> None:
    """实际批次命中率变化后，后续扫描窗口应向新负载收敛而不是冻结预检比例。"""

    controller = _ReplayScanBatchController(
        max_scan_rows=4000,
        sampled_rows=100,
        matched_rows=25,
    )
    assert controller.choose(matched_target_rows=125) == 500

    controller.observe(raw_rows=500, matched_rows=25)

    assert controller.choose(matched_target_rows=125) > 500


def test_low_resource_replay_caps_raw_scan_even_when_hit_rate_is_zero() -> None:
    """资源压力下低命中不能用更大的 raw window 抵消批次降档。"""

    controller = _ReplayScanBatchController(
        max_scan_rows=4000,
        sampled_rows=100,
        matched_rows=0,
    )

    assert (
        controller.choose(
            matched_target_rows=62,
            scan_ceiling_rows=248,
        )
        == 248
    )


def test_replay_scan_partition_caps_each_database_transaction_by_matches() -> None:
    """扫描命中率突然升高时，仍按 matched target 切成多个连续事务。"""

    matched = SimpleNamespace(matched=True)
    filtered = SimpleNamespace(matched=False)
    rows = tuple(
        (SimpleNamespace(external_content_id=str(index)), resolution)
        for index, resolution in enumerate(
            (filtered, matched, matched, matched, filtered, matched, matched)
        )
    )

    chunks = _partition_resolved_batch(rows, matched_target_rows=2)  # type: ignore[arg-type]

    assert [len(chunk) for chunk in chunks] == [3, 3, 1]
    assert [sum(resolution.matched for _content, resolution in chunk) for chunk in chunks] == [
        2,
        2,
        1,
    ]
    assert [item.external_content_id for chunk in chunks for item, _resolution in chunk] == [
        str(index) for index in range(7)
    ]
