"""LLM 物理请求 RPS 限流与 Transport Retry 组合回归。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from aima_ugc.adapters.llm.openai_compatible import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
)
from aima_ugc.adapters.llm.rate_limited import RateLimitedContentLabelingLLM
from aima_ugc.adapters.llm.retrying import RetryingContentLabelingLLM
from aima_ugc.bootstrap.analysis_capacity import AnalysisCapacityFeedback
from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
    ContentLabelingStopped,
)
from aima_ugc.modules.system.models import ProviderConfig
from pydantic import SecretStr


def _capacity():
    """只构造本地反馈，不连接数据库或创建外部请求。"""
    provider = ProviderConfig(
        id=uuid4(),
        provider="test",
        display_name="测试",
        provider_kind="llm",
        base_url="https://example.invalid",
        secret_ref="providers/test/key-1.key",
        enabled=True,
        model="test",
    )
    capacity = AnalysisCapacityFeedback(
        SimpleNamespace(), provider=provider, prompt_sha256="a" * 64, run_id=uuid4()
    )
    return provider, capacity


def test_rate_and_concurrency_gate_do_not_accumulate_expired_send_slots():
    """长请求排空后，快请求仍按实际发送时间限速，而非突发发送。"""
    provider, capacity = _capacity()
    capacity.target = 1
    capacity.rps = 5
    sends = []

    def respond(request):
        """首个物理请求占满许可，后续响应立即完成，不访问外部服务。"""
        sends.append(monotonic())
        if len(sends) == 1:
            sleep(0.3)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    with httpx.Client(base_url=provider.base_url, transport=httpx.MockTransport(respond)) as client:
        adapter = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("fake"),
            model="test",
            client=client,
            before_request=capacity.admit,
            on_request_finished=capacity.finished,
            request_audit=capacity.audit,
        )
        capacity.rate_limiter = RateLimitedContentLabelingLLM(
            inner=adapter, current_rps=lambda: capacity.rps
        )
        request = ContentLabelingLLMRequest(prompt="test", items=())
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: adapter.complete(request), range(3)))
    assert len(sends) == 3
    assert sends[1] - sends[0] >= 0.29
    assert sends[2] - sends[1] >= 0.19
    assert capacity._meter.peak == 1 and capacity._meter.active == 0
    assert capacity.rate_limiter.request_metrics()["rate_wait_ms"] > 0


@pytest.mark.parametrize("blocked_by", ["concurrency", "rate"])
def test_combined_gate_wait_is_cancellable_without_consuming_physical_or_rate_slot(blocked_by):
    """两类许可等待都可取消，尚未发送的请求不能占据物理或速率时隙。"""
    _provider, capacity = _capacity()
    capacity.target = 0 if blocked_by == "concurrency" else 1
    capacity.rps = None if blocked_by == "concurrency" else 0
    capacity.rate_limiter = RateLimitedContentLabelingLLM(
        inner=SimpleNamespace(), current_rps=lambda: capacity.rps
    )
    entered = Event()
    stop = Event()

    def wait_for_admission():
        """标记准入等待开始，使取消发生于实际等待中。"""
        entered.set()
        capacity.admit(stop)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(wait_for_admission)
        assert entered.wait(1)
        sleep(0.15)
        assert not future.done()
        stop.set()
        with pytest.raises(ContentLabelingStopped):
            future.result(timeout=1)
    assert capacity._meter.active == 0 and capacity._delta["started"] == 0
    assert capacity.rate_limiter._last_sent is None


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


def test_dynamic_rps_rechecks_after_drop_without_old_reservations(monkeypatch) -> None:
    clock = _FakeClock()
    base = _FlakyLLM(clock)
    rate = 10.0

    def sleep(seconds: float) -> None:
        nonlocal rate
        clock.sleep(seconds)
        rate = 1.0

    limited = RateLimitedContentLabelingLLM(
        inner=base, current_rps=lambda: rate, clock=clock.monotonic, sleep=sleep
    )
    retrying = RetryingContentLabelingLLM(inner=limited, max_retries=2)
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", lambda _: None)
    retrying.complete(ContentLabelingLLMRequest(prompt="test", items=()))
    assert base.started_at[0] == 0
    assert base.started_at[1] >= 1.0
    assert base.started_at[2] - base.started_at[1] >= 1.0


def test_fractional_send_rate_keeps_physical_interval_without_minimum_floor(monkeypatch):
    """共享小数份额不人为抬高发送率，虚拟时间覆盖长间隔而不真实等待。"""
    clock = _FakeClock()
    base = _FlakyLLM(clock)
    limited = RateLimitedContentLabelingLLM(
        inner=base, current_rps=lambda: 0.04, clock=clock.monotonic, sleep=clock.sleep
    )
    retrying = RetryingContentLabelingLLM(inner=limited, max_retries=2)
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", lambda _: None)
    retrying.complete(ContentLabelingLLMRequest(prompt="test", items=()))
    assert base.started_at == pytest.approx([0.0, 25.0, 50.0], abs=1e-10)


def test_long_fractional_rate_interval_can_be_cancelled_before_next_send():
    """长发送间隔继续短轮询取消，不占物理槽位或预消费新时隙。"""
    _provider, capacity = _capacity()
    capacity.target, capacity.rps = 1, 0.04
    capacity.rate_limiter = RateLimitedContentLabelingLLM(
        inner=SimpleNamespace(), current_rps=lambda: capacity.rps
    )
    assert capacity.rate_limiter.try_acquire_slot() == 0
    previous = capacity.rate_limiter._last_sent
    entered, stop = Event(), Event()

    def wait_for_admission():
        """明确进入准入循环之后测试短轮询取消。"""
        entered.set()
        capacity.admit(stop)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(wait_for_admission)
        assert entered.wait(1)
        sleep(0.15)
        assert not future.done()
        stop.set()
        with pytest.raises(ContentLabelingStopped):
            future.result(timeout=1)
    assert capacity._meter.active == 0 and capacity._delta["started"] == 0
    assert capacity.rate_limiter._last_sent == previous
