"""Provider Request、Attempt、费用与安全错误 V1 Contract。"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from .base import (
    JsonObject,
    OperationName,
    PlatformName,
    ProviderBaseModel,
    ProviderName,
    StableCode,
    assert_redacted_json,
    assert_secret_free,
)

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def compute_request_fingerprint(
    *,
    operation: str,
    request_params: JsonObject,
    pagination_input: JsonObject,
) -> str:
    """对 Scope 内的 Operation、稳定参数和分页输入生成确定性 SHA-256。"""
    assert_secret_free(request_params, path="request_params")
    assert_secret_free(pagination_input, path="pagination_input")
    payload = {
        "operation": operation,
        "pagination_input": pagination_input,
        "request_params": request_params,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ProviderRequestV1(ProviderBaseModel):
    """一个 Provider Scope 内可幂等复用的逻辑请求。"""

    schema_version: Literal["provider-request.v1"] = "provider-request.v1"
    request_id: UUID
    run_id: UUID
    scope_id: UUID
    provider: ProviderName
    platform: PlatformName
    operation: OperationName
    request_fingerprint: Fingerprint
    request_params: JsonObject = Field(default_factory=dict)
    pagination_input: JsonObject = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        request_id: UUID,
        run_id: UUID,
        scope_id: UUID,
        provider: str,
        platform: str,
        operation: str,
        request_params: JsonObject | None = None,
        pagination_input: JsonObject | None = None,
    ) -> Self:
        """从稳定且无 Secret 的参数创建逻辑请求并计算 fingerprint。"""
        params = request_params or {}
        pagination = pagination_input or {}
        return cls(
            request_id=request_id,
            run_id=run_id,
            scope_id=scope_id,
            provider=provider,
            platform=platform,
            operation=operation,
            request_fingerprint=compute_request_fingerprint(
                operation=operation,
                request_params=params,
                pagination_input=pagination,
            ),
            request_params=params,
            pagination_input=pagination,
        )

    @model_validator(mode="after")
    def validate_fingerprint_and_secret_boundary(self) -> Self:
        assert_secret_free(self.request_params, path="request_params")
        assert_secret_free(self.pagination_input, path="pagination_input")
        expected = compute_request_fingerprint(
            operation=self.operation,
            request_params=self.request_params,
            pagination_input=self.pagination_input,
        )
        if self.request_fingerprint != expected:
            raise ValueError("request_fingerprint 与 Provider Request 参数不一致")
        return self


class ProviderBillingV1(ProviderBaseModel):
    """一次 Provider Attempt 的可审计费用快照。"""

    status: Literal["not_billable", "estimated", "confirmed", "unknown"]
    currency: Currency | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=64)
    unit_price_snapshot: Money = Decimal("0")
    estimated_cost: Money = Decimal("0")
    actual_cost: Money = Decimal("0")

    @model_validator(mode="after")
    def validate_billing_state(self) -> Self:
        if self.status == "not_billable" and any(
            amount != 0
            for amount in (self.unit_price_snapshot, self.estimated_cost, self.actual_cost)
        ):
            raise ValueError("not_billable 费用必须为零")
        if self.status == "confirmed" and self.currency is None:
            raise ValueError("confirmed 费用必须声明币种")
        return self


class ProviderErrorV1(ProviderBaseModel):
    """不包含响应原文或 Secret 的稳定 Provider 错误。"""

    category: Literal["rate_limited", "transient", "permanent", "invalid_response", "unknown"]
    code: StableCode
    safe_summary: str = Field(min_length=1, max_length=512)
    retryable: bool

    @model_validator(mode="after")
    def validate_safe_summary(self) -> Self:
        assert_redacted_json(self.safe_summary, path="provider_error.safe_summary")
        return self


class ProviderAttemptV1(ProviderBaseModel):
    """一次真实 Provider 执行的不可变状态快照。"""

    schema_version: Literal["provider-attempt.v1"] = "provider-attempt.v1"
    attempt_id: UUID
    provider_request_id: UUID
    attempt_no: int = Field(ge=1)
    dispatch_status: Literal["reserved", "dispatching", "completed", "not_sent", "unknown"]
    dispatch_started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    external_request_id: str | None = Field(default=None, min_length=1, max_length=512)
    raw_artifact_id: UUID | None = None
    billing: ProviderBillingV1 = Field(
        default_factory=lambda: ProviderBillingV1(status="not_billable")
    )
    potential_duplicate_charge: bool = False
    error: ProviderErrorV1 | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_dispatch_state(self) -> Self:
        started = self.dispatch_started_at
        completed = self.completed_at
        status = self.dispatch_status
        if self.external_request_id is not None:
            assert_redacted_json(
                self.external_request_id,
                path="provider_attempt.external_request_id",
            )
        if status == "reserved" and (started is not None or completed is not None):
            raise ValueError("reserved Attempt 不能已有发送或完成时间")
        if status == "dispatching" and (started is None or completed is not None):
            raise ValueError("dispatching Attempt 必须只有发送开始时间")
        if status == "not_sent" and (started is not None or completed is None):
            raise ValueError("not_sent Attempt 不能有发送开始时间且必须已完成")
        if status in {"completed", "unknown"} and (started is None or completed is None):
            raise ValueError(f"{status} Attempt 必须有发送和完成时间")
        if completed is not None and completed < self.created_at:
            raise ValueError("Attempt 完成时间不能早于创建时间")
        if started is not None and completed is not None and completed < started:
            raise ValueError("Attempt 完成时间不能早于发送开始时间")
        if status in {"reserved", "dispatching"} and self.raw_artifact_id is not None:
            raise ValueError("未完成 Attempt 不能关联 Raw Artifact")
        if status == "not_sent":
            if self.error is None or self.billing.status != "not_billable":
                raise ValueError("not_sent Attempt 必须有安全错误且不可计费")
            if self.potential_duplicate_charge:
                raise ValueError("not_sent Attempt 不能标记潜在重复计费")
        if status == "unknown":
            if self.error is None or self.error.category != "unknown":
                raise ValueError("unknown Attempt 必须有 unknown 安全错误")
            if self.billing.status != "unknown" or not self.potential_duplicate_charge:
                raise ValueError("unknown Attempt 必须保守记录未知费用和潜在重复计费")
        if status == "completed" and self.http_status is not None:
            if self.http_status >= 400 and self.error is None:
                raise ValueError("HTTP 错误响应必须保存安全错误")
            if self.http_status < 400 and self.error is not None:
                raise ValueError("成功 HTTP 响应不能同时保存 Provider 错误")
        return self


def terminal_attempt_with_raw(
    attempt: ProviderAttemptV1, raw_artifact_id: UUID
) -> ProviderAttemptV1:
    """在 Raw 完整落盘后返回关联 Artifact 的终态快照。"""
    if attempt.dispatch_status not in {"completed", "unknown"}:
        raise ValueError("只有 completed/unknown Attempt 可以关联 Raw Artifact")
    return attempt.model_copy(update={"raw_artifact_id": raw_artifact_id})
