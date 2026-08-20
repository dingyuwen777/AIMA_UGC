"""LLM 物理 HTTP 请求费用审计与非覆盖式复算。"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Literal, TextIO

from .pricing import (
    LLMModelPrice,
    LLMPriceNotConfiguredError,
    LLMPricingCatalog,
    LLMTokenUsage,
)

LLMHTTPRequestStatus = Literal["completed", "http_error", "network_error", "protocol_error"]


@dataclass(frozen=True, slots=True)
class LLMHTTPRequestAudit:
    """一次真实 HTTP 请求的安全审计事实，不保存 Prompt、正文或响应正文。"""

    http_request_id: str
    logical_request_id: str
    provider: str
    model: str
    started_at: datetime
    completed_at: datetime
    status: LLMHTTPRequestStatus
    status_code: int | None = None
    error_code: str | None = None
    input_tokens: int | None = None
    input_cache_hit_tokens: int | None = None
    input_cache_miss_tokens: int | None = None
    output_tokens: int | None = None
    input_per_million: Decimal | None = None
    input_cache_hit_per_million: Decimal | None = None
    input_cache_miss_per_million: Decimal | None = None
    output_per_million: Decimal | None = None
    pricing_source_url: str | None = None
    pricing_snapshot_sha256: str | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    cost_unavailable_reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": "llm-http-request.v1",
            "http_request_id": self.http_request_id,
            "logical_request_id": self.logical_request_id,
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "status": self.status,
            "status_code": self.status_code,
            "error_code": self.error_code,
            "usage": {
                "input_tokens": self.input_tokens,
                "input_cache_hit_tokens": self.input_cache_hit_tokens,
                "input_cache_miss_tokens": self.input_cache_miss_tokens,
                "output_tokens": self.output_tokens,
            },
            "pricing": {
                "input_per_million": _decimal_text(self.input_per_million),
                "input_cache_hit_per_million": _decimal_text(self.input_cache_hit_per_million),
                "input_cache_miss_per_million": _decimal_text(self.input_cache_miss_per_million),
                "output_per_million": _decimal_text(self.output_per_million),
                "source_url": self.pricing_source_url,
                "snapshot_sha256": self.pricing_snapshot_sha256,
            },
            "cost": {
                "amount": _decimal_text(self.cost_amount),
                "currency": self.cost_currency,
                **(
                    {"unavailable_reason": self.cost_unavailable_reason}
                    if self.cost_unavailable_reason is not None
                    else {}
                ),
            },
        }


@dataclass(frozen=True, slots=True)
class LLMRequestAuditSummary:
    """一个审计文件或复算报告的费用汇总。"""

    request_count: int
    calculated_request_count: int
    uncalculated_request_count: int
    total_cost_amount: Decimal | None
    cost_currency: str | None
    input_tokens: int
    input_cache_hit_tokens: int
    input_cache_miss_tokens: int
    output_tokens: int

    def to_payload(self) -> dict[str, object]:
        return {
            "request_count": self.request_count,
            "calculated_request_count": self.calculated_request_count,
            "uncalculated_request_count": self.uncalculated_request_count,
            "total_cost_amount": _decimal_text(self.total_cost_amount),
            "cost_currency": self.cost_currency,
            "input_tokens": self.input_tokens,
            "input_cache_hit_tokens": self.input_cache_hit_tokens,
            "input_cache_miss_tokens": self.input_cache_miss_tokens,
            "output_tokens": self.output_tokens,
        }


class LLMRequestAuditWriter:
    """并发安全追加审计；正常或异常退出时统一 fsync。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = Lock()
        self._file: TextIO | None = None
        self._summary: LLMRequestAuditSummary | None = None
        self._session_request_count = 0

    def __enter__(self) -> LLMRequestAuditWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8", newline="\n")
        return self

    def __exit__(self, *_: object) -> None:
        with self._lock:
            output = self._file
            self._file = None
            if output is not None:
                output.flush()
                os.fsync(output.fileno())
                output.close()
        self._summary = summarize_llm_request_audit(self.path)

    @property
    def summary(self) -> LLMRequestAuditSummary:
        if self._summary is None:
            raise RuntimeError("LLM 请求审计尚未完成汇总")
        return self._summary

    @property
    def session_request_count(self) -> int:
        """返回本次 Writer 打开期间追加的请求数，不包含同 run 的历史恢复记录。"""

        with self._lock:
            return self._session_request_count

    def record(self, audit: LLMHTTPRequestAudit) -> None:
        payload = json.dumps(
            audit.to_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock:
            if self._file is None:
                raise RuntimeError("LLM 请求审计 Writer 未打开")
            self._file.write(payload)
            self._file.write("\n")
            self._file.flush()
            self._session_request_count += 1


def summarize_llm_request_audit(path: Path) -> LLMRequestAuditSummary:
    """严格读取整个审计文件；损坏行不得静默跳过。"""

    payloads = _read_audit_payloads(Path(path))
    return _summary_from_payloads(payloads)


def recalculate_llm_request_costs(
    *,
    input_path: Path,
    output_path: Path,
    pricing_catalog: LLMPricingCatalog,
) -> LLMRequestAuditSummary:
    """用当前价格目录生成派生报告，绝不覆盖原物理请求审计。"""

    source = Path(input_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError("费用复算输出不得覆盖原 LLM 请求审计")
    original = source.read_bytes()
    payloads = _read_audit_payloads(source)
    recalculated: list[dict[str, object]] = []

    for payload in payloads:
        provider = _required_payload_text(payload, "provider")
        model = _required_payload_text(payload, "model")
        usage = _usage_from_payload(payload)
        try:
            price = pricing_catalog.price_for(provider=provider, model=model)
            calculation = price.calculate(usage)
        except (LLMPriceNotConfiguredError, ValueError) as exc:
            recalculated.append(
                {
                    "http_request_id": _required_payload_text(payload, "http_request_id"),
                    "provider": provider,
                    "model": model,
                    "usage": _usage_payload(usage),
                    "pricing": None,
                    "cost": {
                        "amount": None,
                        "currency": None,
                        "unavailable_reason": _safe_reason(exc),
                    },
                }
            )
            continue
        recalculated.append(
            {
                "http_request_id": _required_payload_text(payload, "http_request_id"),
                "provider": provider,
                "model": model,
                "usage": _usage_payload(usage),
                "pricing": _price_payload(price),
                "cost": {
                    "amount": _decimal_text(calculation.amount),
                    "currency": calculation.currency,
                },
            }
        )

    summary = _summary_from_payloads(recalculated)
    report: dict[str, object] = {
        "schema_version": "llm-cost-recalculation.v1",
        "source_audit": str(source),
        "source_audit_sha256": hashlib.sha256(original).hexdigest(),
        "summary": summary.to_payload(),
        "requests": recalculated,
    }
    _atomic_write_json(target, report)
    return summary


def _read_audit_payloads(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payloads: list[dict[str, object]] = []
    with path.open("rb") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            if not raw_line.strip():
                raise ValueError(f"{path}: 第 {line_number} 行为空")
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: 第 {line_number} 行不是合法 JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: 第 {line_number} 行顶层必须为 object")
            if payload.get("schema_version") != "llm-http-request.v1":
                raise ValueError(f"{path}: 第 {line_number} 行 schema_version 不支持")
            payloads.append(payload)
    return payloads


def _summary_from_payloads(payloads: list[dict[str, object]]) -> LLMRequestAuditSummary:
    calculated = 0
    uncalculated = 0
    total = Decimal("0")
    currencies: set[str] = set()
    input_tokens = 0
    hit_tokens = 0
    miss_tokens = 0
    output_tokens = 0

    for payload in payloads:
        usage = _usage_from_payload(payload)
        input_tokens += usage.input_tokens or 0
        hit_tokens += usage.input_cache_hit_tokens or 0
        miss_tokens += usage.input_cache_miss_tokens or 0
        output_tokens += usage.output_tokens or 0
        cost = payload.get("cost")
        if not isinstance(cost, dict):
            raise ValueError("LLM 请求审计 cost 必须为 object")
        amount = _optional_payload_decimal(cost.get("amount"), "cost.amount")
        currency = cost.get("currency")
        if amount is None:
            uncalculated += 1
            continue
        if not isinstance(currency, str) or not currency:
            raise ValueError("有费用的 LLM 请求审计缺少 cost.currency")
        calculated += 1
        total += amount
        currencies.add(currency)

    if len(currencies) > 1:
        raise ValueError("同一 LLM 请求审计包含多个币种，不能直接求和")
    currency = next(iter(currencies), None)
    return LLMRequestAuditSummary(
        request_count=len(payloads),
        calculated_request_count=calculated,
        uncalculated_request_count=uncalculated,
        total_cost_amount=total if calculated else None,
        cost_currency=currency,
        input_tokens=input_tokens,
        input_cache_hit_tokens=hit_tokens,
        input_cache_miss_tokens=miss_tokens,
        output_tokens=output_tokens,
    )


def _usage_from_payload(payload: dict[str, object]) -> LLMTokenUsage:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("LLM 请求审计 usage 必须为 object")
    return LLMTokenUsage(
        input_tokens=_optional_payload_int(usage.get("input_tokens"), "input_tokens"),
        output_tokens=_optional_payload_int(usage.get("output_tokens"), "output_tokens"),
        input_cache_hit_tokens=_optional_payload_int(
            usage.get("input_cache_hit_tokens"),
            "input_cache_hit_tokens",
        ),
        input_cache_miss_tokens=_optional_payload_int(
            usage.get("input_cache_miss_tokens"),
            "input_cache_miss_tokens",
        ),
    )


def _usage_payload(usage: LLMTokenUsage) -> dict[str, int | None]:
    return {
        "input_tokens": usage.input_tokens,
        "input_cache_hit_tokens": usage.input_cache_hit_tokens,
        "input_cache_miss_tokens": usage.input_cache_miss_tokens,
        "output_tokens": usage.output_tokens,
    }


def _price_payload(price: LLMModelPrice) -> dict[str, str | None]:
    return {
        "input_per_million": _decimal_text(price.input_per_million),
        "input_cache_hit_per_million": _decimal_text(price.input_cache_hit_per_million),
        "input_cache_miss_per_million": _decimal_text(price.input_cache_miss_per_million),
        "output_per_million": _decimal_text(price.output_per_million),
        "source_url": price.source_url,
        "snapshot_sha256": price.snapshot_sha256,
    }


def _required_payload_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"LLM 请求审计 {key} 必须为非空字符串")
    return value


def _optional_payload_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"LLM 请求审计 {field_name} 必须为非负整数或 null")
    return value


def _optional_payload_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"LLM 请求审计 {field_name} 必须为十进制数字") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"LLM 请求审计 {field_name} 必须为非负有限数字")
    return parsed


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _safe_reason(error: Exception) -> str:
    return f"{type(error).__name__}: {str(error).strip()}"[:500]


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


__all__ = [
    "LLMHTTPRequestAudit",
    "LLMHTTPRequestStatus",
    "LLMRequestAuditSummary",
    "LLMRequestAuditWriter",
    "recalculate_llm_request_costs",
    "summarize_llm_request_audit",
]
