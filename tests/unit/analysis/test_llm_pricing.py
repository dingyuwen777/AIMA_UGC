from __future__ import annotations

from datetime import UTC, date, datetime
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
    price = catalog.price_for(
        provider="api.deepseek.com",
        model="deepseek-v4-pro",
        at=datetime(2026, 8, 24, tzinfo=UTC),
    )

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
    assert price.input_cache_hit_per_million_tokens == Decimal("0.025")
    assert price.input_cache_miss_per_million_tokens == Decimal("3")
    assert price.output_per_million_tokens == Decimal("6")
    assert price.source_url == "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
    assert price.effective_date == date(2026, 8, 24)
    assert not hasattr(price, "input_cache_hit_per_million")
    assert not hasattr(price, "input_cache_miss_per_million")
    assert not hasattr(price, "output_per_million")
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
        output_per_million_tokens = "8"
        source_url = "https://llm.example/pricing"
        effective_date = "2026-08-20"
        """
    )

    price = catalog.price_for(
        provider="LLM.EXAMPLE",
        model="model-a",
        at=datetime(2026, 8, 20, tzinfo=UTC),
    )
    calculation = price.calculate(LLMTokenUsage(input_tokens=1000, output_tokens=250))

    assert calculation.amount == Decimal("0.004")
    assert calculation.currency == "USD"


@pytest.mark.parametrize(
    "at",
    (
        datetime(2026, 8, 24, 0, tzinfo=UTC),
        datetime(2026, 8, 24, 12, tzinfo=UTC),
    ),
)
def test_deepseek_official_example_uses_exact_decimal_cost(at: datetime) -> None:
    price = load_llm_pricing().price_for(
        provider="api.deepseek.com",
        model="deepseek-v4-pro",
        at=at,
    )

    calculation = price.calculate(
        LLMTokenUsage(
            input_tokens=1_000_000,
            output_tokens=100_000,
            input_cache_hit_tokens=800_000,
            input_cache_miss_tokens=200_000,
        )
    )

    assert calculation.amount == Decimal("1.22")
    assert calculation.currency == "CNY"


def test_cache_split_price_refuses_incomplete_or_inconsistent_usage() -> None:
    price = load_llm_pricing().price_for(
        provider="api.deepseek.com",
        model="deepseek-v4-pro",
        at=datetime(2026, 8, 24, tzinfo=UTC),
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
            at=datetime(2026, 8, 24, tzinfo=UTC),
        )


def test_price_periods_are_provider_and_model_independent() -> None:
    catalog = LLMPricingCatalog.from_toml(
        """
        schema_version = "llm-pricing.v1"

        [[models]]
        provider = "llm.example"
        model = "model-a"
        currency = "USD"
        source_url = "https://llm.example/pricing"
        effective_date = "2026-08-20"
        timezone = "UTC"

        [[models.price_periods]]
        name = "standard"
        input_per_million = "2"
        output_per_million_tokens = "8"

        [[models.price_periods]]
        name = "discount"
        time_ranges = ["22:00-06:00"]
        input_per_million = "1"
        output_per_million_tokens = "4"
        """
    )

    standard = catalog.price_for(
        provider="llm.example",
        model="model-a",
        at=datetime(2026, 8, 20, 12, tzinfo=UTC),
    )
    discount_before_midnight = catalog.price_for(
        provider="llm.example",
        model="model-a",
        at=datetime(2026, 8, 20, 23, tzinfo=UTC),
    )
    discount_after_midnight = catalog.price_for(
        provider="llm.example",
        model="model-a",
        at=datetime(2026, 8, 21, 5, 59, 59, tzinfo=UTC),
    )

    assert standard.input_per_million == Decimal("2")
    assert discount_before_midnight.input_per_million == Decimal("1")
    assert discount_after_midnight.input_per_million == Decimal("1")


@pytest.mark.parametrize(
    ("periods", "message"),
    (
        (
            """
            [[models.price_periods]]
            name = "first"
            time_ranges = ["09:00-12:00"]
            input_per_million = "1"
            output_per_million_tokens = "2"
            """,
            "默认价格时段",
        ),
        (
            """
            [[models.price_periods]]
            name = "default"
            input_per_million = "1"
            output_per_million_tokens = "2"

            [[models.price_periods]]
            name = "first"
            time_ranges = ["09:00-12:00"]
            input_per_million = "1"
            output_per_million_tokens = "2"

            [[models.price_periods]]
            name = "second"
            time_ranges = ["11:00-13:00"]
            input_per_million = "1"
            output_per_million_tokens = "2"
            """,
            "重叠",
        ),
    ),
)
def test_catalog_rejects_invalid_price_period_coverage(periods: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        LLMPricingCatalog.from_toml(
            f"""
            schema_version = "llm-pricing.v1"

            [[models]]
            provider = "llm.example"
            model = "model-a"
            currency = "USD"
            source_url = "https://llm.example/pricing"
            effective_date = "2026-08-20"
            timezone = "UTC"
            {periods}
            """
        )


def test_scheduled_price_requires_timezone_aware_request_time() -> None:
    catalog = LLMPricingCatalog.from_toml(
        """
        schema_version = "llm-pricing.v1"

        [[models]]
        provider = "llm.example"
        model = "model-a"
        currency = "USD"
        source_url = "https://llm.example/pricing"
        effective_date = "2026-08-20"
        timezone = "UTC"

        [[models.price_periods]]
        name = "standard"
        input_per_million = "2"
        output_per_million_tokens = "8"

        [[models.price_periods]]
        name = "discount"
        time_ranges = ["22:00-06:00"]
        input_per_million = "1"
        output_per_million_tokens = "4"
        """
    )

    with pytest.raises(ValueError, match="时区"):
        catalog.price_for(
            provider="llm.example",
            model="model-a",
            at=datetime(2026, 8, 20, 9),
        )


@pytest.mark.parametrize(
    "rate_fields",
    (
        'input_per_million = "1"\ninput_cache_hit_per_million_tokens = "0.1"\n'
        'input_cache_miss_per_million_tokens = "1"',
        'input_cache_hit_per_million_tokens = "0.1"',
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
            output_per_million_tokens = "8"
            source_url = "https://llm.example/pricing"
            effective_date = "2026-08-20"
            """
        )


def test_catalog_reads_legacy_rate_fields_with_warning() -> None:
    with pytest.warns(FutureWarning, match="旧字段"):
        catalog = LLMPricingCatalog.from_toml(
            """
            schema_version = "llm-pricing.v1"

            [[models]]
            provider = "api.deepseek.com"
            model = "deepseek-v4-pro"
            currency = "CNY"
            input_cache_hit_per_million = "0.025"
            input_cache_miss_per_million = "3"
            output_per_million = "6"
            source_url = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
            """
        )

    price = catalog.price_for(provider="api.deepseek.com", model="deepseek-v4-pro")
    assert price.input_cache_hit_per_million_tokens == Decimal("0.025")
    assert price.input_cache_miss_per_million_tokens == Decimal("3")
    assert price.output_per_million_tokens == Decimal("6")
    assert price.effective_date is None


def test_catalog_rejects_mixed_new_and_legacy_names() -> None:
    with pytest.raises(ValueError, match="不能同时配置"):
        LLMPricingCatalog.from_toml(
            """
            schema_version = "llm-pricing.v1"

            [[models]]
            provider = "api.deepseek.com"
            model = "deepseek-v4-pro"
            currency = "CNY"
            input_cache_hit_per_million_tokens = "0.025"
            input_cache_hit_per_million = "0.025"
            input_cache_miss_per_million_tokens = "3"
            output_per_million_tokens = "6"
            source_url = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
            effective_date = "2026-08-20"
            """
        )


def test_catalog_requires_effective_date_for_new_names() -> None:
    with pytest.raises(ValueError, match="effective_date"):
        LLMPricingCatalog.from_toml(
            """
            schema_version = "llm-pricing.v1"

            [[models]]
            provider = "api.deepseek.com"
            model = "deepseek-v4-pro"
            currency = "CNY"
            input_cache_hit_per_million_tokens = "0.025"
            input_cache_miss_per_million_tokens = "3"
            output_per_million_tokens = "6"
            source_url = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
            """
        )
