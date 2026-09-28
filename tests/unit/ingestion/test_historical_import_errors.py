"""历史导入 Worker 对临时数据库故障的恢复分类。"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.historical_import_worker import PostgresHistoricalImportJobExecutor
from aima_ugc.modules.ingestion.historical_jobs import HistoricalImportChunkJobPayload
from aima_ugc.platform.capacity import AdaptiveBatchController
from aima_ugc.platform.jobs import JobExecutionFence
from sqlalchemy.exc import OperationalError


def test_chunk_database_operational_error_is_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    """数据库死锁等临时故障应交给持久 Job 退避重试，不能使 Worker 直接中断。"""

    executor = object.__new__(PostgresHistoricalImportJobExecutor)
    executor._runtime = SimpleNamespace(logger=logging.getLogger(__name__))  # type: ignore[assignment]
    executor._sql_batch_tuner = AdaptiveBatchController(lower=250, upper=500)

    def fail_load(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OperationalError("SELECT", {}, RuntimeError("deadlock detected"))

    monkeypatch.setattr(executor, "_load_import_chunk", fail_load)
    result = executor.import_chunk(
        payload=HistoricalImportChunkJobPayload(batch_id=uuid4(), chunk_item_id=uuid4()),
        fence=JobExecutionFence(job_id=uuid4(), lease_token="unit-test-fence"),
        context=object(),  # type: ignore[arg-type]
    )

    assert result.outcome == "retry"
    assert result.error_code == "historical_chunk_database_transient"
