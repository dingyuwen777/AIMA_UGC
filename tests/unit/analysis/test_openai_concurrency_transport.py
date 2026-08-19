from __future__ import annotations

import httpx
import pytest
from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
)
from aima_ugc.modules.analysis import ContentLabelingLLMRequest
from pydantic import SecretStr


def _request() -> ContentLabelingLLMRequest:
    return ContentLabelingLLMRequest(prompt="prompt", items=())


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [
        (429, True),
        (503, True),
        (401, False),
        (402, False),
        (422, False),
    ],
)
def test_openai_compatible_classifies_transport_status(
    status_code: int,
    retryable: bool,
) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, request=request))
    with httpx.Client(base_url="https://api.deepseek.com/", transport=transport) as client:
        llm = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("dummy-key"),
            model="model-a",
            client=client,
        )
        with pytest.raises(OpenAICompatibleLLMError) as exc_info:
            llm.complete(_request())

    assert exc_info.value.status_code == status_code
    assert exc_info.value.retryable is retryable
    assert exc_info.value.error_code == f"http_{status_code}"


def test_openai_compatible_builds_connection_pool_at_requested_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr("aima_ugc.adapters.llm.openai_compatible.httpx.Client", DummyClient)
    llm = OpenAICompatibleContentLabelingLLM(
        api_key=SecretStr("dummy-key"),
        model="model-a",
        base_url="https://api.deepseek.com",
        max_connections=250,
    )
    llm.close()

    limits = captured["limits"]
    assert isinstance(limits, httpx.Limits)
    assert limits.max_connections == 250
    assert limits.max_keepalive_connections == 250
