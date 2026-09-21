"""声音广场读取链路共享的安全耗时日志。"""

from __future__ import annotations

import logging
from time import perf_counter

from aima_ugc.platform.logging import log_event


def elapsed_ms(started: float, finished: float) -> int:
    """把单调时钟差转换为非负毫秒。"""

    return max(0, round((finished - started) * 1000))


def log_voice_plaza_read_timing(
    logger: logging.Logger,
    *,
    operation: str,
    started: float,
    **fields: object,
) -> None:
    """记录安全的阶段耗时；慢查询提升到 WARNING，正常请求保持 DEBUG。"""

    duration_ms = elapsed_ms(started, perf_counter())
    log_event(
        logger,
        logging.WARNING if duration_ms >= 500 else logging.DEBUG,
        "voice_plaza.read_slow" if duration_ms >= 500 else "voice_plaza.read_completed",
        "声音广场读取超过阶段耗时阈值。" if duration_ms >= 500 else "声音广场读取完成。",
        operation=operation,
        duration_ms=duration_ms,
        **fields,
    )


__all__ = ["elapsed_ms", "log_voice_plaza_read_timing"]
