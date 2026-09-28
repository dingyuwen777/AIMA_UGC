"""空库并发工作台请求的 active Scheme 持久化回归。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from uuid import uuid4

from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.bootstrap.workbench_http import PostgresWorkbenchHttpService
from aima_ugc.contracts.workbench import WorkbenchQuery
from aima_ugc.modules.analysis.scheme_tables import analysis_schemes_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.security import read_secret_file
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL


def test_parallel_workbench_requests_persist_one_active_scheme(monkeypatch) -> None:
    """三个模块并发首次访问时，不得各自返回一个回滚后的 Scheme。"""

    settings = load_settings()
    database = f"aima_workbench_{uuid4().hex}"
    password = read_secret_file(settings.postgres_password_file).get_secret_value()
    admin = create_engine(
        URL.create(
            "postgresql+psycopg",
            username=settings.db_user,
            password=password,
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
        ),
        isolation_level="AUTOCOMMIT",
    )
    runtime = None
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        monkeypatch.setenv("AIMA_DB_NAME", database)
        command.upgrade(Config(str(Path(__file__).resolve().parents[3] / "alembic.ini")), "head")
        runtime = create_platform_runtime("api", settings=load_settings())
        service = PostgresWorkbenchHttpService(runtime)
        query = WorkbenchQuery(date_from=date(2026, 9, 1), date_to=date(2026, 9, 2))
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = (
                pool.submit(service.get_stream, query),
                pool.submit(service.get_mind, query),
                pool.submit(service.get_trend, query),
            )
            responses = tuple(future.result(timeout=30) for future in futures)

        assert len({response.analysis_scheme_version_id for response in responses}) == 1
        assert len({response.taxonomy_sha256 for response in responses}) == 1
        with runtime.database.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(analysis_schemes_table)) == 1
    finally:
        if runtime is not None:
            runtime.close()
        with admin.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database AND pid <> pg_backend_pid()"
                ),
                {"database": database},
            )
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database}"')
        admin.dispose()
