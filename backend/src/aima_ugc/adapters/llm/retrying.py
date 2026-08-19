"""OpenAI-compatible LLM 显式 Transport Retry 包装层。"""

from __future__ import annotations

import random
import time
from threading import Lock

from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingLLMPort,
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
)

from .openai_compatible import OpenAICompatibleLLMError

DEFAULT_LLM_TRANSPORT_MAX_RETRIES = 4
_TRANSPORT_RETRY_BASE_DELAY_SECONDS = 1.0
_TRANSPORT_RETRY_MAX_DELAY_SECONDS = 30.0


class RetryingContentLabelingLLM:
    """在 Base Adapter 之外显式执行有界 Transport Retry。"""

    def __init__(
        self,
        *,
        inner: ContentLabelingLLMPort,
        max_retries: int = DEFAULT_LLM_TRANSPORT_MAX_RETRIES,
    ) -> None:
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("LLM transport max_retries 必须是大于等于 0 的整数")
        self._inner = inner
        self._max_retries = max_retries
        self._metrics_lock = Lock()
        self._total_requests = 0
        self._total_retries = 0

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def total_requests(self) -> int:
        with self._metrics_lock:
            return self._total_requests

    @property
    def total_retries(self) -> int:
        with self._metrics_lock:
            return self._total_retries

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """完成一个逻辑 Validation Attempt；Transient Transport 失败才重试。"""

        for transport_attempt in range(1, self._max_retries + 2):
            self._record_request()
            try:
                return self._inner.complete(request)
            except OpenAICompatibleLLMError as exc:
                if not exc.retryable or transport_attempt > self._max_retries:
                    raise
                self._record_retry()
                time.sleep(_retry_delay_seconds(transport_attempt))

        raise RuntimeError("LLM Transport Retry 状态异常")

    def _record_request(self) -> None:
        with self._metrics_lock:
            self._total_requests += 1

    def _record_retry(self) -> None:
        with self._metrics_lock:
            self._total_retries += 1


def _retry_delay_seconds(transport_attempt: int) -> float:
    base = min(
        _TRANSPORT_RETRY_MAX_DELAY_SECONDS,
        _TRANSPORT_RETRY_BASE_DELAY_SECONDS * (2 ** (transport_attempt - 1)),
    )
    return base * random.uniform(0.5, 1.0)


__all__ = [
    "DEFAULT_LLM_TRANSPORT_MAX_RETRIES",
    "RetryingContentLabelingLLM",
]
