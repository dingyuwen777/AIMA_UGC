"""TikHub Operation Probe 必须在发送前核验价格、请求数和费用上限。"""

from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from aima_ugc.adapters.providers.tikhub.operations.douyin import build_video_detail_request
from aima_ugc.adapters.providers.tikhub.probe import (
    TikHubOperationProbe,
    TikHubProbeLimitError,
    TikHubProbeLimits,
)
from aima_ugc.adapters.providers.tikhub.transport import TikHubHttpTransport


def _transport(calls: list[httpx.Request]) -> TikHubHttpTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"aweme_detail": {}}})

    return TikHubHttpTransport(
        client=httpx.Client(
            base_url="https://api.tikhub.io",
            transport=httpx.MockTransport(handler),
        )
    )


def test_probe_uses_verified_price_and_tracks_conservative_cost_before_send() -> None:
    calls: list[httpx.Request] = []
    probe = TikHubOperationProbe(
        transport=_transport(calls),
        credential=SecretStr("probe-secret"),
        limits=TikHubProbeLimits(
            max_requests=2,
            max_estimated_cost=Decimal("0.002"),
        ),
    )

    result = probe.execute(build_video_detail_request(aweme_id="aweme-1"))

    assert len(calls) == 1
    assert result.path == "/api/v1/douyin/app/v3/fetch_one_video_v3"
    assert result.planned_cost == Decimal("0.001000")
    assert result.cumulative_planned_cost == Decimal("0.001000")
    assert probe.request_count == 1


def test_probe_rejects_request_or_cost_limit_before_http_send() -> None:
    calls: list[httpx.Request] = []
    request = build_video_detail_request(aweme_id="aweme-1")

    request_limited = TikHubOperationProbe(
        transport=_transport(calls),
        credential=SecretStr("probe-secret"),
        limits=TikHubProbeLimits(
            max_requests=1,
            max_estimated_cost=Decimal("0.010"),
        ),
    )
    request_limited.execute(request)
    with pytest.raises(TikHubProbeLimitError, match="请求数"):
        request_limited.execute(request)
    assert len(calls) == 1

    calls.clear()
    cost_limited = TikHubOperationProbe(
        transport=_transport(calls),
        credential=SecretStr("probe-secret"),
        limits=TikHubProbeLimits(
            max_requests=2,
            max_estimated_cost=Decimal("0.0005"),
        ),
    )
    with pytest.raises(TikHubProbeLimitError, match="费用"):
        cost_limited.execute(request)
    assert calls == []
