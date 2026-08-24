from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from aima_ugc.adapters.llm import openai_compatible as openai_compatible_module
from aima_ugc.adapters.llm import pricing as pricing_module
from aima_ugc.adapters.llm.openai_compatible import OpenAICompatibleContentLabelingLLM
from aima_ugc.adapters.llm.pricing import LLMPricingCatalog, load_llm_pricing
from aima_ugc.adapters.llm.request_audit import (
    LLMRequestAuditWriter,
    recalculate_llm_request_costs,
)
from aima_ugc.modules.analysis.content_labeling import ContentLabelingLLMRequest
from pydantic import SecretStr


def _response() -> httpx.Response:
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


def _fixed_datetime(at: datetime) -> type[datetime]:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return at

    return FixedDateTime


def test_request_audit_writer_persists_exact_cost_and_summarizes_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        openai_compatible_module,
        "datetime",
        _fixed_datetime(datetime(2026, 8, 20, 0, 0, tzinfo=UTC)),
    )
    audit_path = tmp_path / "analysis" / "llm_requests.jsonl"
    client = httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(lambda _: _response()),
    )
    writer = LLMRequestAuditWriter(audit_path)
    try:
        with writer:
            adapter = OpenAICompatibleContentLabelingLLM(
                api_key=SecretStr("secret"),
                model="deepseek-v4-pro",
                client=client,
                pricing_catalog=load_llm_pricing(),
                request_audit=writer.record,
            )
            adapter.complete(ContentLabelingLLMRequest(prompt="prompt", items=()))
    finally:
        client.close()

    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "llm-http-request.v1"
    assert payload["usage"] == {
        "input_tokens": 31,
        "input_cache_hit_tokens": 20,
        "input_cache_miss_tokens": 11,
        "output_tokens": 17,
    }
    assert payload["pricing"]["input_cache_hit_per_million"] == "0.025"
    assert payload["pricing"]["input_cache_miss_per_million"] == "3"
    assert payload["pricing"]["output_per_million"] == "6"
    assert payload["cost"] == {"amount": "0.0001355", "currency": "CNY"}
    assert writer.summary.request_count == 1
    assert writer.session_request_count == 1
    assert writer.summary.calculated_request_count == 1
    assert writer.summary.uncalculated_request_count == 0
    assert writer.summary.total_cost_amount == Decimal("0.0001355")
    assert writer.summary.cost_currency == "CNY"


def test_recalculation_writes_derived_report_without_overwriting_original_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    peak_request_at = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    monkeypatch.setattr(
        openai_compatible_module,
        "datetime",
        _fixed_datetime(peak_request_at),
    )
    monkeypatch.setattr(
        pricing_module,
        "datetime",
        _fixed_datetime(datetime(2026, 8, 20, 0, 0, tzinfo=UTC)),
    )
    audit_path = tmp_path / "analysis" / "llm_requests.jsonl"
    original_line: str
    client = httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(lambda _: _response()),
    )
    try:
        with LLMRequestAuditWriter(audit_path) as writer:
            OpenAICompatibleContentLabelingLLM(
                api_key=SecretStr("secret"),
                model="deepseek-v4-pro",
                client=client,
                pricing_catalog=load_llm_pricing(),
                request_audit=writer.record,
            ).complete(ContentLabelingLLMRequest(prompt="prompt", items=()))
        original_line = audit_path.read_text(encoding="utf-8")
    finally:
        client.close()

    changed_catalog = LLMPricingCatalog.from_toml(
        """
        schema_version = "llm-pricing.v1"

        [[models]]
        provider = "api.deepseek.com"
        model = "deepseek-v4-pro"
        currency = "CNY"
        source_url = "https://example.invalid/hypothetical-price"
        effective_date = "2026-08-20"
        timezone = "Asia/Shanghai"

        [[models.price_periods]]
        name = "off_peak"
        input_cache_hit_per_million_tokens = "0.15"
        input_cache_miss_per_million_tokens = "4.5"
        output_per_million_tokens = "12"

        [[models.price_periods]]
        name = "peak"
        time_ranges = ["09:00-12:00", "14:00-18:00"]
        input_cache_hit_per_million_tokens = "0.30"
        input_cache_miss_per_million_tokens = "9"
        output_per_million_tokens = "24"
        """
    )
    report_path = tmp_path / "analysis" / "cost_recalculation.json"

    summary = recalculate_llm_request_costs(
        input_path=audit_path,
        output_path=report_path,
        pricing_catalog=changed_catalog,
    )

    assert audit_path.read_text(encoding="utf-8") == original_line
    assert summary.total_cost_amount == Decimal("0.000513")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "llm-cost-recalculation.v1"
    assert report["source_audit_sha256"]
    assert report["summary"]["total_cost_amount"] == "0.000513"
    assert report["requests"][0]["pricing"]["output_per_million"] == "24"
    assert report["summary"]["cost_currency"] == "CNY"


def test_request_audit_resume_distinguishes_current_session_from_run_total(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        openai_compatible_module,
        "datetime",
        _fixed_datetime(datetime(2026, 8, 20, 0, 0, tzinfo=UTC)),
    )
    audit_path = tmp_path / "analysis" / "llm_requests.jsonl"
    client = httpx.Client(
        base_url="https://api.deepseek.com/",
        transport=httpx.MockTransport(lambda _: _response()),
    )
    try:
        for expected_total in (1, 2):
            with LLMRequestAuditWriter(audit_path) as writer:
                OpenAICompatibleContentLabelingLLM(
                    api_key=SecretStr("secret"),
                    model="deepseek-v4-pro",
                    client=client,
                    pricing_catalog=load_llm_pricing(),
                    request_audit=writer.record,
                ).complete(ContentLabelingLLMRequest(prompt="prompt", items=()))
            assert writer.session_request_count == 1
            assert writer.summary.request_count == expected_total
    finally:
        client.close()
