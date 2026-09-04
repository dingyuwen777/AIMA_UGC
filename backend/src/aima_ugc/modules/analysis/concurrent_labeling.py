"""Analysis Offline/Formal 共用的有界线程并发调度器。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConcurrentTaskOutcome[ItemT, ResultT]:
    """一条已提交任务的成功结果或异常。"""

    item: ItemT
    result: ResultT | None = None
    error: BaseException | None = None

    def __post_init__(self) -> None:
        """保证一个 Outcome 不能同时携带结果和异常。"""

        if self.result is not None and self.error is not None:
            raise ValueError("ConcurrentTaskOutcome 不能同时包含 result 和 error")


@dataclass(frozen=True, slots=True)
class BoundedConcurrencySummary:
    """一次有界并发执行的调度摘要。"""

    completed: int
    peak_in_flight: int
    stopped: bool


def run_bounded_concurrently[ItemT, ResultT](
    items: Iterable[ItemT],
    *,
    task: Callable[[ItemT], ResultT],
    max_concurrency: int,
    on_completed: Callable[[tuple[ConcurrentTaskOutcome[ItemT, ResultT], ...]], None],
    canary: bool = True,
    fail_fast: bool = True,
    stop_requested: Callable[[], bool] | None = None,
) -> BoundedConcurrencySummary:
    """先可选 Canary，再以不超过 `max_concurrency` 的线程并发执行任务。

    `on_completed` 始终在调度线程调用，因此调用方可以在回调中做短事务批量落库；
    回调变慢时调度器不会继续无界提交新任务，从而自然形成背压。
    """

    _validate_max_concurrency(max_concurrency)
    iterator = iter(items)
    completed = 0
    peak_in_flight = 0
    stopped = False

    if _should_stop(stop_requested):
        return BoundedConcurrencySummary(completed=0, peak_in_flight=0, stopped=True)

    if canary:
        first_item = next(iterator, None)
        if first_item is None:
            return BoundedConcurrencySummary(completed=0, peak_in_flight=0, stopped=False)
        first_result = task(first_item)
        on_completed((ConcurrentTaskOutcome(item=first_item, result=first_result),))
        completed = 1
        peak_in_flight = 1
        if _should_stop(stop_requested):
            return BoundedConcurrencySummary(
                completed=completed,
                peak_in_flight=peak_in_flight,
                stopped=True,
            )

    with ThreadPoolExecutor(
        max_workers=max_concurrency,
        thread_name_prefix="aima-analysis",
    ) as executor:
        in_flight: dict[Future[ResultT], ItemT] = {}
        exhausted = False

        def fill_capacity() -> None:
            """只补到并发上限，不把整个输入一次性提交进线程池队列。"""

            nonlocal exhausted, peak_in_flight, stopped
            while not exhausted and len(in_flight) < max_concurrency:
                if _should_stop(stop_requested):
                    stopped = True
                    return
                try:
                    item = next(iterator)
                except StopIteration:
                    exhausted = True
                    return
                in_flight[executor.submit(task, item)] = item
                peak_in_flight = max(peak_in_flight, len(in_flight))

        fill_capacity()
        while in_flight:
            done, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
            done.update(future for future in in_flight if future.done())
            outcomes = _collect_completed(in_flight, done)
            if outcomes:
                on_completed(outcomes)
                completed += len(outcomes)

            first_error = next(
                (outcome.error for outcome in outcomes if outcome.error is not None),
                None,
            )
            if first_error is not None and fail_fast:
                trailing = _cancel_and_collect(in_flight)
                if trailing:
                    on_completed(trailing)
                    completed += len(trailing)
                raise first_error

            if _should_stop(stop_requested):
                stopped = True
                trailing = _cancel_and_collect(in_flight)
                if trailing:
                    on_completed(trailing)
                    completed += len(trailing)
                break

            fill_capacity()

    return BoundedConcurrencySummary(
        completed=completed,
        peak_in_flight=peak_in_flight,
        stopped=stopped,
    )


def _collect_completed[ItemT, ResultT](
    in_flight: dict[Future[ResultT], ItemT],
    done: set[Future[ResultT]],
) -> tuple[ConcurrentTaskOutcome[ItemT, ResultT], ...]:
    """收割已完成 Future，并把异常保留为可由调用方解释的 Outcome。"""

    outcomes: list[ConcurrentTaskOutcome[ItemT, ResultT]] = []
    for future in done:
        item = in_flight.pop(future)
        if future.cancelled():
            continue
        try:
            outcomes.append(ConcurrentTaskOutcome(item=item, result=future.result()))
        except BaseException as exc:
            outcomes.append(ConcurrentTaskOutcome(item=item, error=exc))
    return tuple(outcomes)


def _cancel_and_collect[ItemT, ResultT](
    in_flight: dict[Future[ResultT], ItemT],
) -> tuple[ConcurrentTaskOutcome[ItemT, ResultT], ...]:
    """取消尚未开始的任务，并等待已经运行的请求收敛后统一收割。"""

    futures = tuple(in_flight)
    for future in futures:
        future.cancel()
    if futures:
        wait(futures)
    return _collect_completed(in_flight, set(futures))


def _should_stop(stop_requested: Callable[[], bool] | None) -> bool:
    """只在调用方提供停止检查时查询协作式停止状态。"""

    return bool(stop_requested is not None and stop_requested())


def _validate_max_concurrency(value: int) -> None:
    """拒绝布尔值、非整数和无界的非正并发配置。"""

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_concurrency 必须是大于 0 的整数")


__all__ = [
    "BoundedConcurrencySummary",
    "ConcurrentTaskOutcome",
    "run_bounded_concurrently",
]
