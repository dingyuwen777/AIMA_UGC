from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from aima_ugc.adapters.llm import openai_compatible as openai_compatible_module
from aima_ugc.adapters.llm.openai_compatible import OpenAICompatibleContentLabelingLLM
from aima_ugc.adapters.llm.pricing import LLMPriceNotConfiguredError, load_llm_pricing
from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.modules.analysis.content_labeling import ContentLabelingLLMRequest
from pydantic import SecretStr


def test_deepseek_current_price_is_not_available_before_effective_date() -> None:
    catalog = load_llm_pricing()

    with pytest.raises(LLMPriceNotConfiguredError, match="尚未生效"):
        catalog.price_for(
            provider="api.deepseek.com",
            model="deepseek-v4-pro",
            at=datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC),
        )


def test_llm_request_continues_when_price_is_not_effective_yet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[LLMHTTPRequestAudit] = []

    class BeforeEffectiveDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC)

    monkeypatch.setattr(openai_compatible_module, "datetime", BeforeEffectiveDateTime)

    client = httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
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
        ),
    )
    try:
        response = OpenAICompatibleContentLabelingLLM(
            api_key=SecretStr("secret"),
            model="deepseek-v4-pro",
            client=client,
            pricing_catalog=load_llm_pricing(),
            request_audit=records.append,
        ).complete(ContentLabelingLLMRequest(prompt="prompt", items=()))
    finally:
        client.close()

    assert response.raw_text == '{"items":[]}'
    assert response.cost_amount is None
    assert response.cost_currency is None
    assert response.pricing_source_url is None
    assert len(records) == 1
    assert records[0].status == "completed"
    assert records[0].cost_amount is None
    assert records[0].cost_unavailable_reason == "price_not_effective_at_request_time"
