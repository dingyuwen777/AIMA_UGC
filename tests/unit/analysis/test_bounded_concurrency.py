"""Analysis 公共有界并发执行器回归。"""

from __future__ import annotations

from threading import Event, Lock

import pytest
from aima_ugc.modules.analysis.concurrent_labeling import run_bounded_concurrently


def test_two_items_start_together_without_waiting_for_first_result() -> None:
    """两条内容必须在第一条完成前同时进入执行，避免少量任务退化成串行。"""

    release = Event()
    lock = Lock()
    started: list[int] = []

    def task(value: int) -> int:
        """只有两条请求都已进入才解除屏障。"""

        with lock:
            started.append(value)
            if len(started) == 2:
                release.set()
        assert release.wait(0.5), "第二条请求未能在第一条完成前开始"
        return value

    summary = run_bounded_concurrently(
        range(2),
        task=task,
        max_concurrency=10,
        on_completed=lambda outcomes: None,
    )
    assert summary.completed == 2
    assert summary.peak_in_flight == 2


def test_scheduler_checks_stop_while_all_requests_are_waiting() -> None:
    """没有完成结果时也必须执行控制检查，取消不能等待模型返回。"""

    entered = Event()
    release = Event()
    stop = Event()
    called: list[int] = []

    def task(value: int) -> int:
        """模拟等待远端响应的唯一在途请求。"""

        called.append(value)
        entered.set()
        assert release.wait(2)
        return value

    def tick() -> None:
        """模型仍在等待时发出停止信号，并让测试请求收敛。"""

        if entered.is_set():
            stop.set()
            release.set()

    summary = run_bounded_concurrently(
        range(3),
        task=task,
        max_concurrency=1,
        on_completed=lambda outcomes: None,
        stop_requested=stop.is_set,
        on_tick=tick,
    )
    assert summary.stopped
    assert 1 <= len(called) <= 50
    assert all(value < 50 for value in called)


@pytest.mark.parametrize("max_concurrency", [20, 250])
def test_bounded_executor_reaches_and_never_exceeds_configured_concurrency(
    max_concurrency: int,
) -> None:
    """真实线程执行时峰值在途必须达到且不超过配置上限，覆盖 DeepSeek 250 档。"""

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
        assert release.wait(timeout=10)
        with lock:
            active -= 1
        return value * 2

    summary = run_bounded_concurrently(
        range(max_concurrency * 2),
        task=task,
        max_concurrency=max_concurrency,
        on_completed=lambda outcomes: completed.extend(
            outcome.result for outcome in outcomes if outcome.result is not None
        ),
        fail_fast=True,
    )

    assert peak == max_concurrency
    assert summary.peak_in_flight == max_concurrency
    assert summary.completed == max_concurrency * 2
    assert sorted(completed) == [value * 2 for value in range(max_concurrency * 2)]


def test_bounded_executor_supports_1000_configured_in_flight() -> None:
    """1000 档只提交一个有界窗口，不需要把整个输入预先塞进线程池队列。"""

    completed: list[int] = []
    summary = run_bounded_concurrently(
        range(1_000),
        task=lambda value: value,
        max_concurrency=1_000,
        on_completed=lambda outcomes: completed.extend(
            outcome.result for outcome in outcomes if outcome.result is not None
        ),
        fail_fast=True,
    )

    assert summary.peak_in_flight == 1_000
    assert summary.completed == 1_000
    assert len(completed) == 1_000


def test_bounded_executor_failure_stops_refilling() -> None:
    """初始窗口发生错误后不得继续补充剩余请求。"""

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
            fail_fast=True,
        )

    assert 1 <= len(called) <= 50
    assert all(value < 50 for value in called)


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


def test_bounded_executor_stops_refilling_after_cancel_signal() -> None:
    """完成回调观察到取消后不得继续从输入迭代器补提交新的请求。"""

    called: list[int] = []
    stop = False

    def task(value: int) -> int:
        called.append(value)
        return value

    def on_completed(_outcomes: object) -> None:
        nonlocal stop
        stop = True

    summary = run_bounded_concurrently(
        range(100),
        task=task,
        max_concurrency=4,
        on_completed=on_completed,
        fail_fast=False,
        stop_requested=lambda: stop,
    )

    assert summary.stopped is True
    assert summary.peak_in_flight == 4
    assert 1 <= summary.completed <= 4
    assert summary.completed == len(called)
    assert set(called).issubset({0, 1, 2, 3})
