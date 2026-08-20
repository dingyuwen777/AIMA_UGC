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
    input_cache_hit_tokens: int | None = None
    input_cache_miss_tokens: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
            ("input_cache_hit_tokens", self.input_cache_hit_tokens),
            ("input_cache_miss_tokens", self.input_cache_miss_tokens),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} 必须是非负整数或 None")


@dataclass(frozen=True, slots=True)
class LLMCostCalculation:
    """按一份冻结价格快照计算出的费用。"""

    amount: Decimal
    currency: str
    pricing_snapshot_sha256: str


@dataclass(frozen=True, slots=True)
class LLMModelPrice:
    """一个 provider/model 的最小文本 token 单价事实。"""

    provider: str
    model: str
    currency: str
    output_per_million: Decimal
    source_url: str
    input_per_million: Decimal | None = None
    input_cache_hit_per_million: Decimal | None = None
    input_cache_miss_per_million: Decimal | None = None

    @property
    def uses_cache_split(self) -> bool:
        return self.input_cache_hit_per_million is not None

    @property
    def snapshot_sha256(self) -> str:
        """用规范化价格内容生成身份，避免维护人工版本号。"""

        payload = {
            "provider": self.provider,
            "model": self.model,
            "currency": self.currency,
            "input_per_million": _decimal_text(self.input_per_million),
            "input_cache_hit_per_million": _decimal_text(
                self.input_cache_hit_per_million
            ),
            "input_cache_miss_per_million": _decimal_text(
                self.input_cache_miss_per_million
            ),
            "output_per_million": _decimal_text(self.output_per_million),
            "source_url": self.source_url,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def calculate(self, usage: LLMTokenUsage) -> LLMCostCalculation:
        """严格按可观察 token 分类计算；缺字段时不做最坏/最好情况猜测。"""

        if usage.output_tokens is None:
            raise ValueError("费用计算缺少输出 token")
        output_cost = Decimal(usage.output_tokens) * self.output_per_million

        if self.uses_cache_split:
            hit = usage.input_cache_hit_tokens
            miss = usage.input_cache_miss_tokens
            if hit is None or miss is None:
                raise ValueError("缓存拆分价格要求缓存命中和未命中 token")
            if usage.input_tokens is not None and usage.input_tokens != hit + miss:
                raise ValueError("输入 token 与缓存命中/未命中 token 之和不一致")
            hit_price = self.input_cache_hit_per_million
            miss_price = self.input_cache_miss_per_million
            if hit_price is None or miss_price is None:  # pragma: no cover - 构造校验兜底
                raise RuntimeError("缓存拆分价格状态无效")
            input_cost = Decimal(hit) * hit_price + Decimal(miss) * miss_price
        else:
            if usage.input_tokens is None:
                raise ValueError("费用计算缺少输入 token")
            input_price = self.input_per_million
            if input_price is None:  # pragma: no cover - 构造校验兜底
                raise RuntimeError("普通输入价格状态无效")
            input_cost = Decimal(usage.input_tokens) * input_price

        return LLMCostCalculation(
            amount=(input_cost + output_cost) / Decimal(1_000_000),
            currency=self.currency,
            pricing_snapshot_sha256=self.snapshot_sha256,
        )


@dataclass(frozen=True, slots=True)
class LLMPricingCatalog:
    """没有跨模型 fallback 的文本 LLM 价格目录。"""

    models: tuple[LLMModelPrice, ...]

    @classmethod
    def from_toml(cls, content: str) -> LLMPricingCatalog:
        try:
            payload = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError("LLM Pricing TOML 无效") from exc
        if payload.get("schema_version") != "llm-pricing.v1":
            raise ValueError("LLM Pricing schema_version 必须为 llm-pricing.v1")
        raw_models = payload.get("models")
        if not isinstance(raw_models, list) or not raw_models:
            raise ValueError("LLM Pricing models 必须为非空数组")

        parsed: list[LLMModelPrice] = []
        seen: set[tuple[str, str]] = set()
        for index, raw in enumerate(raw_models):
            if not isinstance(raw, dict):
                raise ValueError(f"LLM Pricing models[{index}] 必须为对象")
            provider = _provider(_required_text(raw, "provider"))
            model = _required_text(raw, "model")
            identity = (provider, model)
            if identity in seen:
                raise ValueError(f"LLM Pricing provider/model 重复: {provider}/{model}")
            seen.add(identity)

            currency = _required_text(raw, "currency")
            if len(currency) != 3 or not currency.isascii() or not currency.isupper():
                raise ValueError("LLM Pricing currency 必须为大写三字母币种")
            source_url = _source_url(_required_text(raw, "source_url"))
            output_price = _positive_decimal(raw.get("output_per_million"), "output_per_million")
            input_price = _optional_positive_decimal(
                raw.get("input_per_million"),
                "input_per_million",
            )
            hit_price = _optional_positive_decimal(
                raw.get("input_cache_hit_per_million"),
                "input_cache_hit_per_million",
            )
            miss_price = _optional_positive_decimal(
                raw.get("input_cache_miss_per_million"),
                "input_cache_miss_per_million",
            )
            has_flat = input_price is not None
            has_complete_cache = hit_price is not None and miss_price is not None
            if has_flat == has_complete_cache or (hit_price is None) != (miss_price is None):
                raise ValueError(
                    "LLM Pricing 输入单价必须二选一：input_per_million，或完整缓存命中/未命中单价"
                )
            parsed.append(
                LLMModelPrice(
                    provider=provider,
                    model=model,
                    currency=currency,
                    input_per_million=input_price,
                    input_cache_hit_per_million=hit_price,
                    input_cache_miss_per_million=miss_price,
                    output_per_million=output_price,
                    source_url=source_url,
                )
            )
        return cls(models=tuple(parsed))

    def price_for(self, *, provider: str, model: str) -> LLMModelPrice:
        identity = (_provider(provider), model)
        for price in self.models:
            if (price.provider, price.model) == identity:
                return price
        raise LLMPriceNotConfiguredError(
            f"LLM Pricing 未配置 provider/model: {identity[0]}/{identity[1]}"
        )


def load_llm_pricing() -> LLMPricingCatalog:
    """读取包内价格目录；每个 Adapter run 只需加载一次。"""

    content = (
        files("aima_ugc.adapters.llm").joinpath("pricing.toml").read_text(encoding="utf-8")
    )
    return LLMPricingCatalog.from_toml(content)


def _provider(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("LLM Pricing provider 不能为空")
    return normalized


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LLM Pricing {key} 必须为非空字符串")
    return value.strip()


def _source_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname is None or parsed.username or parsed.password:
        raise ValueError("LLM Pricing source_url 必须是无凭据 HTTPS URL")
    return value


def _positive_decimal(value: object, field_name: str) -> Decimal:
    parsed = _decimal(value, field_name)
    if parsed <= 0:
        raise ValueError(f"LLM Pricing {field_name} 必须大于 0")
    return parsed


def _optional_positive_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _positive_decimal(value, field_name)


def _decimal(value: object, field_name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"LLM Pricing {field_name} 必须为十进制数字")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"LLM Pricing {field_name} 必须为十进制数字") from exc
    if not parsed.is_finite():
        raise ValueError(f"LLM Pricing {field_name} 必须为有限数字")
    return parsed


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


__all__ = [
    "LLMCostCalculation",
    "LLMModelPrice",
    "LLMPriceNotConfiguredError",
    "LLMPricingCatalog",
    "LLMTokenUsage",
    "load_llm_pricing",
]
