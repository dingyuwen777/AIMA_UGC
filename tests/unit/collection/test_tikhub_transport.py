"""TikHub 生产 HTTP Transport 的 Secret、单次发送与失败边界测试。"""

from __future__ import annotations

import json

import httpx
import pytest
from aima_ugc.adapters.providers.tikhub.operations.douyin import build_video_search_request
from aima_ugc.adapters.providers.tikhub.transport import (
    DEFAULT_TIKHUB_BASE_URL,
    TikHubHttpTransport,
    build_tikhub_transport_request,
)
from aima_ugc.modules.collection.providers.transport import ProviderTransportFailure
from pydantic import SecretStr


def test_transport_rejects_non_tikhub_base_url_before_secret_send_boundary() -> None:
    with pytest.raises(ValueError, match="TikHub base_url"):
        TikHubHttpTransport(base_url="https://example.com")


def test_transport_injects_secret_only_at_send_boundary_and_sends_once() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"] == "Bearer probe-secret"
        assert request.url.path == "/api/v1/douyin/search/fetch_video_search_v2"
        assert json.loads(request.content)["keyword"] == "爱玛"
        return httpx.Response(
            200,
            json={"code": 200, "data": {"business_data": []}},
            headers={"x-request-id": "request-fixture-1"},
        )

    client = httpx.Client(
        base_url=DEFAULT_TIKHUB_BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    operation = build_video_search_request(keyword="爱玛")
    transport_request = build_tikhub_transport_request(
        operation,
        credential=SecretStr("probe-secret"),
    )

    assert transport_request.headers == {}
    assert "probe-secret" not in repr(transport_request)
    assert "credential" not in transport_request.model_dump()

    transport = TikHubHttpTransport(client=client)
    response = transport.send(transport_request)

    assert len(calls) == 1
    assert response.status_code == 200
    assert response.external_request_id == "request-fixture-1"
    assert response.body == {"code": 200, "data": {"business_data": []}}


def test_connect_failure_is_not_sent_and_read_failure_is_delivery_unknown() -> None:
    operation = build_video_search_request(keyword="爱玛")
    request = build_tikhub_transport_request(
        operation,
        credential=SecretStr("probe-secret"),
    )

    def connect_failure(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect failed", request=http_request)

    with pytest.raises(ProviderTransportFailure) as connect_error:
        TikHubHttpTransport(
            client=httpx.Client(
                base_url=DEFAULT_TIKHUB_BASE_URL,
                transport=httpx.MockTransport(connect_failure),
            )
        ).send(request)
    assert connect_error.value.delivery == "not_sent"
    assert connect_error.value.code == "tikhub_connect_failed"

    def read_failure(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=http_request)

    with pytest.raises(ProviderTransportFailure) as read_error:
        TikHubHttpTransport(
            client=httpx.Client(
                base_url=DEFAULT_TIKHUB_BASE_URL,
                transport=httpx.MockTransport(read_failure),
            )
        ).send(request)
    assert read_error.value.delivery == "unknown"
    assert read_error.value.code == "tikhub_delivery_unknown"
    assert read_error.value.billing.status == "unknown"
