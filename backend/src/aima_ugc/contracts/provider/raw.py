"""Provider-neutral Raw Envelope V1。"""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from .base import (
    JsonObject,
    OperationName,
    PlatformName,
    ProviderBaseModel,
    ProviderName,
    assert_redacted_json,
)
from .models import ProviderBillingV1, ProviderErrorV1


class RawRequestV1(ProviderBaseModel):
    """已递归脱敏的实际 Transport 请求证据。"""

    transport_kind: Literal["http", "sdk", "file"]
    method: str | None = Field(default=None, min_length=1, max_length=32)
    path: str = Field(min_length=1, max_length=2048)
    params: JsonObject = Field(default_factory=dict)
    headers: JsonObject = Field(default_factory=dict)
    body: JsonValue = None

    @model_validator(mode="after")
    def validate_http_method(self) -> Self:
        if self.transport_kind == "http" and self.method is None:
            raise ValueError("HTTP Raw Request 必须包含 method")
        assert_redacted_json(self.path, path="raw_request.path")
        assert_redacted_json(self.params, path="raw_request.params")
        assert_redacted_json(self.headers, path="raw_request.headers")
        assert_redacted_json(self.body, path="raw_request.body")
        return self


class RawResponseV1(ProviderBaseModel):
    """已递归脱敏的 Provider 响应证据。"""

    status_code: int | None = Field(default=None, ge=100, le=599)
    external_request_id: str | None = Field(default=None, min_length=1, max_length=512)
    body: JsonValue = None

    @model_validator(mode="after")
    def validate_redaction(self) -> Self:
        if self.external_request_id is not None:
            assert_redacted_json(
                self.external_request_id,
                path="raw_response.external_request_id",
            )
        assert_redacted_json(self.body, path="raw_response.body")
        return self


class RawEnvelopeV1(ProviderBaseModel):
    """Provider/平台无关、可回放的 Raw Artifact 文件格式。"""

    schema_version: Literal["provider-response.v1"] = "provider-response.v1"
    provider: ProviderName
    platform: PlatformName
    operation: OperationName
    request_id: UUID
    attempt_id: UUID
    run_id: UUID
    scope_id: UUID
    requested_at: AwareDatetime
    completed_at: AwareDatetime
    dispatch_status: Literal["completed", "unknown"]
    request: RawRequestV1
    response: RawResponseV1 | None = None
    billing: ProviderBillingV1
    error: ProviderErrorV1 | None = None

    @model_validator(mode="after")
    def validate_terminal_evidence(self) -> Self:
        if self.completed_at < self.requested_at:
            raise ValueError("Raw completed_at 不能早于 requested_at")
        if self.dispatch_status == "completed" and self.response is None:
            raise ValueError("completed Raw 必须包含 Provider 响应")
        if self.dispatch_status == "unknown":
            if self.error is None or self.error.category != "unknown":
                raise ValueError("unknown Raw 必须包含 unknown 安全错误")
            if self.billing.status != "unknown":
                raise ValueError("unknown Raw 必须记录未知费用")
        return self
