"""OpenAI-compatible Chat Completions Adapter；一次 complete 恰好一次 HTTP 请求。"""

from __future__ import annotations

import json
from typing import Any, Self
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
)

DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS = 60.0


class OpenAICompatibleLLMError(RuntimeError):
    """OpenAI-compatible HTTP/响应协议错误；消息不得回显 Secret 或 Provider body。"""


class OpenAICompatibleContentLabelingLLM:
    """实现 ContentLabelingLLMPort 的 OpenAI-compatible Chat Completions Adapter。"""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        provider_name: str,
        base_url: str = DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
        timeout_seconds: float = DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS,
        use_json_mode: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        actual_base_url = str(client.base_url) if client is not None else base_url
        normalized_base_url = _normalize_base_url(actual_base_url)
        if timeout_seconds <= 0:
            raise ValueError("OpenAI-compatible timeout_seconds 必须大于 0")
        if not model or model != model.strip():
            raise ValueError("OpenAI-compatible model 必须是非空且已清洗的字符串")
        if not provider_name or provider_name != provider_name.strip():
            raise ValueError("OpenAI-compatible provider_name 必须是非空且已清洗的字符串")
        secret = api_key.get_secret_value()
        if not secret or secret != secret.strip():
            raise ValueError("OpenAI-compatible api_key 必须是非空且已清洗的字符串")

        self._api_key = api_key
        self._model = model
        self._provider_name = provider_name
        self._use_json_mode = use_json_mode
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=normalized_base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )

    @property
    def provider_name(self) -> str:
        """返回用于 Analysis 审计的稳定 Provider 名称。"""

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
            raise OpenAICompatibleLLMError("OpenAI-compatible LLM 网络请求失败") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise OpenAICompatibleLLMError(
                f"OpenAI-compatible LLM 请求失败: HTTP {response.status_code}"
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise OpenAICompatibleLLMError(
                "OpenAI-compatible LLM 返回了不可解析的 HTTP JSON"
            ) from exc

        return ContentLabelingLLMResponse(
            raw_text=_response_content(payload),
            input_tokens=_usage_token(payload, "prompt_tokens"),
            output_tokens=_usage_token(payload, "completion_tokens"),
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


def _user_message(request: ContentLabelingLLMRequest) -> str:
    payload: dict[str, object] = {"items": request.model_payload()}
    if request.previous_validation_error_codes:
        payload["previous_validation_error_codes"] = list(
            request.previous_validation_error_codes
        )
        payload["retry_instruction"] = (
            "上一响应未通过本地校验；仅修正列出的结构/标签错误，并重新返回整个当前批次。"
        )
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _response_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise OpenAICompatibleLLMError("OpenAI-compatible LLM 响应顶层必须是 JSON object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAICompatibleLLMError("OpenAI-compatible LLM 响应缺少 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise OpenAICompatibleLLMError("OpenAI-compatible LLM choices[0] 必须是 object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise OpenAICompatibleLLMError("OpenAI-compatible LLM 响应缺少 message")
    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise OpenAICompatibleLLMError("OpenAI-compatible LLM message.content 必须是非空字符串")
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


__all__ = [
    "DEFAULT_OPENAI_COMPATIBLE_BASE_URL",
    "DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS",
    "OpenAICompatibleContentLabelingLLM",
    "OpenAICompatibleLLMError",
]
