"""文本 LLM token 单价目录与可复算 Decimal 费用计算。"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit


class LLMPriceNotConfiguredError(LookupError):
    """目标 provider/model 没有明确价格，禁止使用默认单价猜测。"""


@dataclass(frozen=True, slots=True)
class LLMTokenUsage:
    """一次文本模型响应可观察到的 token 分类。"""

    input_tokens: int | None
    output_tokens: int | None
    input_cached_tokens: int | None = None
    input_uncached_tokens: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
            ("input_cached_tokens", self.input_cached_tokens),
            ("input_uncached_tokens", self.input_uncached_tokens),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} 必须是非负整数或 None")


@dataclass(frozen=True, slots=True)
class LLMCostCalculation:
    amount: Decimal
    currency: str
    pricing_snapshot_sha256: str


@dataclass(frozen=True, slots=True)
class LLMModelPrice:
    provider: str
    model: str
    currency: str
    output_per_million: Decimal
    source_url: str
    input_per_million: Decimal | None = None
    input_cached_per_million: Decimal | None = None
    input_uncached_per_million: Decimal | None = None

    @property
    def uses_cache_split(self) -> bool:
        return self.input_cached_per_million is not None

    @property
    def snapshot_sha256(self) -> str:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "currency": self.currency,
            "input_per_million": _decimal_text(self.input_per_million),
            "input_cached_per_million": _decimal_text(self.input_cached_per_million),
            "input_uncached_per_million": _decimal_text(self.input_uncached_per_million),
            "output_per_million": _decimal_text(self.output_per_million),
            "source_url": self.source_url,
        }
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def calculate(self, usage: LLMTokenUsage) -> LLMCostCalculation:
        if usage.output_tokens is None:
            raise ValueError("费用计算缺少输出 token")
        output_cost = Decimal(usage.output_tokens) * self.output_per_million
        if self.uses_cache_split:
            cached = usage.input_cached_tokens
            uncached = usage.input_uncached_tokens
            if cached is None or uncached is None:
                raise ValueError("缓存拆分价格要求 cached 和 uncached token")
            if usage.input_tokens is not None and usage.input_tokens != cached + uncached:
                raise ValueError("输入 token 与 cached/uncached token 之和不一致")
            input_cost = Decimal(cached) * self.input_cached_per_million + Decimal(uncached) * self.input_uncached_per_million
        else:
            if usage.input_tokens is None or self.input_per_million is None:
                raise ValueError("费用计算缺少输入 token")
            input_cost = Decimal(usage.input_tokens) * self.input_per_million
        return LLMCostCalculation((input_cost + output_cost) / Decimal(1_000_000), self.currency, self.snapshot_sha256)


@dataclass(frozen=True, slots=True)
class LLMPricingCatalog:
    models: tuple[LLMModelPrice, ...]

    @classmethod
    def from_toml(cls, content: str) -> "LLMPricingCatalog":
        payload = tomllib.loads(content)
        parsed = []
        for raw in payload["models"]:
            input_price = _optional_positive_decimal(raw.get("input_per_million"), "input_per_million")
            cached = _optional_positive_decimal(raw.get("input_cached_per_million"), "input_cached_per_million")
            uncached = _optional_positive_decimal(raw.get("input_uncached_per_million"), "input_uncached_per_million")
            parsed.append(LLMModelPrice(raw["provider"].lower(), raw["model"], raw["currency"], _positive_decimal(raw["output_per_million"], "output_per_million"), raw["source_url"], input_price, cached, uncached))
        return cls(tuple(parsed))

    def price_for(self, *, provider: str, model: str) -> LLMModelPrice:
        for price in self.models:
            if price.provider == provider.lower() and price.model == model:
                return price
        raise LLMPriceNotConfiguredError(f"LLM Pricing 未配置 provider/model: {provider}/{model}")


def load_llm_pricing() -> LLMPricingCatalog:
    return LLMPricingCatalog.from_toml(files("aima_ugc.adapters.llm").joinpath("pricing.toml").read_text(encoding="utf-8"))


def _positive_decimal(value: object, field_name: str) -> Decimal:
    result = _decimal(value, field_name)
    if result <= 0:
        raise ValueError(f"LLM Pricing {field_name} 必须大于 0")
    return result


def _optional_positive_decimal(value: object, field_name: str) -> Decimal | None:
    return None if value is None else _positive_decimal(value, field_name)


def _decimal(value: object, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"LLM Pricing {field_name} 必须为十进制数字") from exc
    if not result.is_finite():
        raise ValueError(f"LLM Pricing {field_name} 必须为有限数字")
    return result


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


__all__ = ["LLMCostCalculation", "LLMModelPrice", "LLMPriceNotConfiguredError", "LLMPricingCatalog", "LLMTokenUsage", "load_llm_pricing"]
