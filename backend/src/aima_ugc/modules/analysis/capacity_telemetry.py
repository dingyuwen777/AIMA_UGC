"""按请求实际在途区间积分；未完成请求也参与当前观察窗。"""

from collections.abc import Callable
from time import monotonic


class InFlightMeter:
    """由调用方锁保护的有界计量器，时间全部使用单调时钟。"""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        """注入时钟用于真实调度或确定性的跨窗回归。"""
        self._clock = clock
        self._at = clock()
        self._busy = 0.0
        self._active: dict[int, tuple[float, int]] = {}
        self.peak = 0

    @property
    def active(self) -> int:
        """返回此刻尚未结束的物理请求数。"""
        return len(self._active)

    def _integrate(self) -> float:
        """只累计上次事件至当前事件与当前请求数的乘积。"""
        now = self._clock()
        self._busy += max(0.0, now - self._at) * self.active
        self._at = now
        return now

    def start(self, identity: int, epoch: int) -> None:
        """记录请求起点和探测阶段，禁止同一发送身份重复计入。"""
        if identity in self._active:
            raise ValueError("物理请求已经开始")
        self._active[identity] = (self._integrate(), epoch)
        self.peak = max(self.peak, self.active)

    def finish(self, identity: int) -> tuple[float, int] | None:
        """在完成事件积分后移除请求，返回其实际延迟和开始阶段。"""
        now = self._integrate()
        started = self._active.pop(identity, None)
        return None if started is None else (max(0.0, now - started[0]), started[1])

    def take_busy_seconds(self) -> float:
        """关闭一个本地增量窗，继续保留所有未完成请求。"""
        self._integrate()
        seconds, self._busy = self._busy, 0.0
        return seconds
