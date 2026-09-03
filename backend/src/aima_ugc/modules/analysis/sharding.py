"""Analysis Run 根据冻结 Provider 并发自动推导 Shard 大小。"""

from __future__ import annotations

ANALYSIS_TARGET_WAVES_PER_SHARD = 20
ANALYSIS_MIN_SHARD_SIZE = 20
ANALYSIS_MAX_SHARD_SIZE = 50_000


def calculate_analysis_shard_size(max_concurrency: int) -> int:
    """让一个 Shard 约包含固定请求波次，并以内部上下限控制 Job 粒度。"""

    if (
        isinstance(max_concurrency, bool)
        or not isinstance(max_concurrency, int)
        or max_concurrency <= 0
    ):
        raise ValueError("max_concurrency 必须是大于 0 的整数")
    calculated = max_concurrency * ANALYSIS_TARGET_WAVES_PER_SHARD
    return max(ANALYSIS_MIN_SHARD_SIZE, min(calculated, ANALYSIS_MAX_SHARD_SIZE))


__all__ = [
    "ANALYSIS_MAX_SHARD_SIZE",
    "ANALYSIS_MIN_SHARD_SIZE",
    "ANALYSIS_TARGET_WAVES_PER_SHARD",
    "calculate_analysis_shard_size",
]
