"""AIMA_UGC Alembic 环境。"""

from alembic import context
from sqlalchemy import Connection, inspect, text

from aima_ugc.database_schema import metadata
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime


def _assert_no_unresolved_legacy_budget_state(connection: Connection) -> None:
    """旧 Budget 表仍有未决预留时拒绝 Migration，避免 0015 静默销毁状态。"""
    if "provider_budget_reservations" not in inspect(connection).get_table_names():
        return
    unresolved = connection.scalar(
        text(
            "SELECT count(*) FROM provider_budget_reservations "
            "WHERE status IN ('reserved', 'unknown')"
        )
    )
    if int(unresolved or 0) > 0:
        raise RuntimeError(
            "Legacy Budget 存在未决 reserved/unknown Reservation；"
            "必须先人工核对并收敛状态，禁止继续 Migration。"
        )


def run_migrations_online() -> None:
    """复用正式 PostgreSQL 配置执行显式 Migration。"""
    runtime = DatabaseRuntime(load_settings())
    try:
        with runtime.engine.connect() as connection:
            _assert_no_unresolved_legacy_budget_state(connection)
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
