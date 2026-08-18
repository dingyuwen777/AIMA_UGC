"""Collection 生产执行技术上限与 Job Deadline sizing。

这些值只用于技术分页防护和 Deadline 容量下限，不是费用/请求 Budget，也不在发送前拦截请求。
"""

MAX_SEARCH_PAGES = 100
MAX_COMMENT_PAGES = 100
MAX_SUB_COMMENT_PAGES = 100
DEADLINE_SAFETY_PERCENT = 20
MIN_DEADLINE_SAFETY_SECONDS = 60


def provider_execution_window_floor_seconds(
    *, scope_count: int, request_timeout_seconds: float
) -> int:
    """按 Scope 数、技术分页深度和单请求 timeout 推导有限 Deadline 下限。"""
    if scope_count < 1:
        raise ValueError("scope_count 必须至少为 1")
    if request_timeout_seconds <= 0:
        raise ValueError("request_timeout_seconds 必须大于 0")
    depth_per_scope = MAX_SEARCH_PAGES + MAX_COMMENT_PAGES + MAX_SUB_COMMENT_PAGES
    base_seconds = max(1, int(scope_count * depth_per_scope * request_timeout_seconds))
    percentage_margin = (base_seconds * DEADLINE_SAFETY_PERCENT + 99) // 100
    return base_seconds + max(MIN_DEADLINE_SAFETY_SECONDS, percentage_margin)


__all__ = [
    "DEADLINE_SAFETY_PERCENT",
    "MAX_COMMENT_PAGES",
    "MAX_SEARCH_PAGES",
    "MAX_SUB_COMMENT_PAGES",
    "MIN_DEADLINE_SAFETY_SECONDS",
    "provider_execution_window_floor_seconds",
]
