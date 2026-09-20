"""声音广场读取阶段日志回归。"""

import logging
from time import perf_counter
from types import SimpleNamespace
from typing import cast

import pytest
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime


def test_slow_voice_plaza_read_emits_safe_structured_timing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("test.voice_plaza.observability")
    runtime = cast(PlatformRuntime, SimpleNamespace(logger=logger))
    service = PostgresContentHttpService(runtime)

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        service._log_read_timing(  # noqa: SLF001
            operation="list",
            started=perf_counter() - 0.6,
            query_ms=580,
            projection_ready=True,
            item_count=20,
        )

    record = next(
        item for item in caplog.records if getattr(item, "event", None) == "voice_plaza.read_slow"
    )
    assert record.levelno == logging.WARNING
    assert record.operation == "list"
    assert record.query_ms == 580
    assert record.projection_ready is True
    assert record.item_count == 20
    assert record.duration_ms >= 500
    assert not hasattr(record, "search")
    assert not hasattr(record, "payload")
