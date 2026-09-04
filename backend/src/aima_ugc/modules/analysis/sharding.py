"""Analysis Run 根据冻结 Provider 容量自动推导 Shard 大小。"""

from __future__ import annotations

ANALYSIS_TARGET_WAVES_PER_SHARD = 20
ANALYSIS_MIN_SHARD_SIZE = 20
ANALYSIS_MAX_SHARD_SIZE = 50_000
ANALYSIS_RPS_SHARD_BUDGET_SECONDS = 900


def calculate_analysis_shard_size(
    max_concurrency: int,
    *,
    max_rps: int | None = None,
) -> int:
    """按并发波次推导 Shard，并在配置 RPS 时收紧到 Job timeout 内的安全预算。"""

    if (
        isinstance(max_concurrency, bool)
        or not isinstance(max_concurrency, int)
        or max_concurrency <= 0
    ):
        raise ValueError("max_concurrency 必须是大于 0 的整数")
    if max_rps is not None and (
        isinstance(max_rps, bool) or not isinstance(max_rps, int) or max_rps <= 0
    ):
        raise ValueError("max_rps 必须为空或大于 0 的整数")

    calculated = max_concurrency * ANALYSIS_TARGET_WAVES_PER_SHARD
    if max_rps is not None:
        calculated = min(calculated, max_rps * ANALYSIS_RPS_SHARD_BUDGET_SECONDS)
    return max(ANALYSIS_MIN_SHARD_SIZE, min(calculated, ANALYSIS_MAX_SHARD_SIZE))


__all__ = [
    "ANALYSIS_MAX_SHARD_SIZE",
    "ANALYSIS_MIN_SHARD_SIZE",
    "ANALYSIS_RPS_SHARD_BUDGET_SECONDS",
    "ANALYSIS_TARGET_WAVES_PER_SHARD",
    "calculate_analysis_shard_size",
]
