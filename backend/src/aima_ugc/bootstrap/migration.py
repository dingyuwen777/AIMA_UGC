"""Migration 进程 Platform 装配；Alembic Revision 在 Stage 3 建立。"""

from aima_ugc.platform.config import PlatformSettings

from .runtime import PlatformRuntime, create_platform_runtime


def create_migration_runtime(*, settings: PlatformSettings | None = None) -> PlatformRuntime:
    """创建 Migration 所需的业务无关 Platform runtime。"""
    return create_platform_runtime("migrate", settings=settings)
