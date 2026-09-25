"""超大撤回请求不能按 Content 数量生成无界子 Job。"""

from aima_ugc.adapters.persistence.postgres.reversal_shards import select_reversal_shard_count


def test_reversal_shards_keep_small_jobs_small_and_bound_large_campaigns_by_resources() -> None:
    assert select_reversal_shard_count(3_000, max_shards=32) == 2
    assert select_reversal_shard_count(10_000, max_shards=32) == 4
    assert select_reversal_shard_count(40_000_000, max_shards=32) == 32
    assert select_reversal_shard_count(40_000_000, max_shards=128) == 128
