"""Analysis 公共有界并发执行器回归。"""

from __future__ import annotations

from threading import Event, Lock

import pytest

from aima_ugc.modules.analysis.concurrent_labeling import run_bounded_concurrently


def test_bounded_executor_reaches_and_never_exceeds_configured_concurrency() -> None:
    """真实线程执行时峰值在途必须达到且不超过配置上限。"""

    max_concurrency = 20
    release = Event()
    lock = Lock()
    active = 0
    peak = 0
    completed: list[int] = []

    def task(value: int) -> int:
        """阻塞任务直到全部 worker 已有机会进入。"""

        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if peak == max_concurrency:
                release.set()
        assert release.wait(timeout=2)
        with lock:
            active -= 1
        return value * 2

    summary = run_bounded_concurrently(
        range(40),
        task=task,
        max_concurrency=max_concurrency,
        on_completed=lambda outcomes: completed.extend(
            outcome.result for outcome in outcomes if outcome.result is not None
        ),
        canary=False,
        fail_fast=True,
    )

    assert peak == max_concurrency
    assert summary.peak_in_flight == max_concurrency
    assert summary.completed == 40
    assert sorted(completed) == [value * 2 for value in range(40)]


def test_bounded_executor_canary_failure_prevents_fanout() -> None:
    """Canary 失败时不得继续提交其余 Provider 请求。"""

    called: list[int] = []

    def task(value: int) -> int:
        """首条任务模拟 Provider 配置错误。"""

        called.append(value)
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_bounded_concurrently(
            range(100),
            task=task,
            max_concurrency=50,
            on_completed=lambda _outcomes: None,
            canary=True,
            fail_fast=False,
        )

    assert called == [0]


def test_bounded_executor_can_isolate_parallel_item_errors() -> None:
    """Formal 模式可以把单条失败作为 outcome 返回并继续处理其他条目。"""

    received: list[tuple[int, bool]] = []

    def task(value: int) -> int:
        """只让一个并行条目失败。"""

        if value == 3:
            raise ValueError("bad item")
        return value

    summary = run_bounded_concurrently(
        range(8),
        task=task,
        max_concurrency=4,
        on_completed=lambda outcomes: received.extend(
            (outcome.item, outcome.error is not None) for outcome in outcomes
        ),
        canary=False,
        fail_fast=False,
    )

    assert summary.completed == 8
    assert sorted(received) == [
        (0, False),
        (1, False),
        (2, False),
        (3, True),
        (4, False),
        (5, False),
        (6, False),
        (7, False),
    ]
