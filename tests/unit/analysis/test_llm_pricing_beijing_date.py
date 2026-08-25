"""LLM Pricing 北京时间日历边界回归。"""

from datetime import UTC, datetime

from aima_ugc.adapters.llm.pricing import load_llm_pricing


def test_effective_date_uses_beijing_calendar_day() -> None:
    """北京时间进入生效日后，即使 UTC 仍是前一天也应启用当日价格。"""
    price = load_llm_pricing().price_for(
        provider="api.deepseek.com",
        model="deepseek-v4-pro",
        at=datetime(2026, 8, 23, 16, 0, 0, tzinfo=UTC),
    )

    assert price.effective_date is not None
    assert price.effective_date.isoformat() == "2026-08-24"
