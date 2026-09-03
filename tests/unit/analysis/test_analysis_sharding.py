"""Analysis Run 自动 Shard 策略回归。"""

from aima_ugc.modules.analysis.sharding import calculate_analysis_shard_size


def test_shard_size_tracks_provider_concurrency_without_admin_configuration() -> None:
    """Shard 大小按 Provider 并发自动计算并保持约 20 个请求波次。"""

    assert calculate_analysis_shard_size(250) == 5_000
    assert calculate_analysis_shard_size(1_000) == 20_000


def test_shard_size_has_internal_bounds() -> None:
    """极小/极大 Provider 并发不能产生失控的 Shard。"""

    assert calculate_analysis_shard_size(1) == 20
    assert calculate_analysis_shard_size(10_000) == 50_000
