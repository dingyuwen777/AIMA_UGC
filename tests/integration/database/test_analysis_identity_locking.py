"""Analysis identity 读取与空库 bootstrap 的 PostgreSQL 锁边界回归。"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.bootstrap.analysis_identity import active_analysis_configuration
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.bootstrap.worker import create_worker_runtime
from aima_ugc.modules.analysis.scheme_tables import (
    analysis_scheme_versions_table,
    analysis_schemes_table,
)
from aima_ugc.platform.config import load_settings
from sqlalchemy import func, select, text


@pytest.fixture
def runtime() -> Iterator[PlatformRuntime]:
    """提供清空 Analysis 配置事实的真实 PostgreSQL Runtime。"""

    value = create_worker_runtime(settings=load_settings())

    def cleanup() -> None:
        """清除本测试创建的 Scheme、审计和 Provider 配置。"""

        with value.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE audit_events, provider_configs, analysis_schemes "
                "RESTART IDENTITY CASCADE"
            )

    cleanup()
    try:
        yield value
    finally:
        cleanup()
        value.close()


def test_active_analysis_configuration_does_not_wait_for_scheme_write_lock(
    runtime: PlatformRuntime,
) -> None:
    """已有 active Version 的读取不应竞争只属于低频写入的 registry 锁。"""

    bootstrap_session = runtime.database.new_session()
    try:
        with bootstrap_session.begin():
            active = active_analysis_configuration(bootstrap_session, runtime.settings)
    finally:
        bootstrap_session.close()

    writer_session = runtime.database.new_session()
    reader_session = runtime.database.new_session()
    writer_transaction = writer_session.begin()
    try:
        PostgresAnalysisSchemeRepository(writer_session).create_draft(
            name="并发写锁测试",
            description="持有 registry advisory lock，验证 active 读取不等待",
            definition=active.scheme.definition,
            actor_ref="test:analysis-lock",
        )
        with reader_session.begin():
            reader_session.execute(text("SET LOCAL lock_timeout = '750ms'"))
            current = active_analysis_configuration(reader_session, runtime.settings)
        assert current.scheme.id == active.scheme.id
    finally:
        if writer_transaction.is_active:
            writer_transaction.rollback()
        writer_session.close()
        reader_session.close()


def test_concurrent_empty_database_bootstrap_keeps_one_active_version(
    runtime: PlatformRuntime,
) -> None:
    """无锁读取快路径不能破坏空库并发 bootstrap 的唯一 active 语义。"""

    barrier = Barrier(2, timeout=5)

    def load_configuration() -> str:
        """同步两个调用方后，通过正式装配入口读取或初始化 active Version。"""

        session = runtime.database.new_session()
        try:
            barrier.wait()
            with session.begin():
                configuration = active_analysis_configuration(session, runtime.settings)
            return str(configuration.scheme.id)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        version_ids = tuple(executor.map(lambda _index: load_configuration(), range(2)))

    assert len(set(version_ids)) == 1
    with runtime.database.engine.begin() as connection:
        scheme_count = connection.scalar(select(func.count()).select_from(analysis_schemes_table))
        version_count = connection.scalar(
            select(func.count()).select_from(analysis_scheme_versions_table)
        )
        active_count = connection.scalar(
            select(func.count())
            .select_from(analysis_schemes_table)
            .where(analysis_schemes_table.c.is_active.is_(True))
        )
    assert scheme_count == 1
    assert version_count == 1
    assert active_count == 1
