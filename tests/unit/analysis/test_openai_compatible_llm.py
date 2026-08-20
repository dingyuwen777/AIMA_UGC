from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from aima_ugc.adapters.llm import RetryingContentLabelingLLM
from aima_ugc.adapters.llm import openai_compatible as openai_compatible_module
from aima_ugc.adapters.llm import pricing as pricing_module
from aima_ugc.adapters.llm.openai_compatible import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
)
from aima_ugc.adapters.llm.pricing import load_llm_pricing
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMRequest,
    ContentLabelingModelItem,
)
from pydantic import SecretStr


def _request(*, previous_errors: tuple[str, ...] = ()) -> ContentLabelingLLMRequest:
    return ContentLabelingLLMRequest(
        prompt="PROMPT-TEXT",
        items=(
            ContentLabelingModelItem(
                item_no=1,
                title="爱玛标题",
                text="正文",
                author_display_name="作者",
            ),
        ),
        previous_validation_error_codes=previous_errors,
    )


def test_openai_compatible_adapter_sends_one_minimal_chat_completion_request() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"items":[{"item_no":1,"sentiment":"中性",'
                            '"primary_label":"一级","secondary_label":"二级"}]}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 31, "completion_tokens": 17},
            },
        )

    client = httpx.Client(
        base_url="https://LLM.Example/v1/",
        transport=httpx.MockTransport(handler),
    )
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            base_url="https://llm.example/v1",
            api_key=SecretStr("super-secret-key"),
            model="model-a",
            client=client,
        )
        response = adapter.complete(_request())
    finally:
        client.close()

    assert adapter.provider_name == "llm.example"
    assert len(captured) == 1
    sent = captured[0]
    assert sent.method == "POST"
    assert str(sent.url) == "https://llm.example/v1/chat/completions"
    assert sent.headers["authorization"] == "Bearer super-secret-key"
    body = json.loads(sent.content)
    assert body["model"] == "model-a"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0] == {"role": "system", "content": "PROMPT-TEXT"}
    user_payload = json.loads(body["messages"][1]["content"])
    assert user_payload == {
        "items": [
            {
                "item_no": 1,
                "title": "爱玛标题",
                "text": "正文",
                "author": {"display_name": "作者"},
            }
        ]
    }
    assert response.input_tokens == 31
    assert response.output_tokens == 17
    assert response.cost_amount is None
    assert response.cost_currency is None


def test_openai_compatible_adapter_derives_non_default_port_in_provider_identity() -> None:
    client = httpx.Client(
        base_url="https://gateway.example:8443/v1/",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("secret"),
            model="model-a",
            client=client,
        )
    finally:
        client.close()

    assert adapter.provider_name == "gateway.example:8443"


def test_openai_compatible_adapter_retry_request_only_adds_validation_errors() -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"items":[]}'}}]},
        )

    client = httpx.Client(
        base_url="https://llm.example/v1/",
        transport=httpx.MockTransport(handler),
    )
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            base_url="https://llm.example/v1",
            api_key=SecretStr("secret"),
            model="model-a",
            provider_name="provider-a",
            client=client,
            use_json_mode=False,
        )
        adapter.complete(_request(previous_errors=("unknown_sentiment", "missing_item")))
    finally:
        client.close()

    assert adapter.provider_name == "provider-a"
    assert "response_format" not in captured_body
    user_payload = json.loads(captured_body["messages"][1]["content"])
    assert user_payload["items"] == _request().model_payload()
    assert user_payload["previous_validation_error_codes"] == [
        "unknown_sentiment",
        "missing_item",
    ]
    assert set(user_payload) == {
        "items",
        "previous_validation_error_codes",
        "retry_instruction",
    }


def test_openai_compatible_adapter_does_not_hide_transport_retry_or_response_body() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, text="sensitive-provider-body")

    client = httpx.Client(
        base_url="https://llm.example/v1/",
        transport=httpx.MockTransport(handler),
    )
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            base_url="https://llm.example/v1",
            api_key=SecretStr("secret"),
            model="model-a",
            provider_name="provider-a",
            client=client,
        )
        with pytest.raises(OpenAICompatibleLLMError) as exc_info:
            adapter.complete(_request())
    finally:
        client.close()

    assert calls == 1
    assert "HTTP 500" in str(exc_info.value)
    assert "sensitive-provider-body" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


@pytest.mark.parametrize("empty_content", [None, "", " \n\t"])
def test_openai_compatible_empty_content_uses_explicit_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
    empty_content: str | None,
) -> None:
    calls = 0
    valid_content = '{"items":[]}'

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = empty_content if calls == 1 else valid_content
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = httpx.Client(
        base_url="https://llm.example/v1/",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", lambda _: None)
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("secret"),
            model="model-a",
            client=client,
        )
        retrying = RetryingContentLabelingLLM(inner=adapter, max_retries=1)

        response = retrying.complete(_request())
    finally:
        client.close()

    assert response.raw_text == valid_content
    assert calls == 2
    assert retrying.total_requests == 2
    assert retrying.total_retries == 1


def test_openai_compatible_uses_physical_request_start_time_for_price_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[LLMHTTPRequestAudit] = []

    class IdleCatalogDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 8, 20, 0, 0, tzinfo=UTC)

    class PeakRequestDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 8, 20, 1, 0, tzinfo=UTC)

    monkeypatch.setattr(pricing_module, "datetime", IdleCatalogDateTime)
    monkeypatch.setattr(openai_compatible_module, "datetime", PeakRequestDateTime)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"items":[]}'}}],
                "usage": {
                    "prompt_tokens": 31,
                    "prompt_cache_hit_tokens": 20,
                    "prompt_cache_miss_tokens": 11,
                    "completion_tokens": 17,
                    "total_tokens": 48,
                },
            },
        )

    client = httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(handler),
    )
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("secret"),
            model="deepseek-v4-pro",
            client=client,
            pricing_catalog=load_llm_pricing(),
            request_audit=records.append,
        )
        response = adapter.complete(_request())
    finally:
        client.close()

    assert response.input_tokens == 31
    assert response.input_cache_hit_tokens == 20
    assert response.input_cache_miss_tokens == 11
    assert response.output_tokens == 17
    assert response.cost_amount == Decimal("0.000564")
    assert response.cost_currency == "CNY"
    assert len(records) == 1
    assert records[0].status == "completed"
    assert records[0].started_at == datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    assert records[0].cost_amount == Decimal("0.000564")
    assert records[0].cost_currency == "CNY"
    assert records[0].input_cache_hit_per_million == Decimal("0.30")
    assert records[0].input_cache_miss_per_million == Decimal("9.0")
    assert records[0].output_per_million == Decimal("27.0")
    assert records[0].pricing_source_url.endswith("/quick_start/pricing/")


def test_empty_content_retry_audits_cost_of_every_paid_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[LLMHTTPRequestAudit] = []
    calls = 0

    class IdleRequestDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 8, 20, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(openai_compatible_module, "datetime", IdleRequestDateTime)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "" if calls == 1 else '{"items":[]}'}}],
                "usage": {
                    "prompt_tokens": 10,
                    "prompt_cache_hit_tokens": 8,
                    "prompt_cache_miss_tokens": 2,
                    "completion_tokens": calls,
                    "total_tokens": 10 + calls,
                },
            },
        )

    client = httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("aima_ugc.adapters.llm.retrying.time.sleep", lambda _: None)
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("secret"),
            model="deepseek-v4-pro",
            client=client,
            pricing_catalog=load_llm_pricing(),
            request_audit=records.append,
        )
        retrying = RetryingContentLabelingLLM(inner=adapter, max_retries=1)
        response = retrying.complete(_request())
    finally:
        client.close()

    assert response.raw_text == '{"items":[]}'
    assert [record.status for record in records] == ["protocol_error", "completed"]
    assert records[0].logical_request_id == records[1].logical_request_id
    assert records[0].http_request_id != records[1].http_request_id
    assert sum(record.cost_amount or Decimal("0") for record in records) == Decimal("0.0000609")
