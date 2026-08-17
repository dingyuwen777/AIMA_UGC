"""TikHub 生产 HTTP Transport；一次 send 恰好一次网络请求。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportFailure,
    ProviderTransportRequest,
    ProviderTransportResponse,
)

DEFAULT_TIKHUB_BASE_URL = "https://api.tikhub.io"
_ALLOWED_TIKHUB_HOST = "api.tikhub.io"
_REQUEST_ID_HEADERS = (
    "x-request-id",
    "x-tikhub-request-id",
    "request-id",
)


class TikHubHttpTransport:
    """把脱敏 Transport Request 发送到 TikHub，不复制 Operation 与重试逻辑。"""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_TIKHUB_BASE_URL,
        timeout_seconds: float = 45.0,
        client: httpx.Client | None = None,
    ) -> None:
        actual_base_url = str(client.base_url) if client is not None else base_url
        normalized_base_url = _validate_tikhub_base_url(actual_base_url)
        if timeout_seconds <= 0:
            raise ValueError("TikHub timeout_seconds 必须大于 0")
        self._base_url = normalized_base_url
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=normalized_base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> TikHubHttpTransport:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        """发送一次确定请求；连接前失败与发送后未知状态分开建模。"""
        if request.transport_kind != "http" or request.method is None:
            raise ProviderTransportFailure.not_sent(
                code="tikhub_invalid_transport",
                safe_summary="TikHub Transport 只接受 HTTP 请求",
            )
        credential = request.credential
        if credential is None:
            raise ProviderTransportFailure.not_sent(
                code="tikhub_missing_credential",
                safe_summary="TikHub 请求缺少凭据",
            )

        headers = _http_headers(request.headers)
        headers["Authorization"] = f"Bearer {credential.get_secret_value()}"
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", "AIMA_UGC/1.0")

        try:
            response = self._client.request(
                request.method,
                request.path,
                params=_http_query_params(request.params),
                headers=headers,
                json=request.body,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ProviderTransportFailure.not_sent(
                code="tikhub_connect_failed",
                safe_summary="TikHub 连接建立失败",
            ) from exc
        except (
            httpx.ReadError,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.WriteError,
            httpx.WriteTimeout,
        ) as exc:
            raise ProviderTransportFailure.unknown(
                code="tikhub_delivery_unknown",
                safe_summary="TikHub 请求发送状态未知",
                currency="USD",
                unit="request",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderTransportFailure.unknown(
                code="tikhub_http_transport_failed",
                safe_summary="TikHub HTTP Transport 失败且发送状态无法确认",
                currency="USD",
                unit="request",
            ) from exc

        try:
            body: Any = response.json()
        except ValueError:
            body = response.text

        return ProviderTransportResponse(
            status_code=response.status_code,
            external_request_id=_external_request_id(response.headers),
            body=body,
        )


def build_tikhub_transport_request(
    operation_request: object,
    *,
    credential: SecretStr,
) -> ProviderTransportRequest:
    """把各平台生产 Operation Request 转为统一 Transport Request，不复制 endpoint。"""
    path = getattr(operation_request, "path", None)
    params = getattr(operation_request, "params", None)
    method = getattr(operation_request, "method", "GET")
    body = getattr(operation_request, "body", None)
    if not isinstance(path, str) or not path.startswith("/api/"):
        raise ValueError("TikHub Operation Request 缺少合法 /api/ path")
    if not isinstance(params, dict):
        raise ValueError("TikHub Operation Request params 必须为对象")
    if method not in {"GET", "POST"}:
        raise ValueError("TikHub Operation Request 当前只支持 GET/POST")
    return ProviderTransportRequest(
        transport_kind="http",
        method=method,
        path=path,
        params=params,
        body=body,
        credential=credential,
    )


_HttpQueryValue = str | int | float | bool | None


def _validate_tikhub_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("TikHub base_url 必须使用受允许的 HTTPS Origin") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != _ALLOWED_TIKHUB_HOST
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("TikHub base_url 必须使用受允许的 https://api.tikhub.io")
    return normalized


def _http_query_params(params: Mapping[str, object]) -> dict[str, _HttpQueryValue]:
    converted: dict[str, _HttpQueryValue] = {}
    for key, value in params.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            converted[str(key)] = value
            continue
        raise ProviderTransportFailure.not_sent(
            code="tikhub_invalid_query_param",
            safe_summary="TikHub query 参数类型不受支持",
        )
    return converted


def _http_headers(headers: Mapping[str, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in headers.items()}


def _external_request_id(headers: httpx.Headers) -> str | None:
    for key in _REQUEST_ID_HEADERS:
        value = headers.get(key)
        if value:
            return str(value)
    return None


__all__ = [
    "DEFAULT_TIKHUB_BASE_URL",
    "TikHubHttpTransport",
    "build_tikhub_transport_request",
]
