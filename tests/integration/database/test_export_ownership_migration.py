"""0087 只回填可靠归属，空库可往返，有数据时保护配置和授权事实。"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from tests.integration.database.test_migration_data_lifecycle import (
    _downgrade,
    _engine,
    _upgrade,
)
from tests.integration.database.test_migration_data_lifecycle import (
    migration_database as migration_database,
)


def _seed_export(connection: Connection, snapshot: dict[str, object]) -> UUID:
    """在旧 Revision 写合法历史 Export，不依赖新增字段或当前 Repository。"""
    job_id, export_id = uuid4(), uuid4()
    connection.execute(
        text(
            "INSERT INTO jobs(id, job_type, payload_version, payload, status, "
            "internal_idempotency_key, priority, attempt, max_attempts, timeout_seconds, "
            "progress, available_at, created_at, updated_at) VALUES ("
            ":job_id, 'reporting.content-export-excel.v1', 'reporting.content-export-excel.v1', "
            "'{}'::jsonb, 'queued', :key, 0, 0, 3, 1800, 0, now(), now(), now())"
        ),
        {"job_id": job_id, "key": f"migration-export:{job_id}"},
    )
    connection.execute(
        text(
            "INSERT INTO reporting_data_exports(id, job_id, format, request_snapshot, "
            "columns, column_catalog_version, created_at) VALUES ("
            ":export_id, :job_id, 'xlsx', CAST(:snapshot AS jsonb), '[\"title\"]'::jsonb, 2, now())"
        ),
        {"export_id": export_id, "job_id": job_id, "snapshot": json.dumps(snapshot)},
    )
    return export_id


def test_migration_backfills_only_reliable_creator_and_preserves_frozen_request(
    migration_database: str,
) -> None:
    """空白、非字符串、NULL、缺失字段不能猜测为任意普通用户。"""
    _upgrade(migration_database, "20261009_0086")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            cases = (
                ({"requested_by": "user:stable"}, "user:stable"),
                ({"requested_by": ""}, None),
                ({"requested_by": "   "}, None),
                ({"requested_by": " user:stable "}, None),
                ({"requested_by": None}, None),
                ({"requested_by": 12}, None),
                ({"requested_by": {"principal_id": "user:stable"}}, None),
                ({}, None),
            )
            expected = {
                _seed_export(connection, snapshot): (snapshot, owner) for snapshot, owner in cases
            }
            before = {
                row["id"]: dict(row)
                for row in connection.execute(
                    text(
                        "SELECT id, job_id, artifact_id, format, request_snapshot, columns, "
                        "column_catalog_version, stats, created_at, completed_at "
                        "FROM reporting_data_exports"
                    )
                ).mappings()
            }
        _upgrade(migration_database, "20261010_0087")
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT * FROM reporting_data_exports")).mappings()
            for row in rows:
                fields = dict(row)
                creator = fields.pop("created_by")
                assert fields == before[row["id"]]
                assert creator == expected[row["id"]][1]
            index_definition = connection.scalar(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE indexname = 'ix_reporting_data_exports_owner_recent'"
                )
            )
            assert "created_by" in index_definition
            assert "created_at DESC" in index_definition
            assert "id DESC" in index_definition
            assert inspect(connection).has_table("reporting_user_export_column_defaults")
    finally:
        engine.dispose()


def test_empty_database_migration_roundtrip_remains_supported(migration_database: str) -> None:
    """Release 兼容门禁的空库往返不需要销毁任何个人配置。"""
    _upgrade(migration_database, "20261010_0087")
    _downgrade(migration_database, "20261009_0086")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert not inspector.has_table("reporting_user_export_column_defaults")
            assert "created_by" not in {
                column["name"] for column in inspector.get_columns("reporting_data_exports")
            }
        _upgrade(migration_database, "20261010_0087")
        with engine.connect() as connection:
            assert inspect(connection).has_table("reporting_user_export_column_defaults")
    finally:
        engine.dispose()


@pytest.mark.parametrize("data_kind", ["personal_default", "export"])
def test_schema_downgrade_refuses_to_destroy_user_data_or_export_ownership(
    migration_database: str,
    data_kind: str,
) -> None:
    """应用回滚保留 Schema；不能借 downgrade 丢失个人配置或文件归属。"""
    _upgrade(migration_database, "20261010_0087")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            if data_kind == "personal_default":
                connection.execute(
                    text(
                        "INSERT INTO reporting_user_export_column_defaults "
                        "(principal_id, schema_version, revision, selected_columns, "
                        "saved_catalog_version, created_at, updated_at) VALUES ("
                        "'development:rollback', 1, 4, '[\"title\"]'::jsonb, 3, now(), now())"
                    )
                )
            else:
                export_id = _seed_export(connection, {"requested_by": "user:rollback"})
                connection.execute(
                    text(
                        "UPDATE reporting_data_exports SET created_by = 'user:rollback' WHERE id = :id"
                    ),
                    {"id": export_id},
                )
        with pytest.raises(RuntimeError, match="不能安全 downgrade"):
            _downgrade(migration_database, "20261009_0086")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20261010_0087"
            )
            if data_kind == "personal_default":
                row = connection.execute(
                    text(
                        "SELECT revision, selected_columns FROM reporting_user_export_column_defaults "
                        "WHERE principal_id = 'development:rollback'"
                    )
                ).one()
                assert row.revision == 4
                assert row.selected_columns == ["title"]
            else:
                assert (
                    connection.scalar(
                        text("SELECT created_by FROM reporting_data_exports WHERE id = :id"),
                        {"id": export_id},
                    )
                    == "user:rollback"
                )
    finally:
        engine.dispose()
