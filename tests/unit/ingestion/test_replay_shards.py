"""Replay 分片数量遵守单路起步和重复读取成本的边界。"""

import pytest
from aima_ugc.modules.ingestion.canonical_replay import CANONICAL_REPLAY_BACKGROUND_PRIORITY
from aima_ugc.modules.ingestion.replay_shards import (
    REPLAY_SHARD_JOB_PRIORITY,
    select_replay_shard_count,
)


@pytest.mark.parametrize(
    ("compressed_mib", "workers", "expected"),
    [(0, 8, 1), (2, 8, 1), (4, 8, 1), (5, 1, 1), (5, 2, 3), (20, 2, 4), (20, 8, 10)],
)
def test_replay_shard_count_preserves_room_for_an_in_run_probe(
    compressed_mib: int, workers: int, expected: int
) -> None:
    assert (
        select_replay_shard_count(
            compressed_bytes=compressed_mib * 1024 * 1024,
            available_workers=workers,
            sampled_rows=100,
            matched_rows=100,
        )
        == expected
    )


def test_replay_shard_count_rejects_invalid_resource_inputs() -> None:
    with pytest.raises(ValueError):
        select_replay_shard_count(
            compressed_bytes=-1, available_workers=2, sampled_rows=100, matched_rows=100
        )
    with pytest.raises(ValueError):
        select_replay_shard_count(
            compressed_bytes=1024, available_workers=0, sampled_rows=100, matched_rows=100
        )


@pytest.mark.parametrize(("sampled", "matched"), [(0, 0), (63, 63), (100, 49)])
def test_replay_shards_skip_low_confidence_or_low_match_input(sampled: int, matched: int) -> None:
    assert (
        select_replay_shard_count(
            compressed_bytes=20 * 1024 * 1024,
            available_workers=8,
            sampled_rows=sampled,
            matched_rows=matched,
        )
        == 1
    )



def test_replay_shard_priority_is_background_work() -> None:
    """Replay 子任务不能再以高于正常 Collection 的优先级抢占 Worker。"""

    assert CANONICAL_REPLAY_BACKGROUND_PRIORITY < 0
    assert REPLAY_SHARD_JOB_PRIORITY == CANONICAL_REPLAY_BACKGROUND_PRIORITY
