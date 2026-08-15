"""Stage 7 TikHub 官方价格配置与保守计费测试。"""

from decimal import Decimal

import pytest
from aima_ugc.adapters.providers.tikhub.pricing import (
    TikHubPriceNotVerifiedError,
    TikHubPricingCatalog,
    load_tikhub_pricing,
)


def test_default_catalog_keeps_global_price_informational_only() -> None:
    catalog = load_tikhub_pricing()

    assert catalog.provider == "tikhub"
    assert catalog.currency == "USD"
    assert catalog.default_base_price == Decimal("0.001000")
    assert catalog.default_price_dispatch_fallback is False
    assert [
        (
            tier.min_requests_per_day,
            tier.max_requests_per_day,
            tier.discount_percent,
        )
        for tier in catalog.tiers
    ] == [
        (0, 1000, Decimal("0")),
        (1000, 5000, Decimal("10")),
        (5000, 10000, Decimal("20")),
        (10000, 20000, Decimal("30")),
        (20000, 30000, Decimal("40")),
        (30000, 2147483647, Decimal("50")),
    ]

    with pytest.raises(TikHubPriceNotVerifiedError, match="官方精确价格"):
        catalog.billing_for_endpoint("/api/v1/xiaohongshu/app_v2/search_notes")


def test_verified_endpoint_builds_conservative_estimated_billing() -> None:
    catalog = TikHubPricingCatalog.from_toml(
        """
        schema_version = "tikhub-pricing.v1"
        provider = "tikhub"
        currency = "USD"
        pricing_version = "test-2026-08-15"
        verified_at = "2026-08-15"
        official_pricing_url = "https://docs.tikhub.io/4592751m0"
        official_endpoint_info_path = "/api/v1/tikhub/user/get_endpoint_info"
        default_base_price = "0.001000"
        default_price_dispatch_fallback = false

        [[tiers]]
        min_requests_per_day = 0
        max_requests_per_day = 2147483647
        discount_percent = "0"

        [[endpoints]]
        path = "/api/v1/example/verified"
        verification_status = "verified"
        base_price = "0.002000"
        verified_at = "2026-08-15"
        verified_via = "get_endpoint_info"
        """
    )

    billing = catalog.billing_for_endpoint("/api/v1/example/verified")

    assert billing.status == "estimated"
    assert billing.currency == "USD"
    assert billing.unit == "request"
    assert billing.unit_price_snapshot == Decimal("0.002000")
    assert billing.estimated_cost == Decimal("0.002000")
    assert billing.actual_cost == Decimal("0")


def test_unverified_or_unknown_endpoint_fails_closed_without_default_fallback() -> None:
    catalog = TikHubPricingCatalog.from_toml(
        """
        schema_version = "tikhub-pricing.v1"
        provider = "tikhub"
        currency = "USD"
        pricing_version = "test-2026-08-15"
        verified_at = "2026-08-15"
        official_pricing_url = "https://docs.tikhub.io/4592751m0"
        official_endpoint_info_path = "/api/v1/tikhub/user/get_endpoint_info"
        default_base_price = "0.001000"
        default_price_dispatch_fallback = false

        [[tiers]]
        min_requests_per_day = 0
        max_requests_per_day = 2147483647
        discount_percent = "0"

        [[endpoints]]
        path = "/api/v1/example/pending"
        verification_status = "pending_endpoint_info"
        """
    )

    with pytest.raises(TikHubPriceNotVerifiedError):
        catalog.billing_for_endpoint("/api/v1/example/pending")
    with pytest.raises(TikHubPriceNotVerifiedError):
        catalog.billing_for_endpoint("/api/v1/example/not-listed")


def test_pricing_catalog_rejects_duplicate_or_nonpositive_verified_price() -> None:
    common = """
        schema_version = "tikhub-pricing.v1"
        provider = "tikhub"
        currency = "USD"
        pricing_version = "test-2026-08-15"
        verified_at = "2026-08-15"
        official_pricing_url = "https://docs.tikhub.io/4592751m0"
        official_endpoint_info_path = "/api/v1/tikhub/user/get_endpoint_info"
        default_base_price = "0.001000"
        default_price_dispatch_fallback = false

        [[tiers]]
        min_requests_per_day = 0
        max_requests_per_day = 2147483647
        discount_percent = "0"
    """

    with pytest.raises(ValueError, match="base_price"):
        TikHubPricingCatalog.from_toml(
            common
            + """
            [[endpoints]]
            path = "/api/v1/example/zero"
            verification_status = "verified"
            base_price = "0"
            verified_at = "2026-08-15"
            verified_via = "get_endpoint_info"
            """
        )

    with pytest.raises(ValueError, match="重复"):
        TikHubPricingCatalog.from_toml(
            common
            + """
            [[endpoints]]
            path = "/api/v1/example/duplicate"
            verification_status = "verified"
            base_price = "0.001"
            verified_at = "2026-08-15"
            verified_via = "get_endpoint_info"

            [[endpoints]]
            path = "/api/v1/example/duplicate"
            verification_status = "verified"
            base_price = "0.001"
            verified_at = "2026-08-15"
            verified_via = "get_endpoint_info"
            """
        )
