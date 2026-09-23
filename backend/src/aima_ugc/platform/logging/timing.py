"""低噪声操作日志使用的单调阶段计时。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


class StageTimings:
    """只保存阶段名与耗时，避免业务输入进入诊断日志。"""

    def __init__(self) -> None:
        self._started = perf_counter()
        self.stage_ms: dict[str, float] = {}

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        """阶段失败时也保留已等待时间，供外层统一记录。"""

        started = perf_counter()
        try:
            yield
        finally:
            self.record_elapsed(stage, started)

    def record_elapsed(self, stage: str, started: float) -> None:
        """记录无法用上下文包裹的事务提交阶段。"""

        self.stage_ms[stage] = round((perf_counter() - started) * 1000, 3)

    @property
    def total_ms(self) -> float:
        """获取从开始到当前的整次操作耗时。"""

        return round((perf_counter() - self._started) * 1000, 3)
