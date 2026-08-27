"""Stage 12D 容量脚本必须编排生产 Campaign/Worker，而不是复制导入规则。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.security import read_secret_file
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, text

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "scripts" / "performance" / "benchmark_stage12_historical.py"


@pytest.fixture
def capacity_database() -> Iterator[str]:
    """为容量 Harness 创建独立临时库，避免依赖开发机预置数据库。"""

    settings = load_settings()
    password = read_secret_file(settings.postgres_password_file).get_secret_value()
    database = f"aima_{uuid4().hex}_stage12_capacity"
    admin_url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.db_user,
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    previous = os.environ.get("AIMA_DB_NAME")
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        os.environ["AIMA_DB_NAME"] = database
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        yield database
    finally:
        if previous is None:
            os.environ.pop("AIMA_DB_NAME", None)
        else:
            os.environ["AIMA_DB_NAME"] = previous
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


def test_capacity_harness_records_bounded_end_to_end_evidence(
    tmp_path: Path,
    capacity_database: str,
) -> None:
    environment = os.environ.copy()
    environment["AIMA_DB_NAME"] = capacity_database
    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--work-dir",
            str(tmp_path),
            "--rows",
            "220",
            "--rows-per-file",
            "220",
            "--chunk-rows",
            "100",
            "--max-in-flight",
            "2",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    report = json.loads((tmp_path / "capacity_report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "stage12-historical-capacity.v1"
    assert report["input"]["rows"] == 220
    assert report["input"]["files"] == 1
    assert report["configuration"]["chunk_rows"] == 100
    assert report["configuration"]["max_in_flight_jobs"] == 2
    assert report["campaign"]["status"] == "succeeded"
    assert report["campaign"]["terminal_rows"] == 220
    assert report["campaign"]["reconciled"] is True
    assert report["campaign"]["stats"]["created"] == 220
    assert report["measurements"]["elapsed_seconds"] > 0
    assert report["measurements"]["rows_per_second"] > 0
    assert report["measurements"]["peak_rss_bytes"] > 0
    assert report["measurements"]["wal_bytes"] >= 0
    assert report["storage"]["database_bytes"] > 0
    assert report["storage"]["source_bytes"] > 0
    assert report["storage"]["artifact_bytes"] > 0
    assert report["jobs"]["maximum_observed_active"] <= 2
    assert report["jobs"]["ordinary_job_starvation_probe"] == "passed"
