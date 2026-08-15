"""Provider Transport Port 与一次发送 Client。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import Field, JsonValue, SecretStr, model_validator

from aima_ugc.contracts.provider import (
    JsonObject,
    ProviderAttemptV1,
    ProviderBillingV1,
    ProviderErrorV1,
    ProviderRequestV1,
    RawRequestV1,
    RawResponseV1,
    assert_redacted_json,
    assert_secret_free,
    redact_json,
)
from aima_ugc.contracts.provider.base import ProviderBaseModel


class ProviderTransportRequest(ProviderBaseModel):
    """Provider Adapter 交给 Transport 的一次低层执行请求。"""

    transport_kind: Literal["http", "sdk", "file"]
    method: str | None = Field(default=None, min_length=1, max_length=32)
    path: str = Field(min_length=1, max_length=2048)
    params: JsonObject = Field(default_factory=dict)
    headers: JsonObject = Field(default_factory=dict)
    body: JsonValue = None
    credential: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.transport_kind == "http" and self.method is None:
            raise ValueError("HTTP Transport Request 必须包含 method")
        assert_redacted_json(self.path, path="transport.path")
        assert_secret_free(self.params, path="transport.params")
        assert_secret_free(self.headers, path="transport.headers")
        assert_secret_free(self.body, path="transport.body")
        return self


class ProviderTransportResponse(ProviderBaseModel):
    """Transport 已收到的确定 Provider 响应。"""

    status_code: int | None = Field(default=None, ge=100, le=599)
    external_request_id: str | None = Field(default=None, min_length=1, max_length=512)
    body: JsonValue = None
    billing: ProviderBillingV1 | None = None


class ProviderTransportFailure(RuntimeError):
    """Transport 未取得确定响应时的安全失败边界。"""

    def __init__(
        self,
        *,
        delivery: Literal["not_sent", "unknown"],
        code: str,
        safe_summary: str,
        billing: ProviderBillingV1,
    ) -> None:
        super().__init__(safe_summary)
        self.delivery = delivery
        self.code = code
        self.safe_summary = safe_summary
        self.billing = billing

    @classmethod
    def not_sent(cls, *, code: str, safe_summary: str) -> Self:
        return cls(
            delivery="not_sent",
            code=code,
            safe_summary=safe_summary,
            billing=ProviderBillingV1(status="not_billable"),
        )

    @classmethod
    def unknown(
        cls,
        *,
        code: str,
        safe_summary: str,
        currency: str | None = None,
        unit: str | None = None,
    ) -> Self:
        return cls(
            delivery="unknown",
            code=code,
            safe_summary=safe_summary,
            billing=ProviderBillingV1(status="unknown", currency=currency, unit=unit),
        )


class ProviderTransport(Protocol):
    """一次 send 对应一次真实 Provider 执行；实现不得隐藏自动重试。"""

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse: ...


@dataclass(frozen=True, slots=True)
class ProviderDispatchResult:
    """一次 Transport 调用产生的 Attempt 与脱敏 Raw 输入。"""

    request: ProviderRequestV1
    attempt: ProviderAttemptV1
    raw_request: RawRequestV1
    raw_response: RawResponseV1 | None


def _redacted_object(value: object) -> JsonObject:
    redacted = redact_json(value)
    if not isinstance(redacted, dict):
        raise TypeError("Raw JSON Object 必须是对象")
    return redacted


def _redacted_string(value: str) -> str:
    redacted = redact_json(value)
    if not isinstance(redacted, str):
        raise TypeError("Raw JSON String 必须是字符串")
    return redacted


def _classify_http_error(status_code: int) -> ProviderErrorV1 | None:
    if status_code < 400:
        return None
    if status_code == 429:
        return ProviderErrorV1(
            category="rate_limited",
            code="http_429",
            safe_summary="Provider 返回 HTTP 429",
            retryable=True,
        )
    if status_code in {408, 425} or status_code >= 500:
        return ProviderErrorV1(
            category="transient",
            code=f"http_{status_code}",
            safe_summary=f"Provider 返回可重试 HTTP {status_code}",
            retryable=True,
        )
    return ProviderErrorV1(
        category="permanent",
        code=f"http_{status_code}",
        safe_summary=f"Provider 返回不可重试 HTTP {status_code}",
        retryable=False,
    )


def _unknown_billing_with_planned_snapshot(
    *,
    planned: ProviderBillingV1 | None,
    reported: ProviderBillingV1,
) -> ProviderBillingV1:
    if planned is None or planned.status != "estimated":
        return reported
    if reported.currency is not None and reported.currency != planned.currency:
        raise ValueError("Provider unknown Billing 币种与发送前价格快照不一致")
    if reported.unit is not None and reported.unit != planned.unit:
        raise ValueError("Provider unknown Billing 单位与发送前价格快照不一致")
    return ProviderBillingV1(
        status="unknown",
        currency=planned.currency,
        unit=planned.unit,
        unit_price_snapshot=planned.unit_price_snapshot,
        estimated_cost=planned.estimated_cost,
        actual_cost=Decimal("0"),
    )


def _completed_billing(
    *,
    planned: ProviderBillingV1 | None,
    reported: ProviderBillingV1 | None,
) -> ProviderBillingV1:
    if planned is None:
        return reported or ProviderBillingV1(status="not_billable")
    if planned.status not in {"not_billable", "estimated"}:
        raise ValueError("Provider planned Billing 必须为 not_billable 或 estimated")
    if planned.status == "not_billable":
        if reported is None or reported.status == "not_billable":
            return ProviderBillingV1(status="not_billable")
        raise ValueError("not_billable Attempt 不能在响应后变为计费 Attempt")

    if reported is None:
        return planned
    if reported.status == "not_billable":
        return reported
    if reported.status == "unknown":
        raise ValueError("确定响应不能使用 unknown Billing")
    if reported.currency is not None and reported.currency != planned.currency:
        raise ValueError("Provider Billing 币种与发送前价格快照不一致")
    if reported.unit is not None and reported.unit != planned.unit:
        raise ValueError("Provider Billing 单位与发送前价格快照不一致")
    if reported.status == "estimated":
        if reported.actual_cost != 0:
            raise ValueError("estimated Billing 不能携带非零 actual_cost")
        return planned
    return ProviderBillingV1(
        status="confirmed",
        currency=planned.currency,
        unit=planned.unit,
        unit_price_snapshot=planned.unit_price_snapshot,
        estimated_cost=planned.estimated_cost,
        actual_cost=reported.actual_cost,
    )


class ProviderClient:
    """通过注入 Transport 执行一次 Provider Attempt，不做隐藏网络重试。"""

    def __init__(
        self,
        *,
        transport: ProviderTransport,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def dispatch(
        self,
        *,
        request: ProviderRequestV1,
        attempt_id: UUID,
        attempt_no: int,
        transport_request: ProviderTransportRequest,
        dispatch_started_at: datetime | None = None,
        planned_billing: ProviderBillingV1 | None = None,
    ) -> ProviderDispatchResult:
        """调用 Transport 恰好一次，并保留发送前价格快照形成终态 Attempt。"""
        if planned_billing is not None and planned_billing.status not in {
            "not_billable",
            "estimated",
        }:
            raise ValueError("发送前 planned Billing 必须为 not_billable 或 estimated")
        started_at = dispatch_started_at or self._clock()
        raw_request = RawRequestV1(
            transport_kind=transport_request.transport_kind,
            method=transport_request.method,
            path=_redacted_string(transport_request.path),
            params=_redacted_object(transport_request.params),
            headers=_redacted_object(transport_request.headers),
            body=redact_json(transport_request.body),
        )
        try:
            response = self._transport.send(transport_request)
        except ProviderTransportFailure as failure:
            completed_at = self._clock()
            if failure.delivery == "not_sent":
                attempt = ProviderAttemptV1(
                    attempt_id=attempt_id,
                    provider_request_id=request.request_id,
                    attempt_no=attempt_no,
                    dispatch_status="not_sent",
                    completed_at=completed_at,
                    billing=failure.billing,
                    error=ProviderErrorV1(
                        category="transient",
                        code=failure.code,
                        safe_summary=_redacted_string(failure.safe_summary),
                        retryable=True,
                    ),
                    created_at=started_at,
                )
            else:
                attempt = ProviderAttemptV1(
                    attempt_id=attempt_id,
                    provider_request_id=request.request_id,
                    attempt_no=attempt_no,
                    dispatch_status="unknown",
                    dispatch_started_at=started_at,
                    completed_at=completed_at,
                    billing=_unknown_billing_with_planned_snapshot(
                        planned=planned_billing,
                        reported=failure.billing,
                    ),
                    potential_duplicate_charge=True,
                    error=ProviderErrorV1(
                        category="unknown",
                        code=failure.code,
                        safe_summary=_redacted_string(failure.safe_summary),
                        retryable=True,
                    ),
                    created_at=started_at,
                )
            return ProviderDispatchResult(
                request=request,
                attempt=attempt,
                raw_request=raw_request,
                raw_response=None,
            )

        completed_at = self._clock()
        error = _classify_http_error(response.status_code) if response.status_code else None
        external_request_id = (
            _redacted_string(response.external_request_id)
            if response.external_request_id is not None
            else None
        )
        attempt = ProviderAttemptV1(
            attempt_id=attempt_id,
            provider_request_id=request.request_id,
            attempt_no=attempt_no,
            dispatch_status="completed",
            dispatch_started_at=started_at,
            completed_at=completed_at,
            http_status=response.status_code,
            external_request_id=external_request_id,
            billing=_completed_billing(planned=planned_billing, reported=response.billing),
            error=error,
            created_at=started_at,
        )
        raw_response = RawResponseV1(
            status_code=response.status_code,
            external_request_id=external_request_id,
            body=redact_json(response.body),
        )
        return ProviderDispatchResult(
            request=request,
            attempt=attempt,
            raw_request=raw_request,
            raw_response=raw_response,
        )
