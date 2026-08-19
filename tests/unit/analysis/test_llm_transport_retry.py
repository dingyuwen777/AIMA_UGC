from __future__ import annotations

import pytest
from aima_ugc.adapters.llm import (
    OpenAICompatibleLLMError,
    RetryingContentLabelingLLM,
)
from aima_ugc.modules.analysis import ContentLabelingLLMRequest, ContentLabelingLLMResponse


class _InnerLLM:
    def __init__(self, outcomes) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "provider"

    @property
    def model_name(self) -> str:
        return "model"

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _request() -> ContentLabelingLLMRequest:
    return ContentLabelingLLMRequest(prompt="prompt", items=())


def _transient(status_code: int = 503) -> OpenAICompatibleLLMError:
    return OpenAICompatibleLLMError(
        f"HTTP {status_code}",
        error_code=f"http_{status_code}",
        retryable=True,
        status_code=status_code,
    )


def _fatal(status_code: int = 401) -> OpenAICompatibleLLMError:
    return OpenAICompatibleLLMError(
        f"HTTP {status_code}",
        error_code=f"http_{status_code}",
        retryable=False,
        status_code=status_code,
    )


def test_transport_retry_retries_transient_failure_without_becoming_validation_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = _InnerLLM(
        [
            _transient(503),
            _transient(429),
            ContentLabelingLLMResponse(raw_text='{"items":[]}'),
        ]
    )
    wrapper = RetryingContentLabelingLLM(inner=inner, max_retries=4)
    sleeps: list[float] = []
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", sleeps.append)
    monkeypatch.setattr(
        "aima_ugc.adapters.llm.retrying._retry_delay_seconds",
        lambda attempt: float(attempt),
    )

    response = wrapper.complete(_request())

    assert response.raw_text == '{"items":[]}'
    assert inner.calls == 3
    assert wrapper.total_requests == 3
    assert wrapper.total_retries == 2
    assert sleeps == [1.0, 2.0]


def test_transport_retry_fails_fast_for_nonretryable_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = _InnerLLM([_fatal(401)])
    wrapper = RetryingContentLabelingLLM(inner=inner, max_retries=4)
    monkeypatch.setattr(
        "aima_ugc.adapters.llm.retrying.time.sleep",
        lambda _: pytest.fail("401 不得进入 Transport Retry sleep"),
    )

    with pytest.raises(OpenAICompatibleLLMError) as exc_info:
        wrapper.complete(_request())

    assert exc_info.value.status_code == 401
    assert inner.calls == 1
    assert wrapper.total_requests == 1
    assert wrapper.total_retries == 0


def test_transport_retry_stops_after_configured_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = _InnerLLM([_transient()] * 3)
    wrapper = RetryingContentLabelingLLM(inner=inner, max_retries=2)
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", lambda _: None)

    with pytest.raises(OpenAICompatibleLLMError):
        wrapper.complete(_request())

    assert inner.calls == 3
    assert wrapper.total_requests == 3
    assert wrapper.total_retries == 2
