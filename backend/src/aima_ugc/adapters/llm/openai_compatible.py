"""OpenAI-compatible Chat Completions Adapter；一次 complete 恰好一次 HTTP 请求。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Self
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import SecretStr

from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
)

from .pricing import (
    LLMCostCalculation,
    LLMModelPrice,
    LLMPriceNotConfiguredError,
    LLMPricingCatalog,
    LLMTokenUsage,
)
from .request_audit import LLMHTTPRequestAudit, LLMHTTPRequestStatus

DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS = 60.0
DEFAULT_OPENAI_COMPATIBLE_MAX_CONNECTIONS = 100
_RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class OpenAICompatibleLLMError(RuntimeError):
    """OpenAI-compatible HTTP/响应协议错误；消息不得回显 Secret 或 Provider body。"""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        self.error_code = error_code
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(message)


class OpenAICompatibleContentLabelingLLM:
    """实现 ContentLabelingLLMPort 的 OpenAI-compatible Chat Completions Adapter。"""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        provider_name: str | None = None,
        base_url: str = DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
        timeout_seconds: float = DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS,
        max_connections: int = DEFAULT_OPENAI_COMPATIBLE_MAX_CONNECTIONS,
        use_json_mode: bool = True,
        client: httpx.Client | None = None,
        pricing_catalog: LLMPricingCatalog | None = None,
        request_audit: Callable[[LLMHTTPRequestAudit], None] | None = None,
    ) -> None:
        actual_base_url = str(client.base_url) if client is not None else base_url
        normalized_base_url = _normalize_base_url(actual_base_url)
        actual_provider_name = (
            provider_name
            if provider_name is not None
            else _provider_name_from_base_url(normalized_base_url)
        )
        if timeout_seconds <= 0:
            raise ValueError("OpenAI-compatible timeout_seconds 必须大于 0")
        if (
            isinstance(max_connections, bool)
            or not isinstance(max_connections, int)
            or max_connections <= 0
        ):
            raise ValueError("OpenAI-compatible max_connections 必须是大于 0 的整数")
        if not model or model != model.strip():
            raise ValueError("OpenAI-compatible model 必须是非空且已清洗的字符串")
        if not actual_provider_name or actual_provider_name != actual_provider_name.strip():
            raise ValueError("OpenAI-compatible provider_name 必须是非空且已清洗的字符串")
        secret = api_key.get_secret_value()
        if not secret or secret != secret.strip():
            raise ValueError("OpenAI-compatible api_key 必须是非空且已清洗的字符串")

        self._api_key = api_key
        self._model = model
        self._provider_name = actual_provider_name
        self._use_json_mode = use_json_mode
        self._request_audit = request_audit
        self._price: LLMModelPrice | None = None
        self._pricing_unavailable_reason: str | None = None
        if pricing_catalog is None:
            self._pricing_unavailable_reason = "pricing_catalog_not_configured"
        else:
            try:
                self._price = pricing_catalog.price_for(
                    provider=actual_provider_name,
                    model=model,
                )
            except LLMPriceNotConfiguredError:
                self._pricing_unavailable_reason = "model_price_not_configured"
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=normalized_base_url,
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections,
            ),
            follow_redirects=False,
            trust_env=False,
        )

    @property
    def provider_name(self) -> str:
        """返回用于 Analysis 审计和 checkpoint 身份的稳定模型服务标识。"""

        return self._provider_name

    @property
    def model_name(self) -> str:
        """返回用于 Analysis 审计的模型名称。"""

        return self._model

    def close(self) -> None:
        """关闭由 Adapter 自己创建的 HTTP Client。"""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """发送一次 Chat Completions 请求；Transport Retry 由更外层显式策略负责。"""

        started_at = datetime.now(UTC)
        http_request_id = uuid4().hex
        logical_request_id = request.logical_request_id or http_request_id
        status: LLMHTTPRequestStatus = "network_error"
        status_code: int | None = None
        error_code: str | None = None
        usage = LLMTokenUsage(input_tokens=None, output_tokens=None)
        calculation: LLMCostCalculation | None = None
        cost_unavailable_reason = self._pricing_unavailable_reason
        body: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.prompt},
                {"role": "user", "content": _user_message(request)},
            ],
        }
        if self._use_json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            try:
                response = self._client.post(
                    "chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "User-Agent": "AIMA_UGC/1.0",
                    },
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise OpenAICompatibleLLMError(
                    "OpenAI-compatible LLM 网络请求失败",
                    error_code="network_error",
                    retryable=True,
                ) from exc

            status_code = response.status_code
            if status_code < 200 or status_code >= 300:
                raise OpenAICompatibleLLMError(
                    f"OpenAI-compatible LLM 请求失败: HTTP {status_code}",
                    error_code=f"http_{status_code}",
                    retryable=status_code in _RETRYABLE_HTTP_STATUS_CODES,
                    status_code=status_code,
                )

            try:
                payload: Any = response.json()
            except ValueError as exc:
                raise OpenAICompatibleLLMError(
                    "OpenAI-compatible LLM 返回了不可解析的 HTTP JSON",
                    error_code="invalid_http_json",
                    retryable=False,
                ) from exc

            usage = _usage(payload)
            calculation, cost_unavailable_reason = _calculate_cost(
                price=self._price,
                usage=usage,
                pricing_unavailable_reason=self._pricing_unavailable_reason,
            )
            raw_text = _response_content(payload)
            status = "completed"
            return ContentLabelingLLMResponse(
                raw_text=raw_text,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                input_cache_hit_tokens=usage.input_cache_hit_tokens,
                input_cache_miss_tokens=usage.input_cache_miss_tokens,
                cost_amount=calculation.amount if calculation is not None else None,
                cost_currency=calculation.currency if calculation is not None else None,
                pricing_snapshot_sha256=(
                    calculation.pricing_snapshot_sha256
                    if calculation is not None
                    else self._price.snapshot_sha256 if self._price is not None else None
                ),
                pricing_source_url=self._price.source_url if self._price is not None else None,
            )
        except OpenAICompatibleLLMError as exc:
            error_code = exc.error_code
            if exc.error_code == "network_error":
                status = "network_error"
            elif exc.status_code is not None:
                status = "http_error"
            else:
                status = "protocol_error"
            raise
        finally:
            if self._request_audit is not None:
                self._request_audit(
                    _request_audit_record(
                        http_request_id=http_request_id,
                        logical_request_id=logical_request_id,
                        provider=self._provider_name,
                        model=self._model,
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        status=status,
                        status_code=status_code,
                        error_code=error_code,
                        usage=usage,
                        price=self._price,
                        calculation=calculation,
                        cost_unavailable_reason=cost_unavailable_reason,
                    )
                )


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        raise ValueError("OpenAI-compatible base_url 不能为空")
    try:
        parsed = urlsplit(normalized)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("OpenAI-compatible base_url 不是合法 HTTP(S) URL") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("OpenAI-compatible base_url 必须是无凭据、query、fragment 的 HTTP(S) URL")
    return normalized + "/"


def _provider_name_from_base_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("OpenAI-compatible base_url 缺少 hostname")

    normalized_host = hostname.lower()
    display_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    default_port = 443 if parsed.scheme == "https" else 80
    if parsed.port is not None and parsed.port != default_port:
        return f"{display_host}:{parsed.port}"
    return display_host


def _user_message(request: ContentLabelingLLMRequest) -> str:
    payload: dict[str, object] = {"items": request.model_payload()}
    if request.previous_validation_error_codes:
        payload["previous_validation_error_codes"] = list(request.previous_validation_error_codes)
        payload["retry_instruction"] = (
            "上一响应未通过本地校验；仅修正列出的结构/标签错误，并重新返回整个当前批次。"
        )
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _protocol_error(
    message: str,
    *,
    error_code: str,
    retryable: bool = False,
) -> OpenAICompatibleLLMError:
    return OpenAICompatibleLLMError(
        message,
        error_code=error_code,
        retryable=retryable,
    )


def _response_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise _protocol_error(
            "OpenAI-compatible LLM 响应顶层必须是 JSON object",
            error_code="invalid_response_root",
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise _protocol_error(
            "OpenAI-compatible LLM 响应缺少 choices",
            error_code="missing_choices",
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise _protocol_error(
            "OpenAI-compatible LLM choices[0] 必须是 object",
            error_code="invalid_choice",
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise _protocol_error(
            "OpenAI-compatible LLM 响应缺少 message",
            error_code="missing_message",
        )
    content = message.get("content")
    if content is None or (isinstance(content, str) and not content.strip()):
        raise _protocol_error(
            "OpenAI-compatible LLM message.content 必须是非空字符串",
            error_code="invalid_message_content",
            retryable=True,
        )
    if not isinstance(content, str):
        raise _protocol_error(
            "OpenAI-compatible LLM message.content 必须是非空字符串",
            error_code="invalid_message_content",
        )
    return content


def _usage_token(payload: Any, key: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    value = usage.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _usage(payload: Any) -> LLMTokenUsage:
    return LLMTokenUsage(
        input_tokens=_usage_token(payload, "prompt_tokens"),
        output_tokens=_usage_token(payload, "completion_tokens"),
        input_cache_hit_tokens=_usage_token(payload, "prompt_cache_hit_tokens"),
        input_cache_miss_tokens=_usage_token(payload, "prompt_cache_miss_tokens"),
    )


def _calculate_cost(
    *,
    price: LLMModelPrice | None,
    usage: LLMTokenUsage,
    pricing_unavailable_reason: str | None,
) -> tuple[LLMCostCalculation | None, str | None]:
    if price is None:
        return None, pricing_unavailable_reason or "model_price_not_configured"
    try:
        return price.calculate(usage), None
    except ValueError as exc:
        return None, f"usage_not_calculable:{str(exc).strip()}"[:300]


def _request_audit_record(
    *,
    http_request_id: str,
    logical_request_id: str,
    provider: str,
    model: str,
    started_at: datetime,
    completed_at: datetime,
    status: LLMHTTPRequestStatus,
    status_code: int | None,
    error_code: str | None,
    usage: LLMTokenUsage,
    price: LLMModelPrice | None,
    calculation: LLMCostCalculation | None,
    cost_unavailable_reason: str | None,
) -> LLMHTTPRequestAudit:
    return LLMHTTPRequestAudit(
        http_request_id=http_request_id,
        logical_request_id=logical_request_id,
        provider=provider,
        model=model,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        status_code=status_code,
        error_code=error_code,
        input_tokens=usage.input_tokens,
        input_cache_hit_tokens=usage.input_cache_hit_tokens,
        input_cache_miss_tokens=usage.input_cache_miss_tokens,
        output_tokens=usage.output_tokens,
        input_per_million=price.input_per_million if price is not None else None,
        input_cache_hit_per_million=(
            price.input_cache_hit_per_million if price is not None else None
        ),
        input_cache_miss_per_million=(
            price.input_cache_miss_per_million if price is not None else None
        ),
        output_per_million=price.output_per_million if price is not None else None,
        pricing_source_url=price.source_url if price is not None else None,
        pricing_snapshot_sha256=price.snapshot_sha256 if price is not None else None,
        cost_amount=calculation.amount if calculation is not None else None,
        cost_currency=calculation.currency if calculation is not None else None,
        cost_unavailable_reason=(
            None
            if calculation is not None
            else cost_unavailable_reason or "usage_unavailable"
        ),
    )


__all__ = [
    "DEFAULT_OPENAI_COMPATIBLE_BASE_URL",
    "DEFAULT_OPENAI_COMPATIBLE_MAX_CONNECTIONS",
    "DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS",
    "OpenAICompatibleContentLabelingLLM",
    "OpenAICompatibleLLMError",
]
