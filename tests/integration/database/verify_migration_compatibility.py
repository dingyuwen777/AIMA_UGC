"""统一执行历史 Workflow 中仍有价值的 Alembic compatibility 回归。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

_ROOT = Path(__file__).resolve().parents[3]
_CONFIG = Config(str(_ROOT / "alembic.ini"))


def _with_inspector(assertion: Callable[[object], None]) -> None:
    runtime = DatabaseRuntime(load_settings())
    try:
        assertion(inspect(runtime.engine))
    finally:
        runtime.dispose()


def _return_to_head() -> None:
    command.upgrade(_CONFIG, "head")
    command.current(_CONFIG)
    command.check(_CONFIG)


def _verify_revision(
    revision: str,
    assertion: Callable[[object], None] | None = None,
) -> None:
    command.downgrade(_CONFIG, revision)
    try:
        if assertion is not None:
            _with_inspector(assertion)
    finally:
        _return_to_head()


def _assert_stage3_foundation(inspector: object) -> None:
    tables = set(inspector.get_table_names())
    assert {"artifacts", "system_settings", "audit_events"} <= tables, tables
    assert not ({"jobs", "job_attempt_events"} & tables), tables


def _assert_job_runtime_without_collection(inspector: object) -> None:
    tables = set(inspector.get_table_names())
    previous = {
        "artifacts",
        "system_settings",
        "audit_events",
        "jobs",
        "job_attempt_events",
    }
    assert previous <= tables, tables
    assert not ({"collection_runs", "collection_scopes"} & tables), tables


def _assert_collection_without_provider_persistence(inspector: object) -> None:
    tables = set(inspector.get_table_names())
    previous = {
        "artifacts",
        "system_settings",
        "audit_events",
        "jobs",
        "job_attempt_events",
        "collection_runs",
        "collection_scopes",
    }
    assert previous <= tables, tables
    assert not ({"provider_requests", "provider_request_attempts"} & tables), tables


def _assert_pre_dispatch_provider_schema(inspector: object) -> None:
    checks = {item["name"] for item in inspector.get_check_constraints("provider_requests")}
    assert "ck_provider_requests_status_allowed" not in checks, checks


def _assert_pre_coverage_columns(inspector: object) -> None:
    columns = {item["name"] for item in inspector.get_columns("comment_coverage_observations")}
    assert "sample_mode" not in columns, columns
    assert "sort_mode" not in columns, columns
    assert "target_count" not in columns, columns
    assert "stop_reason" not in columns, columns


def _assert_base_is_empty(inspector: object) -> None:
    tables = set(inspector.get_table_names())
    application_tables = {
        "artifacts",
        "system_settings",
        "audit_events",
        "jobs",
        "job_attempt_events",
        "collection_runs",
        "collection_scopes",
        "provider_requests",
        "provider_request_attempts",
        "accounts",
        "contents",
        "comments",
        "comment_coverage_observations",
        "provider_configs",
        "keywords",
        "keyword_packs",
    }
    assert not (application_tables & tables), tables


def main() -> int:
    """验证旧正式 Revision/base 均能回到当前 head，并保留关键中间态断言。"""

    # 历史 Workflow 中带结构语义的 checkpoint。
    _verify_revision("20260813_0001", _assert_stage3_foundation)
    _verify_revision("20260814_0002", _assert_job_runtime_without_collection)
    _verify_revision("20260814_0003", _assert_collection_without_provider_persistence)
    _verify_revision("20260814_0004", _assert_pre_dispatch_provider_schema)

    # 历史 Stage 6/7 以及当前主 CI 已长期验证的升级入口。
    for revision in (
        "20260814_0005",
        "20260814_0006",
        "20260814_0008",
        "20260814_0009",
        "20260815_0010",
        "20260815_0012",
        "20260815_0013",
    ):
        _verify_revision(revision)

    _verify_revision("20260817_0015", _assert_pre_coverage_columns)
    _verify_revision("20260821_0021")
    _verify_revision("base", _assert_base_is_empty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
