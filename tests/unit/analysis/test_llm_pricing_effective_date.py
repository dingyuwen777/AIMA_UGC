from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aima_ugc.adapters.llm.pricing import LLMPriceNotConfiguredError, load_llm_pricing


def test_deepseek_current_price_is_not_available_before_effective_date() -> None:
    catalog = load_llm_pricing()

    with pytest.raises(LLMPriceNotConfiguredError, match="尚未生效"):
        catalog.price_for(
            provider="api.deepseek.com",
            model="deepseek-v4-pro",
            at=datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC),
        )
