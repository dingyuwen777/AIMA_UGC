"""AIMA 自有 HTTP 输入时间解释回归。"""

from datetime import UTC, datetime, timedelta

from aima_ugc.contracts.http import ImportBatchListQuery


def test_http_time_filters_normalize_to_beijing_time() -> None:
    """带时区的 HTTP 时间筛选进入 AIMA Contract 后统一解释为北京时间。"""
    query = ImportBatchListQuery(
        created_from=datetime(2026, 8, 25, 1, 0, 0, tzinfo=UTC),
        created_to=datetime(2026, 8, 25, 2, 0, 0, tzinfo=UTC),
    )

    assert query.created_from is not None
    assert query.created_to is not None
    assert query.created_from.hour == 9
    assert query.created_to.hour == 10
    assert query.created_from.utcoffset() == timedelta(hours=8)
