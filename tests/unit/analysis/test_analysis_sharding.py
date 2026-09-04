"""Analysis Run 自动 Shard 策略回归。"""

from dataclasses import replace
from uuid import UUID, uuid4

from aima_ugc.bootstrap.content_http import _analysis_shard_size
from aima_ugc.modules.analysis.content_analysis_job import CONTENT_ANALYSIS_JOB_TIMEOUT_SECONDS
from aima_ugc.modules.analysis.sharding import (
    ANALYSIS_RPS_SHARD_BUDGET_SECONDS,
    calculate_analysis_shard_size,
)
from aima_ugc.modules.system.models import ProviderConfig


def _provider(*, max_concurrency: int, max_rps: int | None) -> ProviderConfig:
    """构造正式数据库 LLM Provider，直接验证 HTTP Preview/Create 使用的 Shard helper。"""

    return ProviderConfig(
        id=uuid4(),
        provider="fake-rps",
        provider_kind="llm",
        display_name="RPS Shard Fake",
        base_url="https://fake.example/v1",
        secret_ref="providers/tests/fake-rps.key",
        model="fake-model",
        enabled=True,
        max_concurrency=max_concurrency,
        max_rps=max_rps,
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


def test_content_http_shard_size_uses_provider_rps() -> None:
    """Preview/Create 的正式数据库 Provider helper 必须把 max_rps 传入 Shard 计算。"""

    assert _analysis_shard_size(_provider(max_concurrency=1_000, max_rps=1)) == 900
    assert _analysis_shard_size(_provider(max_concurrency=250, max_rps=5)) == 4_500
    assert _analysis_shard_size(_provider(max_concurrency=250, max_rps=None)) == 5_000


def test_environment_provider_uses_the_same_automatic_shards() -> None:
    """本地环境产生的 Provider 也按容量分片，不能退回逐条串行执行。"""

    provider = replace(
        _provider(max_concurrency=10, max_rps=None),
        id=UUID("00000000-0000-4000-8000-000000000001"),
    )
    assert _analysis_shard_size(provider) == 200
