"""AIMA_UGC Alembic 环境。"""

from alembic import context

from aima_ugc.database_schema import metadata
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def run_migrations_online() -> None:
    """复用正式 PostgreSQL 配置执行显式 Migration。"""
    runtime = DatabaseRuntime(load_settings())
    try:
        with runtime.engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        runtime.dispose()


if context.is_offline_mode():
    raise RuntimeError("AIMA_UGC Migration 只支持连接真实 PostgreSQL 的 online 模式")

run_migrations_online()
