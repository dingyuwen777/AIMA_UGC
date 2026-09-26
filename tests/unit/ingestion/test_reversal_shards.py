"""超大撤回请求不能按 Content 数量生成无界子 Job。"""

from aima_ugc.adapters.persistence.postgres.reversal_shards import select_reversal_shard_count
from aima_ugc.modules.ingestion.reversal_shards import (
    IMPORT_REVERSAL_SHARD_PRIORITY,
    REPLAY_REVERSAL_SHARD_PRIORITY,
)


def test_reversal_shards_keep_small_jobs_small_and_bound_large_campaigns_by_resources() -> None:
    assert select_reversal_shard_count(3_000, max_shards=32) == 2
    assert select_reversal_shard_count(10_000, max_shards=32) == 4
    assert select_reversal_shard_count(40_000_000, max_shards=32) == 32
    assert select_reversal_shard_count(40_000_000, max_shards=128) == 128



def test_replay_reversal_yields_without_lowering_import_reversal_priority() -> None:
    """只让 Replay 撤回成为后台工作，普通导入撤销维持原有优先级。"""

    assert IMPORT_REVERSAL_SHARD_PRIORITY == 40
    assert REPLAY_REVERSAL_SHARD_PRIORITY < 0
