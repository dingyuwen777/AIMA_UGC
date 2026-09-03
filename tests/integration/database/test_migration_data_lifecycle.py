"""数据型 Migration 必须用旧 Revision + 历史数据验证，而不只验证空库 round-trip。"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis.schemes import compile_analysis_scheme
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.security import read_secret_file
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

_ROOT = Path(__file__).resolve().parents[3]
_NOW = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)


def _legacy_analysis_snapshot(definition: dict[str, object]) -> tuple[str, str, str]:
    """复现 0038 之前依赖 labels 插入顺序的编译行为。"""

    taxonomy_payload = {
        "schema_version": "aima-content-taxonomy.v2",
        "sentiments": list(definition["sentiments"]),  # type: ignore[arg-type]
        "voice_types": list(definition["voice_types"]),  # type: ignore[arg-type]
        "labels": {
            key: list(values)
            for key, values in definition["labels"].items()  # type: ignore[union-attr]
        },
    }
    readable_json = json.dumps(taxonomy_payload, ensure_ascii=False, indent=2)
    normalized_json = json.dumps(
        taxonomy_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    block = (
        f"<!-- AIMA_TAXONOMY_START -->\n```json\n{readable_json}\n```\n<!-- AIMA_TAXONOMY_END -->"
    )
    prompt_text = str(definition["prompt_template"]).replace("{{AIMA_TAXONOMY_JSON}}", block)
    return (
        prompt_text,
        hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        hashlib.sha256(normalized_json).hexdigest(),
    )


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


def _observed_at(value: object) -> datetime:
    """解析 Migration 写入 JSONB 的带时区时间，并按绝对时刻参与断言。"""
    if not isinstance(value, str):
        raise AssertionError(f"field_observed_at 时间必须是字符串，实际为 {type(value).__name__}")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssertionError("field_observed_at 时间必须包含时区")
    return parsed


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
    """0017 回填只覆盖已有字段，并按绝对时刻而非旧 UTC 文本格式比较时间。"""
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
                        "SELECT field_observed_at, last_seen_at AS seen "
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
                        "SELECT field_observed_at, last_seen_at AS seen "
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
                        "SELECT field_observed_at, last_seen_at AS seen "
                        "FROM comments WHERE id = :id"
                    ),
                    {"id": comment_id},
                )
                .mappings()
                .one()
            )

        account_fields = account["field_observed_at"]
        assert _observed_at(account_fields["author.handle"]) == account["seen"]
        assert "author.display_name" not in account_fields

        content_fields = content["field_observed_at"]
        for field in (
            "content_type",
            "title",
            "author.external_account_id",
            "metrics.like_count",
        ):
            assert _observed_at(content_fields[field]) == content["seen"]
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
            assert _observed_at(comment_fields[field]) == comment["seen"]
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
                    INSERT INTO keyword_packs(
                      id, name, description, enabled, version, created_at, updated_at
                    ) VALUES (:id, :name, '', TRUE, 1, :seen, :seen)
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
                    INSERT INTO keyword_pack_items(
                      pack_id, keyword_id, platform, priority, enabled, note
                    ) VALUES (:pack_id, :keyword_id, 'all', 10, TRUE, '')
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
            with pytest.raises(IntegrityError):
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
                        "SELECT platform FROM contents "
                        "WHERE external_content_id = 'platform-conflict' ORDER BY platform"
                    )
                )
                .scalars()
                .all()
            )
            assert platforms == ["xhs", "xiaohongshu"]
    finally:
        engine.dispose()


def test_0026_to_0027_backfills_legacy_analysis_request_and_result(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260826_0026")
    request_id = uuid4()
    job_id = uuid4()
    content_id = uuid4()
    result_id = uuid4()
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
            connection.execute(
                text(
                    """
                    INSERT INTO contents(
                      id, platform, external_content_id, content_type,
                      first_seen_at, last_seen_at, current_version,
                      field_observed_at, updated_at
                    ) VALUES (
                      :id, 'xiaohongshu', 'legacy-analysis-content', 'note',
                      :seen, :seen, 1, '{}'::jsonb, :seen
                    )
                    """
                ),
                {"id": content_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO jobs(
                      id, job_type, payload_version, payload, status,
                      internal_idempotency_key, priority, attempt,
                      lease_takeover_count, max_attempts, timeout_seconds, progress,
                      available_at, started_at, finished_at, created_at, updated_at
                    ) VALUES (
                      :job_id, 'analysis.content-label.v1', 'analysis.content-label.v1',
                      '{}'::jsonb, 'succeeded', :key, 0, 1, 0, 3, 1800, 100,
                      :seen, :seen, :seen, :seen, :seen
                    )
                    """
                ),
                {"job_id": job_id, "key": f"legacy:{job_id}", "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO analysis_content_requests(
                      id, job_id, scope, filter_snapshot, target_count, created_at
                    ) VALUES (:id, :job_id, 'selected', '{}'::jsonb, 1, :seen)
                    """
                ),
                {"id": request_id, "job_id": job_id, "seen": _NOW},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO analysis_content_results(
                      id, content_id, content_version, job_id, schema_version,
                      relevance, voice_type, sentiment, prompt_version,
                      prompt_sha256, taxonomy_sha256, model_provider, model,
                      input_hash, analyzed_at, created_at
                    ) VALUES (
                      :id, :content_id, 1, :job_id, 'analysis.content-label.v3',
                      'irrelevant', 'unknown', NULL, 'v3', :prompt_sha,
                      :taxonomy_sha, 'fake', 'fake-v1', :input_hash, :seen, :seen
                    )
                    """
                ),
                {
                    "id": result_id,
                    "content_id": content_id,
                    "job_id": job_id,
                    "prompt_sha": "a" * 64,
                    "taxonomy_sha": "b" * 64,
                    "input_hash": "c" * 64,
                    "seen": _NOW,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO analysis_content_request_items(
                      request_id, content_id, content_version, ordinal,
                      analysis_result_id, status
                    ) VALUES (:request_id, :content_id, 1, 0, :result_id, 'succeeded')
                    """
                ),
                {
                    "request_id": request_id,
                    "content_id": content_id,
                    "result_id": result_id,
                },
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260826_0027")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            run = (
                connection.execute(
                    text(
                        "SELECT id, planner_job_id, shard_size, status "
                        "FROM analysis_content_runs WHERE id = :id"
                    ),
                    {"id": request_id},
                )
                .mappings()
                .one()
            )
            assert run == {
                "id": request_id,
                "planner_job_id": job_id,
                "shard_size": 1,
                "status": "succeeded",
            }
            assert connection.execute(
                text(
                    "SELECT content_id, content_version, target_ordinal "
                    "FROM analysis_content_run_targets WHERE run_id = :id"
                ),
                {"id": request_id},
            ).one() == (content_id, 1, 0)
            assert connection.execute(
                text("SELECT run_id, shard_no FROM analysis_content_requests WHERE id = :id"),
                {"id": request_id},
            ).one() == (request_id, 0)
            assert (
                connection.scalar(
                    text("SELECT analysis_run_id FROM analysis_content_results WHERE id = :id"),
                    {"id": result_id},
                )
                == request_id
            )
    finally:
        engine.dispose()

    _downgrade(migration_database, "20260826_0026")
    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        assert "analysis_content_runs" not in set(inspector.get_table_names())
        assert "analysis_run_id" not in {
            column["name"] for column in inspector.get_columns("analysis_content_results")
        }
    finally:
        engine.dispose()


def test_0027_to_0028_backfills_server_campaign_and_round_trips_schema(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260826_0027")
    campaign_id = uuid4()
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO historical_import_campaigns(
                      id, client_idempotency_key, root_relative_path, recursive,
                      profile_snapshot, keyword_pack_snapshot, status,
                      discovered_file_count, ready_item_count, total_rows, stats, created_at
                    ) VALUES (
                      :id, :key, 'archive/2025', TRUE,
                      '{}'::jsonb, '{}'::jsonb, 'ready', 3, 3, 120, '{}'::jsonb, :seen
                    )
                    """
                ),
                {
                    "id": campaign_id,
                    "key": f"legacy-server:{campaign_id}",
                    "seen": _NOW,
                },
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260827_0028")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT source_kind, ingestion_policy, declared_file_count "
                    "FROM historical_import_campaigns WHERE id = :id"
                ),
                {"id": campaign_id},
            ).one() == ("server_path", "historical_fill_only", 3)
    finally:
        engine.dispose()

    _downgrade(migration_database, "20260826_0027")
    engine = _engine(migration_database)
    try:
        columns = {
            column["name"] for column in inspect(engine).get_columns("historical_import_campaigns")
        }
        assert "source_kind" not in columns
        assert "ingestion_policy" not in columns
        assert "declared_file_count" not in columns
    finally:
        engine.dispose()


def test_0028_accepts_legacy_double_prefixed_historical_constraint(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260826_0027")
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE processing_import_batches RENAME CONSTRAINT "
                    "ck_processing_import_batches_historical_fields_consistent TO "
                    "ck_processing_import_batches_ck_processing_import_batch_fa0e"
                )
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260827_0028")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260827_0028"
            )
    finally:
        engine.dispose()


def test_0028_downgrade_refuses_local_campaign_semantics(migration_database: str) -> None:
    _upgrade(migration_database, "20260827_0028")
    campaign_id = uuid4()
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO historical_import_campaigns(
                      id, client_idempotency_key, source_kind, ingestion_policy,
                      declared_file_count, root_relative_path, recursive,
                      profile_snapshot, keyword_pack_snapshot, status, created_at
                    ) VALUES (
                      :id, :key, 'local_upload', 'standard_observation',
                      1, '', FALSE, '{}'::jsonb, '{}'::jsonb, 'uploading', :seen
                    )
                    """
                ),
                {
                    "id": campaign_id,
                    "key": f"local-upload:{campaign_id}",
                    "seen": _NOW,
                },
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="统一导入已产生本地、标准观测或 updated 账本"):
        _downgrade(migration_database, "20260826_0027")

    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260827_0028"
            )
    finally:
        engine.dispose()


def test_0029_repairs_stage12_development_schema_names_and_index(
    migration_database: str,
) -> None:
    _upgrade(migration_database, "20260827_0028")
    renames = (
        (
            "historical_import_campaigns",
            "ck_historical_import_campaigns_discovered_files_nonnegative",
            "ck_historical_import_campaigns_discovered_file_count_no_c356",
        ),
        (
            "processing_import_batch_identities",
            "ck_processing_import_batch_identities_first_row_positive",
            "ck_processing_import_batch_identities_first_row_ordinal_abf7",
        ),
        (
            "processing_import_batch_item_conflicts",
            "ck_processing_import_batch_item_conflicts_version_positive",
            "ck_processing_import_batch_item_conflicts_content_versi_bd36",
        ),
        (
            "processing_import_batch_item_conflicts",
            "ck_processing_import_batch_item_conflicts_history_hash_sha256",
            "ck_processing_import_batch_item_conflicts_historical_ha_1c30",
        ),
        (
            "processing_import_batch_items",
            "ck_processing_import_batch_items_external_id_hash_sha256",
            "ck_processing_import_batch_items_external_content_id_ha_5e82",
        ),
    )
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            for table_name, canonical_name, legacy_name in renames:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} RENAME CONSTRAINT {canonical_name} TO {legacy_name}"
                )
            connection.exec_driver_sql(
                "DROP INDEX uq_historical_import_campaign_items_source_manifest"
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260827_0029")

    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        for table_name, canonical_name, legacy_name in renames:
            names = {
                constraint["name"] for constraint in inspector.get_check_constraints(table_name)
            }
            assert canonical_name in names
            assert legacy_name not in names
        assert "uq_historical_import_campaign_items_source_manifest" in {
            index["name"] for index in inspector.get_indexes("historical_import_campaign_items")
        }
    finally:
        engine.dispose()

    _downgrade(migration_database, "20260827_0028")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260827_0028"
            )
        names = {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints("processing_import_batch_items")
        }
        assert "ck_processing_import_batch_items_external_id_hash_sha256" in names
        assert "uq_historical_import_campaign_items_source_manifest" in {
            index["name"]
            for index in inspect(engine).get_indexes("historical_import_campaign_items")
        }
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260827_0029")


def test_0038_recompiles_existing_analysis_scheme_snapshots(
    migration_database: str,
) -> None:
    """历史 Scheme 经 0038 后可恢复，downgrade 后也兼容旧编译算法。"""

    _upgrade(migration_database, "20260902_0037")
    scheme_id, version_id = uuid4(), uuid4()
    definition: dict[str, object] = {
        "prompt_template": "请按以下分类输出：\n{{AIMA_TAXONOMY_JSON}}",
        "sentiments": ["正面", "无法判断"],
        "voice_types": ["真实用户发声", "无法判断"],
        # 特意使用与 PostgreSQL JSONB 返回顺序不同的插入顺序。
        "labels": {
            "无法分类": ["无法判断"],
            "产品体验": ["续航表现"],
        },
    }
    legacy_prompt, legacy_prompt_sha, legacy_taxonomy_sha = _legacy_analysis_snapshot(definition)
    engine = _engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO analysis_schemes"
                    "(id, name, active_version_id, is_active, created_at, updated_at) "
                    "VALUES (:id, '历史方案', NULL, FALSE, :now, :now)"
                ),
                {"id": scheme_id, "now": _NOW},
            )
            connection.execute(
                text(
                    "INSERT INTO analysis_scheme_versions"
                    "(id, scheme_id, version, status, description, definition, "
                    "compiled_prompt, prompt_sha256, taxonomy_sha256, created_by, "
                    "created_at, published_at) VALUES "
                    "(:id, :scheme_id, 1, 'published', '', CAST(:definition AS jsonb), "
                    ":compiled_prompt, :prompt_sha256, :taxonomy_sha256, "
                    "'migration-test', :now, :now)"
                ),
                {
                    "id": version_id,
                    "scheme_id": scheme_id,
                    "definition": json.dumps(definition, ensure_ascii=False),
                    "compiled_prompt": legacy_prompt,
                    "prompt_sha256": legacy_prompt_sha,
                    "taxonomy_sha256": legacy_taxonomy_sha,
                    "now": _NOW,
                },
            )
            connection.execute(
                text(
                    "UPDATE analysis_schemes SET active_version_id = :version_id, "
                    "is_active = TRUE WHERE id = :scheme_id"
                ),
                {"version_id": version_id, "scheme_id": scheme_id},
            )
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260902_0038")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT definition, compiled_prompt, prompt_sha256, taxonomy_sha256 "
                        "FROM analysis_scheme_versions WHERE id = :id"
                    ),
                    {"id": version_id},
                )
                .mappings()
                .one()
            )
        compiled = compile_analysis_scheme(
            AnalysisSchemeDefinitionRequest.model_validate(row["definition"])
        )
        assert row["compiled_prompt"] == compiled.prompt_text
        assert row["prompt_sha256"] == compiled.prompt_sha256
        assert row["taxonomy_sha256"] == compiled.taxonomy_sha256
    finally:
        engine.dispose()

    _downgrade(migration_database, "20260902_0037")
    engine = _engine(migration_database)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT definition, compiled_prompt, prompt_sha256, taxonomy_sha256 "
                        "FROM analysis_scheme_versions WHERE id = :id"
                    ),
                    {"id": version_id},
                )
                .mappings()
                .one()
            )
        legacy = _legacy_analysis_snapshot(row["definition"])
        assert row["compiled_prompt"] == legacy[0]
        assert row["prompt_sha256"] == legacy[1]
        assert row["taxonomy_sha256"] == legacy[2]
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260902_0038")


def test_0040_adds_and_reverses_collection_campaign_source(
    migration_database: str,
) -> None:
    """0040 只扩展 Collection Run 来源；降级移除新增关联并恢复 0039 Schema。"""

    _upgrade(migration_database, "20260903_0039")
    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        assert "data_import_campaign_id" not in {
            column["name"] for column in inspector.get_columns("collection_runs")
        }
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260903_0040")
    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        assert "data_import_campaign_id" in {
            column["name"] for column in inspector.get_columns("collection_runs")
        }
        assert any(
            foreign_key["constrained_columns"] == ["data_import_campaign_id"]
            and foreign_key["referred_table"] == "historical_import_campaigns"
            for foreign_key in inspector.get_foreign_keys("collection_runs")
        )
        assert "ck_collection_runs_import_source_at_most_one" in {
            constraint["name"] for constraint in inspector.get_check_constraints("collection_runs")
        }
        assert "ix_collection_runs_campaign_id_created_at" in {
            index["name"] for index in inspector.get_indexes("collection_runs")
        }
    finally:
        engine.dispose()

    _downgrade(migration_database, "20260903_0039")
    engine = _engine(migration_database)
    try:
        inspector = inspect(engine)
        assert "data_import_campaign_id" not in {
            column["name"] for column in inspector.get_columns("collection_runs")
        }
        assert "ck_collection_runs_import_source_at_most_one" not in {
            constraint["name"] for constraint in inspector.get_check_constraints("collection_runs")
        }
        assert "ix_collection_runs_campaign_id_created_at" not in {
            index["name"] for index in inspector.get_indexes("collection_runs")
        }
    finally:
        engine.dispose()

    _upgrade(migration_database, "20260903_0040")
