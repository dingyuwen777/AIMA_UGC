"""TikHub 官方价格配置加载与保守 Billing 构造。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from typing import Any, Literal

from aima_ugc.contracts.provider import ProviderBillingV1

TikHubPriceVerificationStatus = Literal["verified", "pending_endpoint_info"]


class TikHubPricingError(RuntimeError):
    """TikHub Pricing 配置或查价失败。"""


class TikHubPriceNotVerifiedError(TikHubPricingError):
    """目标 endpoint 没有已核验的官方精确单价。"""


@dataclass(frozen=True, slots=True)
class TikHubPricingTier:
    """TikHub 官方每日请求量阶梯折扣快照。"""

    min_requests_per_day: int
    max_requests_per_day: int
    discount_percent: Decimal


@dataclass(frozen=True, slots=True)
class TikHubEndpointPrice:
    """一个 TikHub endpoint 的官方价格核验状态。"""

    path: str
    verification_status: TikHubPriceVerificationStatus
    base_price: Decimal | None = None
    verified_at: str | None = None
    verified_via: str | None = None


@dataclass(frozen=True, slots=True)
class TikHubPricingCatalog:
    """版本化 TikHub Pricing 事实；只允许 verified endpoint 构造发送前 Billing。"""

    schema_version: str
    provider: str
    currency: str
    pricing_version: str
    verified_at: str
    official_pricing_url: str
    official_endpoint_info_path: str
    default_base_price: Decimal
    default_price_dispatch_fallback: bool
    tiers: tuple[TikHubPricingTier, ...]
    endpoints: tuple[TikHubEndpointPrice, ...]

    @classmethod
    def from_toml(cls, content: str) -> TikHubPricingCatalog:
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError("TikHub Pricing TOML 无效") from exc

        schema_version = _required_text(data, "schema_version")
        if schema_version != "tikhub-pricing.v1":
            raise ValueError("TikHub Pricing schema_version 必须为 tikhub-pricing.v1")
        provider = _required_text(data, "provider")
        if provider != "tikhub":
            raise ValueError("TikHub Pricing provider 必须为 tikhub")
        currency = _required_text(data, "currency")
        if len(currency) != 3 or not currency.isascii() or not currency.isupper():
            raise ValueError("TikHub Pricing currency 必须为大写三字母币种")

        default_base_price = _positive_decimal(data.get("default_base_price"), "default_base_price")
        fallback = data.get("default_price_dispatch_fallback")
        if not isinstance(fallback, bool):
            raise ValueError("default_price_dispatch_fallback 必须为布尔值")
        if fallback:
            raise ValueError("TikHub 全局默认价格不得作为 Dispatch fallback")

        tiers = _parse_tiers(data.get("tiers"))
        endpoints = _parse_endpoints(data.get("endpoints"))
        return cls(
            schema_version=schema_version,
            provider=provider,
            currency=currency,
            pricing_version=_required_text(data, "pricing_version"),
            verified_at=_required_text(data, "verified_at"),
            official_pricing_url=_required_text(data, "official_pricing_url"),
            official_endpoint_info_path=_required_text(data, "official_endpoint_info_path"),
            default_base_price=default_base_price,
            default_price_dispatch_fallback=fallback,
            tiers=tiers,
            endpoints=endpoints,
        )

    def endpoint(self, path: str) -> TikHubEndpointPrice:
        """返回 endpoint 配置；未知 endpoint 与未核验价格都按关闭失败处理。"""
        normalized = _normalize_path(path)
        for endpoint in self.endpoints:
            if endpoint.path == normalized:
                return endpoint
        raise TikHubPriceNotVerifiedError(
            f"TikHub endpoint 缺少已核验官方精确价格: {normalized}"
        )

    def billing_for_endpoint(self, path: str) -> ProviderBillingV1:
        """按已核验官方基价构造发送前保守 Billing，不生成假 actual_cost。"""
        endpoint = self.endpoint(path)
        if endpoint.verification_status != "verified" or endpoint.base_price is None:
            raise TikHubPriceNotVerifiedError(
                f"TikHub endpoint 缺少已核验官方精确价格: {endpoint.path}"
            )
        return ProviderBillingV1(
            status="estimated",
            currency=self.currency,
            unit="request",
            unit_price_snapshot=endpoint.base_price,
            estimated_cost=endpoint.base_price,
            actual_cost=Decimal("0"),
        )


def load_tikhub_pricing() -> TikHubPricingCatalog:
    """从 Python 包内版本化 TOML 读取生产 TikHub Pricing 配置。"""
    content = (
        files("aima_ugc.adapters.providers.tikhub")
        .joinpath("pricing.toml")
        .read_text(encoding="utf-8")
    )
    return TikHubPricingCatalog.from_toml(content)


def _parse_tiers(value: object) -> tuple[TikHubPricingTier, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("TikHub Pricing tiers 必须为非空数组")
    parsed: list[TikHubPricingTier] = []
    previous_max: int | None = None
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"TikHub Pricing tiers[{index}] 必须为对象")
        min_requests = _nonnegative_int(raw.get("min_requests_per_day"), "min_requests_per_day")
        max_requests = _nonnegative_int(raw.get("max_requests_per_day"), "max_requests_per_day")
        if max_requests <= min_requests:
            raise ValueError("TikHub Pricing tier max_requests_per_day 必须大于 min")
        if previous_max is None:
            if min_requests != 0:
                raise ValueError("TikHub Pricing tiers 必须从 0 开始")
        elif min_requests != previous_max:
            raise ValueError("TikHub Pricing tiers 必须连续且不重叠")
        discount = _decimal(raw.get("discount_percent"), "discount_percent")
        if discount < 0 or discount > 100:
            raise ValueError("TikHub Pricing discount_percent 必须在 0 到 100 之间")
        parsed.append(
            TikHubPricingTier(
                min_requests_per_day=min_requests,
                max_requests_per_day=max_requests,
                discount_percent=discount,
            )
        )
        previous_max = max_requests
    return tuple(parsed)


def _parse_endpoints(value: object) -> tuple[TikHubEndpointPrice, ...]:
    if not isinstance(value, list):
        raise ValueError("TikHub Pricing endpoints 必须为数组")
    parsed: list[TikHubEndpointPrice] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"TikHub Pricing endpoints[{index}] 必须为对象")
        path = _normalize_path(_required_text(raw, "path"))
        if path in seen:
            raise ValueError(f"TikHub Pricing endpoint 重复: {path}")
        seen.add(path)

        status = _required_text(raw, "verification_status")
        if status not in {"verified", "pending_endpoint_info"}:
            raise ValueError(f"TikHub Pricing verification_status 无效: {status}")
        base_price_raw = raw.get("base_price")
        if status == "verified":
            base_price = _positive_decimal(base_price_raw, "base_price")
            verified_at = _required_text(raw, "verified_at")
            verified_via = _required_text(raw, "verified_via")
        else:
            if base_price_raw is not None:
                raise ValueError("pending endpoint 不得携带未核验 base_price")
            base_price = None
            verified_at = _optional_text(raw.get("verified_at"))
            verified_via = _optional_text(raw.get("verified_via"))

        parsed.append(
            TikHubEndpointPrice(
                path=path,
                verification_status=status,  # type: ignore[arg-type]
                base_price=base_price,
                verified_at=verified_at,
                verified_via=verified_via,
            )
        )
    return tuple(parsed)


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"TikHub Pricing {key} 必须为非空字符串")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("TikHub Pricing 可选文本必须为非空字符串")
    return value.strip()


def _decimal(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"TikHub Pricing {field_name} 必须为十进制数字")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"TikHub Pricing {field_name} 必须为十进制数字") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"TikHub Pricing {field_name} 必须为有限数字")
    return decimal_value


def _positive_decimal(value: object, field_name: str) -> Decimal:
    decimal_value = _decimal(value, field_name)
    if decimal_value <= 0:
        raise ValueError(f"TikHub Pricing {field_name} 必须大于 0")
    return decimal_value


def _nonnegative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"TikHub Pricing {field_name} 必须为非负整数")
    return value


def _normalize_path(path: str) -> str:
    normalized = path.strip()
    if not normalized.startswith("/api/") or "?" in normalized or "#" in normalized:
        raise ValueError("TikHub Pricing endpoint 必须是无 query/fragment 的 /api/ 路径")
    return normalized


__all__ = [
    "TikHubEndpointPrice",
    "TikHubPriceNotVerifiedError",
    "TikHubPricingCatalog",
    "TikHubPricingError",
    "TikHubPricingTier",
    "load_tikhub_pricing",
]
