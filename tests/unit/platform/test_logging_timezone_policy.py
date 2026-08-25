"""日志北京时间前缀不重复输出 timezone 文本。"""

import logging
from datetime import UTC, datetime

from aima_ugc.platform.logging import AimaLogFormatter


def test_log_prefix_omits_timezone_field_and_name() -> None:
    """日志已有北京时间墙钟后，不再输出 timezone 字段或 Asia/Shanghai 文本。"""
    record = logging.LogRecord(
        name="aima_ugc.test.logging.timezone",
        level=logging.INFO,
        pathname="/tmp/runtime.py",
        lineno=114,
        msg="时间策略",
        args=(),
        exc_info=None,
    )
    record.created = datetime(2026, 8, 25, 1, 44, 19, 257000, tzinfo=UTC).timestamp()

    line = AimaLogFormatter(service="api").format(record)

    assert line.startswith("[2026-08-25 09:44:19.257 runtime.py L114] [INFO] ")
    assert "timezone=" not in line
    assert "Asia/Shanghai" not in line
