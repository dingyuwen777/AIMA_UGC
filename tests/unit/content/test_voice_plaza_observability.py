"""声音广场读取阶段日志回归。"""

from contextlib import nullcontext
import logging
from time import perf_counter
from types import SimpleNamespace
from typing import cast

import pytest
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.bootstrap.product_http import PostgresProductHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.contracts.http import ContentCountRequest


class _FakeSession:
    """为 Count 可观测性测试提供最小事务与关闭边界。"""

    def begin(self):  # type: ignore[no-untyped-def]
        """返回无需数据库副作用的上下文管理器。"""

        return nullcontext()

    def close(self) -> None:
        """匹配正式 Session 生命周期。"""


class _FakeCountRepository:
    """返回投影就绪后的精确计数，避免单元测试连接数据库。"""

    def __init__(self, session, *, analysis_identity):  # type: ignore[no-untyped-def]
        """接受正式 Repository 的构造参数。"""

    @property
    def last_projection_ready(self) -> bool:
        """声明本次 Count 使用已就绪投影。"""

        return True

    def display_count(self, filters):  # type: ignore[no-untyped-def]
        """返回确定的精确数量供日志断言。"""

        return 42, "exact"


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


def test_voice_plaza_count_emits_projection_and_filter_shape_without_values(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Count 日志只暴露筛选形状和阶段耗时，不泄露真实筛选值。"""

    logger = logging.getLogger("test.voice_plaza.count_observability")
    runtime = cast(
        PlatformRuntime,
        SimpleNamespace(
            logger=logger,
            settings=SimpleNamespace(),
            database=SimpleNamespace(new_session=_FakeSession),
        ),
    )
    monkeypatch.setattr(
        "aima_ugc.bootstrap.product_http.active_analysis_configuration",
        lambda session, settings: SimpleNamespace(identity=None),
    )
    monkeypatch.setattr(
        "aima_ugc.bootstrap.product_http.PostgresContentProductRepository",
        _FakeCountRepository,
    )

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        response = PostgresProductHttpService(runtime).count_contents(
            ContentCountRequest(
                count_mode="estimated",
                filters={"platforms": ["douyin"], "search": "不得进入日志的筛选词"},
            )
        )

    assert (response.count, response.count_kind) == (42, "exact")
    record = next(
        item
        for item in caplog.records
        if getattr(item, "event", None) == "voice_plaza.read_completed"
        and getattr(item, "operation", None) == "count"
    )
    assert record.projection_ready is True
    assert record.count_kind == "exact"
    assert record.filter_fields == ("platforms", "search")
    assert record.configuration_ms >= 0
    assert record.query_ms >= 0
    assert not hasattr(record, "search")
    assert "不得进入日志的筛选词" not in caplog.text
