"""正式 Analysis Run 的持久可恢复失败协议。"""

from __future__ import annotations

import random

RECOVERY_MODE = "recovery.v2"
SUPPORTED_RECOVERY_MODES = frozenset({"recovery.v1", RECOVERY_MODE})
UNHEALTHY_SECONDS = 300
TRANSPORT_UNAVAILABLE = "llm_transport_unavailable"
VALIDATION_UNHEALTHY = "llm_validation_unhealthy"
OUTPUT_ERROR_CODES = frozenset(
    {
        "invalid_http_json",
        "invalid_response_root",
        "missing_choices",
        "invalid_choice",
        "missing_message",
        "invalid_message_content",
    }
)


def retry_delay_seconds(retry_count: int) -> float:
    """按连续恢复轮数退避，加 jitter 且最多等待 30 秒；不限制总次数。"""

    base = min(30.0, float(2 ** min(max(retry_count - 1, 0), 5)))
    return base * random.uniform(0.5, 1.0)
