"""不访问网络的 Provider Transport Fake。"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportFailure,
    ProviderTransportRequest,
    ProviderTransportResponse,
)


class FakeProviderTransport:
    """按脚本返回响应/失败；只保留移除 credential 的请求快照。"""

    def __init__(
        self,
        outcomes: Iterable[ProviderTransportResponse | ProviderTransportFailure],
    ) -> None:
        self._outcomes = deque(outcomes)
        self.call_count = 0
        self.seen_requests: list[ProviderTransportRequest] = []

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        self.call_count += 1
        self.seen_requests.append(request.model_copy(update={"credential": None}))
        if not self._outcomes:
            raise AssertionError("FakeProviderTransport 没有剩余脚本结果")
        outcome = self._outcomes.popleft()
        if isinstance(outcome, ProviderTransportFailure):
            raise outcome
        return outcome
