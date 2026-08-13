"""Worker 进程 Platform 装配；Job Runtime 在 Stage 4 实现。"""

from aima_ugc.platform.config import PlatformSettings

from .runtime import PlatformRuntime, create_platform_runtime


def create_worker_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Worker 所需的业务无关 Platform runtime。"""
    return create_platform_runtime("worker", settings=settings)
