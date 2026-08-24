from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from aima_ugc.adapters.llm.pricing import (
    LLMModelPrice,
    LLMPricingCatalog,
    LLMTokenUsage,
    load_llm_pricing,
)


def _price_at(at: datetime) -> LLMModelPrice:
    return load_llm_pricing().price_for(
        provider="api.deepseek.com",
        model="deepseek-v4-pro",
        at=at,
    )


def test_deepseek_v4_pro_uses_off_peak_price_before_weekday_peak_window() -> None:
    price = _price_at(datetime(2026, 8, 24, 0, 0, tzinfo=UTC))  # Monday 08:00 Asia/Shanghai

    assert price.input_cache_hit_per_million_tokens == Decimal("0.15")
    assert price.input_cache_miss_per_million_tokens == Decimal("4.5")
    assert price.output_per_million_tokens == Decimal("13.5")
    calculation = price.calculate(
        LLMTokenUsage(
            input_tokens=31,
            input_cache_hit_tokens=20,
            input_cache_miss_tokens=11,
            output_tokens=17,
        )
    )
    assert calculation.amount == Decimal("0.000282")


def test_deepseek_v4_pro_uses_peak_price_during_weekday_peak_window() -> None:
    price = _price_at(datetime(2026, 8, 24, 1, 0, tzinfo=UTC))  # Monday 09:00 Asia/Shanghai

    assert price.input_cache_hit_per_million_tokens == Decimal("0.30")
    assert price.input_cache_miss_per_million_tokens == Decimal("9.0")
    assert price.output_per_million_tokens == Decimal("27.0")
    calculation = price.calculate(
        LLMTokenUsage(
            input_tokens=31,
            input_cache_hit_tokens=20,
            input_cache_miss_tokens=11,
            output_tokens=17,
        )
    )
    assert calculation.amount == Decimal("0.000564")


def test_deepseek_v4_pro_weekend_same_clock_time_remains_off_peak() -> None:
    price = _price_at(datetime(2026, 8, 29, 1, 0, tzinfo=UTC))  # Saturday 09:00 Asia/Shanghai

    assert price.input_cache_hit_per_million_tokens == Decimal("0.15")
    assert price.input_cache_miss_per_million_tokens == Decimal("4.5")
    assert price.output_per_million_tokens == Decimal("13.5")


def test_price_period_weekdays_reject_unknown_weekday() -> None:
    with pytest.raises(ValueError, match="weekdays"):
        LLMPricingCatalog.from_toml(
            """
            schema_version = "llm-pricing.v1"

            [[models]]
            provider = "llm.example"
            model = "model-a"
            currency = "USD"
            source_url = "https://llm.example/pricing"
            effective_date = "2026-08-24"
            timezone = "UTC"

            [[models.price_periods]]
            name = "default"
            input_per_million = "1"
            output_per_million_tokens = "2"

            [[models.price_periods]]
            name = "weekday"
            weekdays = ["funday"]
            time_ranges = ["09:00-12:00"]
            input_per_million = "2"
            output_per_million_tokens = "4"
            """
        )
