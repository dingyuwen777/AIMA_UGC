"""数据型 Migration 必须用旧 Revision + 历史数据验证，而不只验证空库 round-trip。"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.security import read_secret_file
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.engine import Engine

_ROOT = Path(__file__).resolve().parents[3]
_NOW = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)


def _database_url(database: str) -> URL:
    settings = load_settings()
    password = read_secret_file(settings.postgres_password_file).get_secret_value()
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.db_user,
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database=database,
    )


def _engine(database: str, *, autocommit: bool = False) -> Engine:
    return create_engine(
        _database_url(database),
        isolation_level="AUTOCOMMIT" if autocommit else None,
        pool_pre_ping=True,
    )


@pytest.fixture
def migration_database() -> Iterator[str]:
    settings = load_settings()
    database = f"aima_migration_{uuid4().hex}"
    admin = _engine(settings.db_name, autocommit=True)
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        yield database
    finally:
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


@contextmanager
def _migration_target(database: str) -> Iterator[None]:
    previous = os.environ.get("AIMA_DB_NAME")
    os.environ["AIMA_DB_NAME"] = database
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("AIMA_DB_NAME", None)
        else:
            os.environ["AIMA_DB_NAME"] = previous


def _upgrade(database: str, revision: str) -> None:
    with _migration_target(database):
        command.upgrade(Config(str(_ROOT / "alembic.ini")), revision)


def _downgrade(database: str, revision: str) -> None:
    with _migration_target(database):
        command.downgrade(Config(str(_ROOT / "alembic.ini")), revision)


def _seed_keyword(
    database: str,
    *,
    text_value: str,
    normalized_text: str,
) -> None:
    engine = _engine(database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO keywords(
                      id, text, normalized_text, enabled, created_at, updated_at
                    ) VALUES (
                      :id, :text, :normalized_text, TRUE, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "text": text_value,
                    "normalized_text": normalized_text,
                    "created_at": _NOW,
                    "updated_at": _NOW,
                },
            )
    finally:
        engine.dispose()


def _seed_budget_reservation(database: str, *, status: str) -> None:
    settled_amount = 1 if status == "settled" else None
    engine = _engine(database)
    try:
        with engine.begin() as connection:
            # 测试只需要制造“0014 已存在的历史 Reservation”事实。FK 来源链在这里
            # 不是被测对象；replica 仅用于隔离测试装载，不进入生产 Migration。
            connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
            connection.execute(
                text(
                    """
                    INSERT INTO provider_budget_reservations(
                      id, budget_account_id, provider_request_id,
                      provider_request_attempt_id, reserved_amount,
                      settled_amount, status, created_at, updated_at
                    ) VALUES (
                      :id, :budget_account_id, :provider_request_id,
                      :provider_request_attempt_id, 1,
                      :settled_amount, :status, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "budget_account_id": uuid4(),
                    "provider_request_id": uuid4(),
                    "provider_request_attempt_id": uuid4(),
                    "settled_amount": settled_amount,
                    "status": status,
                    "created_at": _NOW,
                    "updated_at": _NOW,
                },
            )
    finally:
        engine.dispose()


def test_0014_to_0015_accepts_settled_historical_budget_rows(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260815_0014")
    _seed_budget_reservation(migration_database, status="settled")

    _upgrade(migration_database, "20260817_0015")

    engine = _engine(migration_database)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "provider_budget_accounts" not in tables
        assert "provider_budget_reservations" not in tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260817_0015"
            )
    finally:
        engine.dispose()


def test_0014_to_0015_blocks_unresolved_budget_before_destructive_ddl(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260815_0014")
    _seed_budget_reservation(migration_database, status="reserved")

    with pytest.raises(RuntimeError, match="未决.*Reservation"):
        _upgrade(migration_database, "20260817_0015")

    engine = _engine(migration_database)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "provider_budget_accounts" in tables
        assert "provider_budget_reservations" in tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260815_0014"
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM provider_budget_reservations "
                        "WHERE status = 'reserved'"
                    )
                )
                == 1
            )
    finally:
        engine.dispose()


def test_0016_to_0017_backfills_only_existing_current_fields(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260817_0016")
    account_id = uuid4()
    content_id = uuid4()
    comment_id = uuid4()
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts(
                      id, platform, external_account_id, handle, display_name,
                      first_seen_at, last_seen_at, updated_at
                    ) VALUES (
                      :id, 'xiaohongshu', 'account-old', 'old-handle', NULL,
                      :seen, :seen, :seen
                    )
                    """
                ),
                {"id": account_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO contents(
                      id, platform, external_content_id, content_type,
                      title, text, author_account_id, first_seen_at,
                      last_seen_at, current_version, current_like_count,
                      current_comment_count, updated_at
                    ) VALUES (
                      :id, 'xiaohongshu', 'content-old', 'image',
                      '历史标题', NULL, :author_id, :seen,
                      :seen, 1, 9, NULL, :seen
                    )
                    """
                ),
                {"id": content_id, "author_id": account_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO comments(
                      id, content_id, external_comment_id, root_comment_id,
                      parent_comment_id, author_account_id, text,
                      is_by_content_author, first_seen_at, last_seen_at,
                      current_like_count, current_reply_count, current_version,
                      updated_at
                    ) VALUES (
                      :id, :content_id, 'comment-old', 'comment-old',
                      NULL, :author_id, '历史评论', FALSE, :seen, :seen,
                      2, NULL, 1, :seen
                    )
                    """
                ),
                {
                    "id": comment_id,
                    "content_id": content_id,
                    "author_id": account_id,
                    "seen": _NOW,
                },
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260817_0017")

    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            account = (
                connection.execute(
                    text(
                        "SELECT field_observed_at, last_seen_at::text AS seen "
                        "FROM accounts WHERE id = :id"
                    ),
                    {"id": account_id},
                )
                .mappings()
                .one()
            )
            content = (
                connection.execute(
                    text(
                        "SELECT field_observed_at, last_seen_at::text AS seen "
                        "FROM contents WHERE id = :id"
                    ),
                    {"id": content_id},
                )
                .mappings()
                .one()
            )
            comment = (
                connection.execute(
                    text(
                        "SELECT field_observed_at, last_seen_at::text AS seen "
                        "FROM comments WHERE id = :id"
                    ),
                    {"id": comment_id},
                )
                .mappings()
                .one()
            )

        account_fields = account["field_observed_at"]
        assert account_fields["author.handle"] == account["seen"]
        assert "author.display_name" not in account_fields

        content_fields = content["field_observed_at"]
        for field in (
            "content_type",
            "title",
            "author.external_account_id",
            "metrics.like_count",
        ):
            assert content_fields[field] == content["seen"]
        assert "text" not in content_fields
        assert "metrics.comment_count" not in content_fields

        comment_fields = comment["field_observed_at"]
        for field in (
            "root_comment_id",
            "author.external_account_id",
            "text",
            "is_by_content_author",
            "metrics.like_count",
        ):
            assert comment_fields[field] == comment["seen"]
        assert "parent_comment_id" not in comment_fields
        assert "metrics.reply_count" not in comment_fields
    finally:
        engine.dispose()


def test_0019_to_0020_normalizes_keyword_identity_and_round_trips_schema(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260820_0019")
    _seed_keyword(
        migration_database,
        text_value="  ＡＩＭＡ  ",
        normalized_text=f"legacy-{uuid4()}",
    )

    _upgrade(migration_database, "20260820_0020")
    engine = _engine(migration_database)
    try:
        assert "global_relevance_config" in set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT normalized_text FROM keywords")) == "aima"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260820_0020"
            )
    finally:
        engine.dispose()

    _downgrade(migration_database, "20260820_0019")
    engine = _engine(migration_database)
    try:
        assert "global_relevance_config" not in set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT normalized_text FROM keywords")) == "aima"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260820_0019"
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260820_0020")


def test_0019_to_0020_blocks_nfkc_identity_collision_before_schema_change(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260820_0019")
    _seed_keyword(
        migration_database,
        text_value="ＡＩＭＡ",
        normalized_text=f"fullwidth-{uuid4()}",
    )
    _seed_keyword(
        migration_database,
        text_value="aima",
        normalized_text=f"ascii-{uuid4()}",
    )

    with pytest.raises(RuntimeError, match="NFKC/casefold 身份冲突"):
        _upgrade(migration_database, "20260820_0020")

    engine = _engine(migration_database)
    try:
        assert "global_relevance_config" not in set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260820_0019"
            )
            assert connection.scalar(text("SELECT count(*) FROM keywords")) == 2
    finally:
        engine.dispose()


def test_0020_downgrade_refuses_to_erase_filtered_candidate_semantics(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260820_0020")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
            connection.execute(
                text(
                    """
                    INSERT INTO collection_candidate_ingestions(
                      id, candidate_id, ingestion_no, observed_fields,
                      result, processed_at
                    ) VALUES (
                      :id, :candidate_id, 1, '[]'::jsonb,
                      'filtered', :processed_at
                    )
                    """
                ),
                {"id": uuid4(), "candidate_id": uuid4(), "processed_at": _NOW},
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="不能安全 downgrade"):
        _downgrade(migration_database, "20260820_0019")

    engine = _engine(migration_database)
    try:
        assert "global_relevance_config" in set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20260820_0020"
            )
    finally:
        engine.dispose()


def test_0023_to_0024_unifies_platform_machine_values(migration_database: str) -> None:
    _upgrade(migration_database, "20260821_0023")
    account_id = uuid4()
    content_id = uuid4()
    pack_id = uuid4()
    keyword_id = uuid4()
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts(
                      id, platform, external_account_id, first_seen_at, last_seen_at,
                      field_observed_at, updated_at
                    ) VALUES (
                      :id, 'xhs', 'platform-migration-account', :seen, :seen, '{}'::jsonb, :seen
                    )
                    """
                ),
                {"id": account_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO contents(
                      id, platform, external_content_id, content_type, author_account_id,
                      first_seen_at, last_seen_at, current_version, field_observed_at, updated_at
                    ) VALUES (
                      :id, 'xhs', 'platform-migration-content', 'image', :author_id,
                      :seen, :seen, 1, '{}'::jsonb, :seen
                    )
                    """
                ),
                {"id": content_id, "author_id": account_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO keyword_packs(id, name, description, enabled, version, created_at, updated_at)
                    VALUES (:id, :name, '', TRUE, 1, :seen, :seen)
                    """
                ),
                {"id": pack_id, "name": f"platform-migration-{pack_id}", "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO keywords(id, text, normalized_text, enabled, created_at, updated_at)
                    VALUES (:id, '爱玛', :normalized, TRUE, :seen, :seen)
                    """
                ),
                {"id": keyword_id, "normalized": f"platform-migration-{keyword_id}", "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO keyword_pack_items(pack_id, keyword_id, platform, priority, enabled, note)
                    VALUES (:pack_id, :keyword_id, 'all', 10, TRUE, '')
                    """
                ),
                {"pack_id": pack_id, "keyword_id": keyword_id},
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260822_0024")

    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        assert "platform_scope" in {
            item["name"] for item in inspector.get_columns("keyword_pack_items")
        }
        assert "platform" not in {
            item["name"] for item in inspector.get_columns("keyword_pack_items")
        }
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT platform FROM accounts WHERE id = :id"), {"id": account_id}
                )
                == "xiaohongshu"
            )
            assert (
                connection.scalar(
                    text("SELECT platform FROM contents WHERE id = :id"), {"id": content_id}
                )
                == "xiaohongshu"
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT platform_scope FROM keyword_pack_items "
                        "WHERE pack_id = :pack_id AND keyword_id = :keyword_id"
                    ),
                    {"pack_id": pack_id, "keyword_id": keyword_id},
                )
                == "all"
            )
            with pytest.raises(Exception):
                connection.execute(
                    text("UPDATE contents SET platform = 'invalid-platform' WHERE id = :id"),
                    {"id": content_id},
                )
    finally:
        engine.dispose()


def test_0023_to_0024_blocks_duplicate_content_identity(migration_database: str) -> None:
    _upgrade(migration_database, "20260821_0023")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            for platform in ("xhs", "xiaohongshu"):
                connection.execute(
                    text(
                        """
                        INSERT INTO contents(
                          id, platform, external_content_id, content_type,
                          first_seen_at, last_seen_at, current_version,
                          field_observed_at, updated_at
                        ) VALUES (
                          :id, :platform, 'platform-conflict', 'image',
                          :seen, :seen, 1, '{}'::jsonb, :seen
                        )
                        """
                    ),
                    {"id": uuid4(), "platform": platform, "seen": _NOW},
                )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="平台标识迁移冲突.*contents"):
        _upgrade(migration_database, "20260822_0024")

    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260821_0023"
            )
            platforms = (
                connection.execute(
                    text(
                        "SELECT platform FROM contents WHERE external_content_id = 'platform-conflict' "
                        "ORDER BY platform"
                    )
                )
                .scalars()
                .all()
            )
            assert platforms == ["xhs", "xiaohongshu"]
    finally:
        engine.dispose()
