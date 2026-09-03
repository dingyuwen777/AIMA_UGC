"""LLM Provider 的线程安全物理请求 RPS 限流包装层。"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMPort,
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
)


class RateLimitedContentLabelingLLM:
    """按固定间隔预约物理 HTTP Attempt 起始时刻，避免并发 Retry 形成请求风暴。"""

    def __init__(
        self,
        *,
        inner: ContentLabelingLLMPort,
        max_rps: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """创建一个无 burst 的线程安全 RPS 限流器。"""

        if isinstance(max_rps, bool) or not isinstance(max_rps, int) or max_rps <= 0:
            raise ValueError("LLM max_rps 必须是大于 0 的整数")
        self._inner = inner
        self._interval_seconds = 1.0 / max_rps
        self._clock = clock
        self._sleep = sleep
        self._lock = Lock()
        self._next_slot = 0.0

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

        self._wait_for_slot()
        return self._inner.complete(request)

    def _wait_for_slot(self) -> None:
        """原子预约下一个请求起始时刻，并在锁外等待以允许其他线程继续预约。"""

        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval_seconds
            delay = max(slot - now, 0.0)
        if delay > 0:
            self._sleep(delay)


__all__ = ["RateLimitedContentLabelingLLM"]
