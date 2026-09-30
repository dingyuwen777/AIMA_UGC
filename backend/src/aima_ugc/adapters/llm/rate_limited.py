"""LLM Provider 的线程安全物理请求 RPS 限流包装层。"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Lock

from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMPort,
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
    ensure_labeling_running,
)


class RateLimitedContentLabelingLLM:
    """按固定间隔预约物理 HTTP Attempt 起始时刻，避免并发 Retry 形成请求风暴。"""

    def __init__(
        self,
        *,
        inner: ContentLabelingLLMPort,
        max_rps: int | None = None,
        current_rps: Callable[[], float | None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """创建一个无 burst 的线程安全 RPS 限流器。"""

        if current_rps is None and (
            isinstance(max_rps, bool) or not isinstance(max_rps, int) or max_rps <= 0
        ):
            raise ValueError("LLM max_rps 必须是大于 0 的整数")
        self._inner = inner
        self._interval_seconds = 1.0 / max_rps if max_rps is not None else 0.0
        self._current_rps = current_rps
        self._last_sent: float | None = None
        self._clock = clock
        self._sleep = sleep
        self._lock = Lock()
        self._next_slot = 0.0
        self._wait_seconds = 0.0

    @property
    def provider_name(self) -> str:
        """透传底层 Provider 身份。"""

        return self._inner.provider_name

    @property
    def model_name(self) -> str:
        """透传底层模型身份。"""

        return self._inner.model_name

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """取得一个物理请求时隙后再调用底层 Adapter。"""

        ensure_labeling_running(request.stop_event)
        self._wait_for_slot(request.stop_event)
        ensure_labeling_running(request.stop_event)
        return self._inner.complete(request)

    def request_metrics(self) -> dict[str, int]:
        """限流等待是本地策略开销，与模型 HTTP 累计耗时单独统计。"""

        with self._lock:
            return {"rate_wait_ms": round(self._wait_seconds * 1000)}

    def _wait_for_slot(self, stop_event: Event | None) -> None:
        """原子预约下一个请求起始时刻，并在锁外等待以允许其他线程继续预约。"""

        if self._current_rps is not None:
            self._wait_dynamic_slot(stop_event)
            return
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval_seconds
            delay = max(slot - now, 0.0)
        if delay > 0:
            before = self._clock()
            if stop_event is None:
                self._sleep(delay)
            else:
                stop_event.wait(delay)
            with self._lock:
                self._wait_seconds += self._clock() - before

    def _wait_dynamic_slot(self, stop_event: Event | None) -> None:
        """动态速率只在真正发送时占位；短等待后重读，不保留旧速率的远期预约。"""

        assert self._current_rps is not None
        while True:
            ensure_labeling_running(stop_event)
            with self._lock:
                rate = self._current_rps()
                now = self._clock()
                if rate is None:
                    self._last_sent = now
                    return
                if rate < 0:
                    raise ValueError("动态 RPS 不能为负数")
                delay = 0.1 if rate == 0 else max(0.0, (self._last_sent or 0.0) + 1.0 / rate - now)
                if rate > 0 and (self._last_sent is None or delay == 0):
                    self._last_sent = now
                    return
            before = self._clock()
            if stop_event is None:
                self._sleep(min(delay, 0.1))
            else:
                stop_event.wait(min(delay, 0.1))
            with self._lock:
                self._wait_seconds += self._clock() - before


__all__ = ["RateLimitedContentLabelingLLM"]
