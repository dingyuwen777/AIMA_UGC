"""LLM 物理请求 RPS 限流与 Transport Retry 组合回归。"""

from __future__ import annotations

from aima_ugc.adapters.llm.openai_compatible import OpenAICompatibleLLMError
from aima_ugc.adapters.llm.rate_limited import RateLimitedContentLabelingLLM
from aima_ugc.adapters.llm.retrying import RetryingContentLabelingLLM
from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
)


class _FakeClock:
    """由测试显式推进的单调时钟。"""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        """返回当前虚拟单调时间。"""

        return self.now

    def sleep(self, seconds: float) -> None:
        """记录并推进限流等待时间，不做真实阻塞。"""

        self.sleeps.append(seconds)
        self.now += seconds


class _FlakyLLM:
    """前两次物理 Attempt 返回可重试错误，第三次成功。"""

    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, clock: _FakeClock) -> None:
        self.clock = clock
        self.started_at: list[float] = []

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """记录物理 Attempt 起始时间并按次数返回错误或成功。"""

        del request
        self.started_at.append(self.clock.monotonic())
        if len(self.started_at) < 3:
            raise OpenAICompatibleLLMError(
                "temporary",
                error_code="http_429",
                retryable=True,
                status_code=429,
            )
        return ContentLabelingLLMResponse(raw_text='{"items":[]}')


def test_rate_limit_applies_to_every_transport_retry(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Retry wrapper 的每次物理 Attempt 都必须重新取得 RPS 时隙。"""

    clock = _FakeClock()
    base = _FlakyLLM(clock)
    limited = RateLimitedContentLabelingLLM(
        inner=base,
        max_rps=2,
        clock=clock.monotonic,
        sleep=clock.sleep,
    )
    retrying = RetryingContentLabelingLLM(inner=limited, max_retries=2)
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", lambda _seconds: None)

    retrying.complete(ContentLabelingLLMRequest(prompt="test", items=()))

    assert base.started_at == [0.0, 0.5, 1.0]
    assert retrying.total_requests == 3
    assert retrying.total_retries == 2
