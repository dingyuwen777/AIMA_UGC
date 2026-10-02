"""空库并发工作台请求的 active Scheme 持久化回归。"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.workbench_snapshots import (
    PostgresWorkbenchSnapshotRepository,
    WorkbenchSnapshotRefresh,
)
from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.bootstrap.workbench_http import (
    PostgresWorkbenchHttpService,
    _resolved_snapshot_query,
    _snapshot_query_hash,
)
from aima_ugc.contracts.workbench import (
    WorkbenchMindResponse,
    WorkbenchQuery,
    WorkbenchStreamQuery,
)
from aima_ugc.modules.analysis.scheme_tables import analysis_schemes_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.security import read_secret_file
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select, text
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
        service = PostgresWorkbenchHttpService(
            runtime,
            cursor_signing_secret=b"workbench-bootstrap-cursor-key-32-bytes-minimum",
        )
        query = WorkbenchQuery(date_from=date(2026, 9, 1), date_to=date(2026, 9, 2))
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = (
                pool.submit(
                    service.get_stream,
                    WorkbenchStreamQuery.model_validate(query.model_dump()),
                ),
                pool.submit(service.get_mind, query),
                pool.submit(service.get_trend, query),
            )
            responses = tuple(future.result(timeout=30) for future in futures)

        assert len({response.analysis_scheme_version_id for response in responses}) == 1
        assert len({response.taxonomy_sha256 for response in responses}) == 1
        assert responses[1].snapshot_status == "preparing"
        assert responses[2].snapshot_status == "preparing"
        assert isinstance(responses[1], WorkbenchMindResponse)
        direct_mind = PostgresWorkbenchHttpService(
            runtime,
            use_snapshot_cache=False,
        ).get_mind(query)
        assert direct_mind.dimensions
        assert all(item.primary_label != "无法分类" for item in direct_mind.dimensions)
        with runtime.database.engine.connect() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(jobs_table)
                    .where(jobs_table.c.job_type == "workbench.snapshot-refresh.v1")
                )
                == 2
            )
        resolved_query = _resolved_snapshot_query(query)
        mind_hash = _snapshot_query_hash("mind", resolved_query)
        # 持久保存旧作者口径 JSONB；新查询必须另建身份，不能误解析成新 Contract。
        legacy_payload = resolved_query.model_dump(mode="json")
        for key, value in legacy_payload.items():
            if isinstance(value, list):
                legacy_payload[key] = sorted(value)
        legacy_hash = hashlib.sha256(
            json.dumps(
                {"module": "mind", "query": legacy_payload},
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        assert legacy_hash != mind_hash
        with runtime.database.new_session() as session, session.begin():
            snapshots = PostgresWorkbenchSnapshotRepository(session)
            legacy_refresh = snapshots.request_refresh(
                module="mind",
                query_hash=legacy_hash,
                query=legacy_payload,
                source_revision=snapshots.current_data_revision(),
                analysis_scheme_version_id=responses[1].analysis_scheme_version_id,
            )
            assert legacy_refresh is not None
            assert snapshots.record_success(
                refresh=legacy_refresh,
                taxonomy_sha256=responses[1].taxonomy_sha256,
                response={
                    "identified_user_count": 8,
                    "dimensions": [{"user_count": 4, "user_share": 0.5}],
                },
                computed_at=responses[1].as_of,
            )
            row = snapshots.get(module="mind", query_hash=mind_hash)
            assert row is not None
            refresh = WorkbenchSnapshotRefresh(
                module="mind",
                query_hash=mind_hash,
                source_revision=int(row["target_revision"]),
                refresh_generation=int(row["refresh_generation"]),
                analysis_scheme_version_id=responses[1].analysis_scheme_version_id,
            )
            incompatible = responses[1].model_copy(
                update={
                    "snapshot_status": "fresh",
                    "computed_at": responses[1].as_of,
                    "source_revision": refresh.source_revision,
                    "taxonomy_sha256": "f" * 64,
                }
            )
            assert snapshots.record_success(
                refresh=refresh,
                taxonomy_sha256="f" * 64,
                response=incompatible.model_dump(mode="json"),
                computed_at=responses[1].as_of,
            )

        current_mind = service.get_mind(query)
        assert current_mind.snapshot_status == "preparing"
        assert current_mind.taxonomy_sha256 == responses[0].taxonomy_sha256
        assert current_mind.dimensions == ()
        with runtime.database.new_session() as session, session.begin():
            snapshots = PostgresWorkbenchSnapshotRepository(session)
            row = snapshots.get(module="mind", query_hash=mind_hash)
            assert row is not None
            refresh = WorkbenchSnapshotRefresh(
                module="mind",
                query_hash=mind_hash,
                source_revision=int(row["target_revision"]),
                refresh_generation=int(row["refresh_generation"]),
                analysis_scheme_version_id=current_mind.analysis_scheme_version_id,
            )
            compatible = current_mind.model_copy(
                update={
                    "snapshot_status": "fresh",
                    "computed_at": current_mind.as_of,
                    "source_revision": refresh.source_revision,
                }
            )
            assert snapshots.record_success(
                refresh=refresh,
                taxonomy_sha256=current_mind.taxonomy_sha256,
                response=compatible.model_dump(mode="json"),
                computed_at=current_mind.as_of,
            )

        statements: list[str] = []

        def capture_statement(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(runtime.database.engine, "before_cursor_execute", capture_statement)
        try:
            cached_mind = service.get_mind(query)
        finally:
            event.remove(runtime.database.engine, "before_cursor_execute", capture_statement)
        assert cached_mind.snapshot_status == "fresh"
        assert not any("workbench:mind-snapshot" in statement for statement in statements)
        with runtime.database.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(analysis_schemes_table)) == 1
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(jobs_table)
                    .where(jobs_table.c.job_type == "workbench.snapshot-refresh.v1")
                )
                == 3
            )
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
