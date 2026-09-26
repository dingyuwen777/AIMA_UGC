"""Worker Pool 为非 Replay 工作保留执行能力。"""

from aima_ugc.entrypoints.worker_main import _foreground_supported_job_types
from aima_ugc.modules.ingestion.canonical_replay import (
    CANONICAL_REPLAY_JOB_TYPE,
    CANONICAL_REPLAY_PLAN_JOB_TYPE,
    CANONICAL_REPLAY_REVERSAL_JOB_TYPE,
)
from aima_ugc.modules.ingestion.replay_shards import REPLAY_SHARD_JOB_TYPE


def test_foreground_worker_excludes_long_replay_work_when_pool_can_reserve_capacity() -> None:
    """多进程池中保留 Worker 不领取 Replay 长任务，其余 Job 类型保持可领取。"""

    foreground_type = "collection.run.v1"
    all_types = (
        foreground_type,
        CANONICAL_REPLAY_PLAN_JOB_TYPE,
        CANONICAL_REPLAY_JOB_TYPE,
        REPLAY_SHARD_JOB_TYPE,
        CANONICAL_REPLAY_REVERSAL_JOB_TYPE,
    )

    assert _foreground_supported_job_types(all_types, maximum_processes=6) == (foreground_type,)


def test_single_process_worker_keeps_replay_executable() -> None:
    """只有一个 Worker 时不能为了保留槽位让 Replay 永久饥饿。"""

    all_types = ("collection.run.v1", CANONICAL_REPLAY_JOB_TYPE)

    assert _foreground_supported_job_types(all_types, maximum_processes=1) == all_types
