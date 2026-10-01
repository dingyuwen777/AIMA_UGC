from __future__ import annotations

import httpx
import pytest
from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
)
from aima_ugc.adapters.llm import openai_compatible as adapter_module
from aima_ugc.modules.analysis import ContentLabelingLLMRequest
from aima_ugc.platform.time import BEIJING_TIMEZONE
from pydantic import SecretStr


def _request() -> ContentLabelingLLMRequest:
    return ContentLabelingLLMRequest(prompt="prompt", items=())


@pytest.mark.parametrize(
    "header,expected",
    [
        ("x-ratelimit-remaining-requests", "request_rate"),
        ("x-ratelimit-remaining-tokens", "token_rate"),
    ],
)
def test_explicit_429_quota_overrides_declared_model_concurrency(header, expected):
    """官方并发额度只是缺省提示，明确配额反馈不能被模型名称覆盖。"""
    audits = []
    with httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={header: "0"}, request=request)
        ),
    ) as client:
        llm = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("fake"),
            model="deepseek-flash",
            client=client,
            request_audit=audits.append,
        )
        with pytest.raises(OpenAICompatibleLLMError):
            llm.complete(_request())
    assert audits[0].rate_limit_kind == expected


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


@pytest.mark.parametrize(
    "error_type,code",
    [
        (httpx.ReadTimeout, "timeout"),
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ConnectError, "network_error"),
    ],
)
def test_timeout_and_transport_have_separate_physical_audit_codes(error_type, code) -> None:
    audits = []

    def fail(request):
        raise error_type("fake", request=request)

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(fail)
    ) as client:
        llm = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("fake"), model="test", client=client, request_audit=audits.append
        )
        with pytest.raises(OpenAICompatibleLLMError) as error:
            llm.complete(_request())
    assert error.value.error_code == code
    assert error.value.retryable
    assert len(audits) == 1 and audits[0].error_code == code


def test_request_audit_excludes_local_admission_wait(monkeypatch) -> None:
    """本地许可等待不能写成模型 HTTP 延迟。"""
    from datetime import datetime, timedelta

    base = datetime(2026, 10, 1, tzinfo=BEIJING_TIMEZONE)
    elapsed = [0]
    audits = []
    monkeypatch.setattr(adapter_module, "beijing_now", lambda: base + timedelta(seconds=elapsed[0]))

    def admit(_stop):
        """模拟本地等待，保持请求阶段尚未开始。"""
        elapsed[0] = 10

    def respond(request):
        """仅让 HTTP 阶段耗时两秒，不发出外部网络调用。"""
        elapsed[0] = 12
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(respond)
    ) as client:
        llm = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("fake"),
            model="test",
            client=client,
            before_request=admit,
            request_audit=audits.append,
        )
        llm.complete(_request())
    assert len(audits) == 1
    assert audits[0].started_at == base + timedelta(seconds=10)
    assert (audits[0].completed_at - audits[0].started_at).total_seconds() == 2
