"""Scheduler 进程 Platform 装配；计划调度逻辑在 Stage 7 实现。"""

from aima_ugc.platform.config import PlatformSettings

from .runtime import PlatformRuntime, create_platform_runtime


def create_scheduler_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Scheduler 所需的业务无关 Platform runtime。"""
    return create_platform_runtime("scheduler", settings=settings)
