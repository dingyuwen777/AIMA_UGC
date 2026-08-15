"""TikHub 显式真实 Operation Probe；复用生产 Transport 与 Pricing。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pydantic import SecretStr

from aima_ugc.modules.collection.providers.transport import ProviderTransportResponse

from .pricing import TikHubPricingCatalog, load_tikhub_pricing
from .transport import TikHubHttpTransport, build_tikhub_transport_request


class TikHubProbeLimitError(RuntimeError):
    """真实 Probe 将超过显式请求数或费用上限。"""


@dataclass(frozen=True, slots=True)
class TikHubProbeLimits:
    """一次显式 Probe 的硬上限；不用于生产业务预算。"""

    max_requests: int
    max_estimated_cost: Decimal

    def __post_init__(self) -> None:
        if self.max_requests <= 0:
            raise ValueError("TikHub Probe max_requests 必须大于 0")
        if self.max_estimated_cost <= 0:
            raise ValueError("TikHub Probe max_estimated_cost 必须大于 0")


@dataclass(frozen=True, slots=True)
class TikHubProbeResult:
    """一次真实 Probe 的非 Secret 执行元数据与确定响应。"""

    path: str
    request_no: int
    planned_cost: Decimal
    cumulative_planned_cost: Decimal
    response: ProviderTransportResponse


class TikHubOperationProbe:
    """显式执行受限 TikHub Operation；一次 execute 恰好最多发送一次 HTTP。"""

    def __init__(
        self,
        *,
        transport: TikHubHttpTransport,
        credential: SecretStr,
        limits: TikHubProbeLimits,
        pricing: TikHubPricingCatalog | None = None,
    ) -> None:
        self._transport = transport
        self._credential = credential
        self._limits = limits
        self._pricing = pricing or load_tikhub_pricing()
        self._request_count = 0
        self._planned_cost = Decimal("0")

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def cumulative_planned_cost(self) -> Decimal:
        return self._planned_cost

    def execute(self, operation_request: object) -> TikHubProbeResult:
        """先核验精确价格和硬上限，再通过生产 Transport 执行一次。"""
        transport_request = build_tikhub_transport_request(
            operation_request,
            credential=self._credential,
        )
        billing = self._pricing.billing_for_endpoint(transport_request.path)
        assert billing.estimated_cost is not None
        next_request_no = self._request_count + 1
        next_cost = self._planned_cost + billing.estimated_cost
        if next_request_no > self._limits.max_requests:
            raise TikHubProbeLimitError("TikHub Probe 请求数上限不足，发送前已拒绝")
        if next_cost > self._limits.max_estimated_cost:
            raise TikHubProbeLimitError("TikHub Probe 费用上限不足，发送前已拒绝")

        # 网络结果未知时也按已计划请求保守占用 Probe 上限，避免循环重试放大费用。
        self._request_count = next_request_no
        self._planned_cost = next_cost
        response = self._transport.send(transport_request)
        return TikHubProbeResult(
            path=transport_request.path,
            request_no=next_request_no,
            planned_cost=billing.estimated_cost,
            cumulative_planned_cost=next_cost,
            response=response,
        )


__all__ = [
    "TikHubOperationProbe",
    "TikHubProbeLimitError",
    "TikHubProbeLimits",
    "TikHubProbeResult",
]
