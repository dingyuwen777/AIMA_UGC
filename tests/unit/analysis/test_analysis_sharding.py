"""Analysis Run 自动 Shard 策略回归。"""

from aima_ugc.modules.analysis.content_analysis_job import CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS
from aima_ugc.modules.analysis.sharding import (
    ANALYSIS_RPS_SHARD_BUDGET_SECONDS,
    calculate_analysis_shard_size,
)


def test_shard_size_tracks_provider_concurrency_without_admin_configuration() -> None:
    """未配置 RPS 时按 Provider 并发自动计算并保持约 20 个请求波次。"""

    assert calculate_analysis_shard_size(250) == 5_000
    assert calculate_analysis_shard_size(1_000) == 20_000


def test_shard_size_has_internal_bounds() -> None:
    """极小/极大 Provider 并发不能产生失控的 Shard。"""

    assert calculate_analysis_shard_size(1) == 20
    assert calculate_analysis_shard_size(10_000) == 50_000


def test_shard_size_respects_rps_budget_below_job_timeout() -> None:
    """低 RPS Provider 必须收紧 Shard，避免正常一次请求/Content 就理论必超 Job timeout。"""

    assert ANALYSIS_RPS_SHARD_BUDGET_SECONDS < CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS
    assert calculate_analysis_shard_size(1_000, max_rps=1) == 900
    assert calculate_analysis_shard_size(250, max_rps=5) == 4_500
    assert calculate_analysis_shard_size(250, max_rps=10) == 5_000
