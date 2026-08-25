"""文本 LLM token 单价目录与可复算 Decimal 费用计算。"""

from __future__ import annotations

import hashlib
import json
import tomllib
import warnings
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aima_ugc.platform.time import beijing_now


class LLMPriceNotConfiguredError(LookupError):
    """目标 provider/model/请求时点没有明确价格，禁止使用默认单价猜测。"""


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
    output_per_million_tokens: Decimal
    source_url: str
    effective_date: date | None = None
    input_per_million: Decimal | None = None
    input_cache_hit_per_million_tokens: Decimal | None = None
    input_cache_miss_per_million_tokens: Decimal | None = None

    @property
    def uses_cache_split(self) -> bool:
        return self.input_cache_hit_per_million_tokens is not None

    @property
    def snapshot_sha256(self) -> str:
        """保持既有审计快照身份，不让配置字段改名改写历史语义。"""

        payload = {
            "provider": self.provider,
            "model": self.model,
            "currency": self.currency,
            "input_per_million": _decimal_text(self.input_per_million),
            "input_cache_hit_per_million": _decimal_text(self.input_cache_hit_per_million_tokens),
            "input_cache_miss_per_million": _decimal_text(self.input_cache_miss_per_million_tokens),
            "output_per_million": _decimal_text(self.output_per_million_tokens),
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
        output_cost = Decimal(usage.output_tokens) * self.output_per_million_tokens

        if self.uses_cache_split:
            hit = usage.input_cache_hit_tokens
            miss = usage.input_cache_miss_tokens
            if hit is None or miss is None:
                raise ValueError("缓存拆分价格要求缓存命中和未命中 token")
            if usage.input_tokens is not None and usage.input_tokens != hit + miss:
                raise ValueError("输入 token 与缓存命中/未命中 token 之和不一致")
            hit_price = self.input_cache_hit_per_million_tokens
            miss_price = self.input_cache_miss_per_million_tokens
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
class _LocalTimeRange:
    start_second: int
    end_second: int

    def contains(self, second_of_day: int) -> bool:
        if self.start_second < self.end_second:
            return self.start_second <= second_of_day < self.end_second
        return second_of_day >= self.start_second or second_of_day < self.end_second

    def segments(self) -> tuple[tuple[int, int], ...]:
        if self.start_second < self.end_second:
            return ((self.start_second, self.end_second),)
        return ((self.start_second, 86_400), (0, self.end_second))


@dataclass(frozen=True, slots=True)
class _LLMPricePeriod:
    name: str
    time_ranges: tuple[_LocalTimeRange, ...]
    weekdays: frozenset[int] | None
    price: LLMModelPrice

    def applies_on(self, weekday: int) -> bool:
        return self.weekdays is None or weekday in self.weekdays


@dataclass(frozen=True, slots=True)
class _LLMModelSchedule:
    provider: str
    model: str
    timezone: ZoneInfo
    default_price: LLMModelPrice
    scheduled_periods: tuple[_LLMPricePeriod, ...]

    def price_at(self, at: datetime) -> LLMModelPrice:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("LLM Pricing 分时选价要求带时区的请求时间")
        local = at.astimezone(self.timezone)
        second_of_day = local.hour * 3600 + local.minute * 60 + local.second
        for period in self.scheduled_periods:
            if period.applies_on(local.weekday()) and any(
                item.contains(second_of_day) for item in period.time_ranges
            ):
                return period.price
        return self.default_price


@dataclass(frozen=True, slots=True)
class LLMPricingCatalog:
    """没有跨模型 fallback、支持每模型独立分时规则的文本 LLM 价格目录。"""

    models: tuple[LLMModelPrice, ...]
    _schedules: tuple[_LLMModelSchedule, ...] = field(default=(), repr=False)

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
        schedules: list[_LLMModelSchedule] = []
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

            currency = _currency(_required_text(raw, "currency"))
            source_url = _source_url(_required_text(raw, "source_url"))
            raw_periods = raw.get("price_periods")
            if raw_periods is None:
                price, legacy_fields = _model_price(
                    raw,
                    provider=provider,
                    model=model,
                    currency=currency,
                    source_url=source_url,
                    effective_date=_effective_date(
                        raw.get("effective_date"),
                        required=not _has_legacy_rate_field(raw),
                    ),
                    allow_legacy=True,
                )
                if "timezone" in raw:
                    raise ValueError("LLM Pricing timezone 仅用于 price_periods 分时配置")
                _warn_legacy_fields(legacy_fields)
                parsed.append(price)
                continue

            if _has_any_rate_field(raw):
                raise ValueError("LLM Pricing 模型级单价与 price_periods 不能同时配置")
            if not isinstance(raw_periods, list) or not raw_periods:
                raise ValueError("LLM Pricing price_periods 必须为非空数组")
            timezone = _timezone(_required_text(raw, "timezone"))
            effective_date = _effective_date(raw.get("effective_date"), required=True)
            default_price: LLMModelPrice | None = None
            scheduled_periods: list[_LLMPricePeriod] = []
            seen_period_names: set[str] = set()
            for period_index, raw_period in enumerate(raw_periods):
                if not isinstance(raw_period, dict):
                    raise ValueError(
                        f"LLM Pricing models[{index}].price_periods[{period_index}] 必须为对象"
                    )
                name = _required_text(raw_period, "name")
                if name in seen_period_names:
                    raise ValueError(f"LLM Pricing price_periods.name 重复: {name}")
                seen_period_names.add(name)
                period_price, legacy_fields = _model_price(
                    raw_period,
                    provider=provider,
                    model=model,
                    currency=currency,
                    source_url=source_url,
                    effective_date=effective_date,
                    allow_legacy=False,
                )
                if legacy_fields:  # pragma: no cover - allow_legacy=False 已保证
                    raise RuntimeError("LLM Pricing 分时价格旧字段状态无效")
                ranges = _time_ranges(raw_period.get("time_ranges"))
                weekdays = _weekdays(raw_period.get("weekdays"))
                if not ranges:
                    if weekdays is not None:
                        raise ValueError("LLM Pricing weekdays 仅用于带 time_ranges 的分时价格")
                    if default_price is not None:
                        raise ValueError("LLM Pricing 每个模型只能配置一个默认价格时段")
                    default_price = period_price
                else:
                    scheduled_periods.append(
                        _LLMPricePeriod(
                            name=name,
                            time_ranges=ranges,
                            weekdays=weekdays,
                            price=period_price,
                        )
                    )
            if default_price is None:
                raise ValueError("LLM Pricing price_periods 必须包含一个默认价格时段")
            _validate_no_overlapping_ranges(scheduled_periods)
            parsed.append(default_price)
            schedules.append(
                _LLMModelSchedule(
                    provider=provider,
                    model=model,
                    timezone=timezone,
                    default_price=default_price,
                    scheduled_periods=tuple(scheduled_periods),
                )
            )
        return cls(models=tuple(parsed), _schedules=tuple(schedules))

    def price_for(
        self,
        *,
        provider: str,
        model: str,
        at: datetime | None = None,
    ) -> LLMModelPrice:
        identity = (_provider(provider), model)
        request_at = at or beijing_now()
        for schedule in self._schedules:
            if (schedule.provider, schedule.model) == identity:
                return _price_effective_at(schedule.price_at(request_at), request_at)
        for price in self.models:
            if (price.provider, price.model) == identity:
                return _price_effective_at(price, request_at)
        raise LLMPriceNotConfiguredError(
            f"LLM Pricing 未配置 provider/model: {identity[0]}/{identity[1]}"
        )

    def has_price(self, *, provider: str, model: str) -> bool:
        identity = (_provider(provider), model)
        return any((price.provider, price.model) == identity for price in self.models)


def _price_effective_at(price: LLMModelPrice, at: datetime) -> LLMModelPrice:
    """只在 AIMA 价格目录生效日及之后返回价格，避免历史请求套用未来价格。"""

    if price.effective_date is None:
        return price
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("LLM Pricing effective_date 选价要求带时区的请求时间")
    request_date = at.astimezone(UTC).date()
    if request_date < price.effective_date:
        raise LLMPriceNotConfiguredError(
            "LLM Pricing 价格尚未生效: "
            f"{price.provider}/{price.model}; "
            f"request_date={request_date.isoformat()}; "
            f"effective_date={price.effective_date.isoformat()}"
        )
    return price


def load_llm_pricing() -> LLMPricingCatalog:
    """读取包内价格目录；每个 Adapter run 只需加载一次。"""

    content = files("aima_ugc.adapters.llm").joinpath("pricing.toml").read_text(encoding="utf-8")
    return LLMPricingCatalog.from_toml(content)


def _provider(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("LLM Pricing provider 不能为空")
    return normalized


def _currency(value: str) -> str:
    if len(value) != 3 or not value.isascii() or not value.isupper():
        raise ValueError("LLM Pricing currency 必须为大写三字母币种")
    return value


def _timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"LLM Pricing timezone 不是有效 IANA 时区: {value}") from exc


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


def _model_price(
    mapping: dict[str, Any],
    *,
    provider: str,
    model: str,
    currency: str,
    source_url: str,
    effective_date: date | None,
    allow_legacy: bool,
) -> tuple[LLMModelPrice, tuple[str, ...]]:
    if not allow_legacy and _has_legacy_rate_field(mapping):
        raise ValueError("LLM Pricing price_periods 只接受包含 per_million_tokens 的正式字段")

    output_raw, output_field, output_legacy = _rate_value(
        mapping,
        current="output_per_million_tokens",
        legacy="output_per_million",
    )
    hit_raw, hit_field, hit_legacy = _rate_value(
        mapping,
        current="input_cache_hit_per_million_tokens",
        legacy="input_cache_hit_per_million",
    )
    miss_raw, miss_field, miss_legacy = _rate_value(
        mapping,
        current="input_cache_miss_per_million_tokens",
        legacy="input_cache_miss_per_million",
    )
    legacy_fields = tuple(
        field for field in (output_legacy, hit_legacy, miss_legacy) if field is not None
    )
    output_price = _positive_decimal(output_raw, output_field)
    input_price = _optional_positive_decimal(
        mapping.get("input_per_million"),
        "input_per_million",
    )
    hit_price = _optional_positive_decimal(hit_raw, hit_field)
    miss_price = _optional_positive_decimal(miss_raw, miss_field)
    has_flat = input_price is not None
    has_complete_cache = hit_price is not None and miss_price is not None
    if has_flat == has_complete_cache or (hit_price is None) != (miss_price is None):
        raise ValueError(
            "LLM Pricing 输入单价必须二选一：input_per_million，或完整缓存命中/未命中单价"
        )
    return (
        LLMModelPrice(
            provider=provider,
            model=model,
            currency=currency,
            input_per_million=input_price,
            input_cache_hit_per_million_tokens=hit_price,
            input_cache_miss_per_million_tokens=miss_price,
            output_per_million_tokens=output_price,
            source_url=source_url,
            effective_date=effective_date,
        ),
        legacy_fields,
    )


def _has_legacy_rate_field(mapping: dict[str, Any]) -> bool:
    return any(
        field_name in mapping
        for field_name in (
            "input_cache_hit_per_million",
            "input_cache_miss_per_million",
            "output_per_million",
        )
    )


def _has_any_rate_field(mapping: dict[str, Any]) -> bool:
    return "input_per_million" in mapping or any(
        field_name in mapping
        for field_name in (
            "input_cache_hit_per_million_tokens",
            "input_cache_miss_per_million_tokens",
            "output_per_million_tokens",
            "input_cache_hit_per_million",
            "input_cache_miss_per_million",
            "output_per_million",
        )
    )


def _warn_legacy_fields(fields: tuple[str, ...]) -> None:
    if not fields:
        return
    warnings.warn(
        f"LLM Pricing 使用旧字段 {', '.join(fields)}；请迁移到包含 per_million_tokens 的新字段",
        FutureWarning,
        stacklevel=3,
    )


_WEEKDAY_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
_ALL_WEEKDAYS = frozenset(range(7))


def _weekdays(value: object) -> frozenset[int] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise ValueError("LLM Pricing weekdays 必须为非空星期字符串数组")
    parsed: set[int] = set()
    for item in value:
        if not isinstance(item, str) or item != item.strip() or item not in _WEEKDAY_INDEX:
            raise ValueError("LLM Pricing weekdays 只接受 mon/tue/wed/thu/fri/sat/sun")
        weekday = _WEEKDAY_INDEX[item]
        if weekday in parsed:
            raise ValueError(f"LLM Pricing weekdays 重复: {item}")
        parsed.add(weekday)
    return frozenset(parsed)


def _time_ranges(value: object) -> tuple[_LocalTimeRange, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise ValueError("LLM Pricing time_ranges 必须为非空字符串数组")
    parsed: list[_LocalTimeRange] = []
    for item in value:
        if not isinstance(item, str) or item != item.strip() or item.count("-") != 1:
            raise ValueError("LLM Pricing time_ranges 必须使用 HH:MM-HH:MM")
        start_text, end_text = item.split("-", maxsplit=1)
        start_second = _clock_second(start_text)
        end_second = _clock_second(end_text)
        if start_second == end_second:
            raise ValueError("LLM Pricing time_ranges 起止时间不能相同")
        parsed.append(
            _LocalTimeRange(
                start_second=start_second,
                end_second=end_second,
            )
        )
    return tuple(parsed)


def _clock_second(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2 or any(
        len(part) != 2 or not part.isascii() or not part.isdigit() for part in parts
    ):
        raise ValueError("LLM Pricing time_ranges 必须使用 HH:MM-HH:MM")
    hour, minute = (int(part) for part in parts)
    if hour > 23 or minute > 59:
        raise ValueError("LLM Pricing time_ranges 包含无效时间")
    return hour * 3600 + minute * 60


def _validate_no_overlapping_ranges(periods: list[_LLMPricePeriod]) -> None:
    segments: list[tuple[int, int, int, str]] = []
    for period in periods:
        weekdays = period.weekdays or _ALL_WEEKDAYS
        for weekday in weekdays:
            for time_range in period.time_ranges:
                segments.extend(
                    (weekday, start, end, period.name) for start, end in time_range.segments()
                )
    segments.sort()
    for previous, current in zip(segments, segments[1:], strict=False):
        if current[0] == previous[0] and current[1] < previous[2]:
            raise ValueError(
                f"LLM Pricing price_periods 时间范围重叠: {previous[3]} / {current[3]}"
            )


def _rate_value(
    mapping: dict[str, Any],
    *,
    current: str,
    legacy: str,
) -> tuple[object, str, str | None]:
    has_current = current in mapping
    has_legacy = legacy in mapping
    if has_current and has_legacy:
        raise ValueError(f"LLM Pricing {current} 与旧字段 {legacy} 不能同时配置")
    if has_current:
        return mapping[current], current, None
    if has_legacy:
        return mapping[legacy], legacy, legacy
    return None, current, None


def _effective_date(value: object, *, required: bool) -> date | None:
    if value is None:
        if required:
            raise ValueError("LLM Pricing effective_date 必须为 YYYY-MM-DD 字符串")
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("LLM Pricing effective_date 必须为 YYYY-MM-DD 字符串")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("LLM Pricing effective_date 必须为合法 YYYY-MM-DD 日期") from exc


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
