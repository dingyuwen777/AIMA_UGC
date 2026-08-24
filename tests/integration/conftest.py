"""Shared isolation for consolidated PostgreSQL integration suites in GitHub Actions."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import inspect, text

_CI_DATABASE_PASSWORD = "ci-postgres"
_LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost"}


@pytest.fixture(scope="session", autouse=True)
def reset_consolidated_ci_database() -> Iterator[None]:
    """Restore the fresh-database boundary formerly provided by separate CI runners.

    The destructive reset is deliberately limited to GitHub Actions, the local
    PostgreSQL service address, and the dedicated CI credential. Local/manual
    integration runs keep their existing database lifecycle.
    """

    if os.environ.get("GITHUB_ACTIONS") != "true":
        yield
        return

    settings = load_settings()
    if settings.db_host not in _LOCAL_DATABASE_HOSTS:
        raise RuntimeError(
            f"Refusing CI integration reset for non-local database host: {settings.db_host}"
        )

    if (
        settings.postgres_password_file.read_text(encoding="utf-8").strip()
        != _CI_DATABASE_PASSWORD
    ):
        raise RuntimeError("Refusing CI integration reset outside the dedicated CI database")

    runtime = DatabaseRuntime(settings)
    try:
        inspector = inspect(runtime.engine)
        table_names = [
            table_name
            for table_name in inspector.get_table_names(schema="public")
            if table_name != "alembic_version"
        ]
        if table_names:
            quote = runtime.engine.dialect.identifier_preparer.quote
            tables = ", ".join(quote(table_name) for table_name in table_names)
            with runtime.engine.begin() as connection:
                connection.execute(
                    text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
                )
    finally:
        runtime.dispose()

    yield
