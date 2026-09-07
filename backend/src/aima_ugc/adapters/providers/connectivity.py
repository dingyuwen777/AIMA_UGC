"""管理员 Provider“测试连接”的最小无业务副作用 HTTP Adapter。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from pydantic import SecretStr

from aima_ugc.adapters.providers.tikhub.transport import _validate_tikhub_base_url
from aima_ugc.modules.system.models import ProviderConfig


class ProviderConnectionTestUnsupported(ValueError):
    """当前 Provider 没有已验证的无业务副作用连接测试入口。"""


@dataclass(frozen=True, slots=True)
class ProviderConnectionTestResult:
    """不包含 Secret/原始响应体的连接测试安全结果。"""

    ok: bool
    message: str
    latency_ms: int | None


def test_provider_connection(
    config: ProviderConfig,
    credential: SecretStr,
    *,
    client: httpx.Client | None = None,
) -> ProviderConnectionTestResult:
    """验证鉴权和服务可达性；TikHub 不触发采集，LLM 不触发推理。"""

    if config.provider_kind == "collection":
        if config.provider != "tikhub":
            raise ProviderConnectionTestUnsupported(
                "该采集 Provider 尚未定义无业务副作用的连接测试"
            )
        try:
            safe_base_url = _validate_tikhub_base_url(config.base_url)
        except ValueError as exc:
            raise ProviderConnectionTestUnsupported("TikHub 服务地址不在允许范围内") from exc
        path = "/api/v1/tikhub/user/get_user_info"
        url = urljoin(safe_base_url.rstrip("/") + "/", path.lstrip("/"))
    elif config.provider_kind == "llm":
        # OpenAI-compatible Base URL 已由 ProviderConfig 拒绝 credential/query/fragment；
        # 通常包含 /v1，因此这里只在既有路径后拼接 metadata-only /models。
        url = f"{config.base_url.rstrip('/')}/models"
    else:  # pragma: no cover - ProviderConfig Literal/领域校验双保险
        raise ProviderConnectionTestUnsupported("Provider 类型不支持连接测试")

    owns_client = client is None
    actual_client = client or httpx.Client(
        timeout=httpx.Timeout(min(float(config.timeout_seconds), 15.0)),
        follow_redirects=False,
        trust_env=False,
    )
    started = time.monotonic()
    try:
        try:
            response = actual_client.get(
                url,
                headers={
                    "Authorization": f"Bearer {credential.get_secret_value()}",
                    "Accept": "application/json",
                    "User-Agent": "AIMA_UGC/1.0",
                },
            )
        except httpx.ConnectError, httpx.ConnectTimeout:
            return ProviderConnectionTestResult(False, "无法连接服务地址", None)
        except httpx.TimeoutException:
            return ProviderConnectionTestResult(False, "服务响应超时", None)
        except httpx.HTTPError:
            return ProviderConnectionTestResult(False, "连接测试失败", None)
        latency_ms = max(0, round((time.monotonic() - started) * 1000))
        if response.status_code in {401, 403}:
            return ProviderConnectionTestResult(False, "认证失败，请检查 API Key", latency_ms)
        if not 200 <= response.status_code < 300:
            return ProviderConnectionTestResult(
                False,
                f"服务返回 HTTP {response.status_code}",
                latency_ms,
            )
        if config.provider_kind == "collection":
            try:
                payload = response.json()
            except ValueError:
                return ProviderConnectionTestResult(False, "服务响应格式不正确", latency_ms)
            if not isinstance(payload, dict) or payload.get("code") != 200:
                return ProviderConnectionTestResult(
                    False, "TikHub 未确认当前 API Key 可用", latency_ms
                )
        return ProviderConnectionTestResult(True, "连接成功", latency_ms)
    finally:
        if owns_client:
            actual_client.close()


__all__ = [
    "ProviderConnectionTestResult",
    "ProviderConnectionTestUnsupported",
    "test_provider_connection",
]
