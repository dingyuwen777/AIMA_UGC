from __future__ import annotations

from decimal import Decimal

import pytest
from aima_ugc.adapters.llm.pricing import (
    LLMPriceNotConfiguredError,
    LLMPricingCatalog,
    LLMTokenUsage,
    load_llm_pricing,
)


def test_default_catalog_calculates_deepseek_v4_pro_cache_split_cost() -> None:
    catalog = load_llm_pricing()
    assert [(item.provider, item.model) for item in catalog.models] == [
        ("api.deepseek.com", "deepseek-v4-pro")
    ]
    price = catalog.price_for(provider="api.deepseek.com", model="deepseek-v4-pro")

    calculation = price.calculate(
        LLMTokenUsage(
            input_tokens=31,
            output_tokens=17,
            input_cache_hit_tokens=20,
            input_cache_miss_tokens=11,
        )
    )

    assert price.currency == "CNY"
    assert price.input_per_million is None
    assert price.input_cache_hit_per_million == Decimal("0.025")
    assert price.input_cache_miss_per_million == Decimal("3")
    assert price.output_per_million == Decimal("6")
    assert price.source_url == "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
    assert len(price.snapshot_sha256) == 64
    assert calculation.amount == Decimal("0.0001355")
    assert calculation.currency == "CNY"
    assert calculation.pricing_snapshot_sha256 == price.snapshot_sha256


def test_catalog_supports_flat_input_output_text_model_without_extra_mode_config() -> None:
    catalog = LLMPricingCatalog.from_toml(
        """
        schema_version = "llm-pricing.v1"

        [[models]]
        provider = "llm.example"
        model = "model-a"
        currency = "USD"
        input_per_million = "2"
        output_per_million = "8"
        source_url = "https://llm.example/pricing"
        """
    )

    price = catalog.price_for(provider="LLM.EXAMPLE", model="model-a")
    calculation = price.calculate(LLMTokenUsage(input_tokens=1000, output_tokens=250))

    assert calculation.amount == Decimal("0.004")
    assert calculation.currency == "USD"


def test_cache_split_price_refuses_incomplete_or_inconsistent_usage() -> None:
    price = load_llm_pricing().price_for(
        provider="api.deepseek.com",
        model="deepseek-v4-pro",
    )

    with pytest.raises(ValueError, match="缓存"):
        price.calculate(LLMTokenUsage(input_tokens=31, output_tokens=17))
    with pytest.raises(ValueError, match="不一致"):
        price.calculate(
            LLMTokenUsage(
                input_tokens=31,
                output_tokens=17,
                input_cache_hit_tokens=20,
                input_cache_miss_tokens=10,
            )
        )


def test_unknown_model_has_no_silent_fallback_price() -> None:
    with pytest.raises(LLMPriceNotConfiguredError):
        load_llm_pricing().price_for(
            provider="api.deepseek.com",
            model="unknown-model",
        )


@pytest.mark.parametrize(
    "rate_fields",
    (
        'input_per_million = "1"\ninput_cache_hit_per_million = "0.1"\n'
        'input_cache_miss_per_million = "1"',
        'input_cache_hit_per_million = "0.1"',
    ),
)
def test_catalog_rejects_ambiguous_or_incomplete_input_rates(rate_fields: str) -> None:
    with pytest.raises(ValueError, match="输入单价"):
        LLMPricingCatalog.from_toml(
            f"""
            schema_version = "llm-pricing.v1"

            [[models]]
            provider = "llm.example"
            model = "model-a"
            currency = "USD"
            {rate_fields}
            output_per_million = "8"
            source_url = "https://llm.example/pricing"
            """
        )
