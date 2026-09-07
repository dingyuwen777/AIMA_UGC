"""Provider 管理连接测试只验证鉴权/可达性，不触发业务调用。"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from aima_ugc.adapters.providers.connectivity import (
    ProviderConnectionTestUnsupported,
    test_provider_connection as run_provider_connection,
)
from aima_ugc.modules.system.models import ProviderConfig


def _config(*, provider_kind: str, provider: str, base_url: str, model: str | None = None) -> ProviderConfig:
    return ProviderConfig(
        id=uuid4(),
        provider=provider,
        provider_kind=provider_kind,  # type: ignore[arg-type]
        display_name="测试 Provider",
        base_url=base_url,
        model=model,
        secret_ref="providers/test/key.txt",
        timeout_seconds=45,
        max_retries=0,
        max_concurrency=1,
        enabled=False,
    )


def test_tikhub_connection_uses_current_user_endpoint_without_collection_params() -> None:
    """TikHub 连接测试只能访问账户信息端点，不带搜索/内容采集参数。"""

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"balance": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = run_provider_connection(
            _config(
                provider_kind="collection",
                provider="tikhub",
                base_url="https://api.tikhub.io",
            ),
            SecretStr("unit-test-secret"),
            client=client,
        )
    finally:
        client.close()

    assert result.ok is True
    assert result.message == "连接成功"
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/api/v1/tikhub/user/get_user_info"
    assert seen[0].url.query == b""
    assert seen[0].content == b""
    assert seen[0].headers["authorization"] == "Bearer unit-test-secret"


def test_tikhub_connection_rejects_untrusted_origin_before_http() -> None:
    """TikHub API Key 不能被发送到生产 Transport 不允许的 Origin。"""

    with pytest.raises(ProviderConnectionTestUnsupported, match="允许范围"):
        run_provider_connection(
            _config(
                provider_kind="collection",
                provider="tikhub",
                base_url="https://example.com",
            ),
            SecretStr("unit-test-secret"),
        )


def test_llm_connection_uses_models_metadata_endpoint_without_inference_body() -> None:
    """OpenAI-compatible LLM 只请求 /models，不创建 completion/chat 推理。"""

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"object": "list", "data": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = run_provider_connection(
            _config(
                provider_kind="llm",
                provider="deepseek",
                base_url="https://llm.example.test/v1",
                model="example-model",
            ),
            SecretStr("unit-test-secret"),
            client=client,
        )
    finally:
        client.close()

    assert result.ok is True
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/v1/models"
    assert seen[0].content == b""


def test_connection_failure_does_not_return_upstream_body_or_secret() -> None:
    """认证失败只返回安全业务提示，不透传第三方响应正文。"""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="secret-looking upstream diagnostics")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = run_provider_connection(
            _config(
                provider_kind="llm",
                provider="deepseek",
                base_url="https://llm.example.test/v1",
                model="example-model",
            ),
            SecretStr("unit-test-secret"),
            client=client,
        )
    finally:
        client.close()

    assert result.ok is False
    assert result.message == "认证失败，请检查 API Key"
    assert "secret-looking" not in result.message
    assert "unit-test-secret" not in result.message
