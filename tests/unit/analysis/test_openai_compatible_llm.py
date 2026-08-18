from __future__ import annotations

import json

import httpx
import pytest
from aima_ugc.adapters.llm.openai_compatible import (
    OpenAICompatibleContentLabelingLLM,
    OpenAICompatibleLLMError,
)
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
        base_url="https://llm.example/v1/",
        transport=httpx.MockTransport(handler),
    )
    try:
        adapter = OpenAICompatibleContentLabelingLLM(
            base_url="https://llm.example/v1",
            api_key=SecretStr("super-secret-key"),
            model="model-a",
            provider_name="provider-a",
            client=client,
            use_json_mode=True,
        )
        response = adapter.complete(_request())
    finally:
        client.close()

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
