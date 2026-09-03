"""长期 PostgreSQL Schema 关键不变量回归。"""

from __future__ import annotations

from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import inspect, text


def test_current_schema_preserves_job_collection_and_provider_invariants() -> None:
    """承接历史 Stage CI 中仍有独立价值的数据库结构断言。"""

    runtime = DatabaseRuntime(load_settings())
    try:
        inspector = inspect(runtime.engine)
        tables = set(inspector.get_table_names())

        required_tables = {
            "artifacts",
            "system_settings",
            "audit_events",
            "jobs",
            "job_attempt_events",
            "collection_runs",
            "collection_scopes",
            "provider_requests",
            "provider_request_attempts",
        }
        assert required_tables <= tables, tables

        run_foreign_keys = inspector.get_foreign_keys("collection_runs")
        run_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("collection_runs")
        }
        scope_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("collection_scopes")
        }
        run_indexes = {item["name"] for item in inspector.get_indexes("collection_runs")}
        run_checks = {item["name"] for item in inspector.get_check_constraints("collection_runs")}
        scope_indexes = {item["name"] for item in inspector.get_indexes("collection_scopes")}

        assert any(
            item["constrained_columns"] == ["job_id"]
            and item["referred_table"] == "jobs"
            and item["referred_columns"] == ["id"]
            for item in run_foreign_keys
        ), run_foreign_keys
        assert any(
            item["constrained_columns"] == ["data_import_campaign_id"]
            and item["referred_table"] == "historical_import_campaigns"
            and item["referred_columns"] == ["id"]
            for item in run_foreign_keys
        ), run_foreign_keys
        assert ("job_id",) in run_uniques, run_uniques
        assert (
            "run_id",
            "platform",
            "source_type",
            "source_value",
            "operation_group",
        ) in scope_uniques, scope_uniques
        assert "ix_collection_runs_status_created_at" in run_indexes, run_indexes
        assert "ix_collection_runs_campaign_id_created_at" in run_indexes, run_indexes
        assert "ck_collection_runs_import_source_at_most_one" in run_checks, run_checks
        assert "ix_collection_scopes_run_id_status" in scope_indexes, scope_indexes

        request_foreign_keys = inspector.get_foreign_keys("provider_requests")
        attempt_foreign_keys = inspector.get_foreign_keys("provider_request_attempts")
        request_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("provider_requests")
        }
        attempt_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("provider_request_attempts")
        }
        request_checks = {
            item["name"] for item in inspector.get_check_constraints("provider_requests")
        }
        attempt_checks = {
            item["name"] for item in inspector.get_check_constraints("provider_request_attempts")
        }
        request_indexes = {item["name"] for item in inspector.get_indexes("provider_requests")}
        attempt_indexes = {
            item["name"] for item in inspector.get_indexes("provider_request_attempts")
        }

        assert any(
            item["constrained_columns"] == ["scope_id"]
            and item["referred_table"] == "collection_scopes"
            and item["referred_columns"] == ["id"]
            for item in request_foreign_keys
        ), request_foreign_keys
        assert any(
            item["constrained_columns"] == ["provider_request_id"]
            and item["referred_table"] == "provider_requests"
            for item in attempt_foreign_keys
        ), attempt_foreign_keys
        assert any(
            item["constrained_columns"] == ["raw_artifact_id"]
            and item["referred_table"] == "artifacts"
            for item in attempt_foreign_keys
        ), attempt_foreign_keys
        assert ("scope_id", "request_fingerprint") in request_uniques, request_uniques
        assert ("provider_request_id", "attempt_no") in attempt_uniques, attempt_uniques
        assert ("id", "provider_request_id") in attempt_uniques, attempt_uniques
        assert "ck_provider_requests_request_fingerprint_sha256" in request_checks, request_checks
        assert "ck_provider_requests_status_allowed" in request_checks, request_checks
        assert "ck_provider_request_attempts_dispatch_times_consistent" in attempt_checks, (
            attempt_checks
        )
        assert "ck_provider_request_attempts_billing_status_allowed" in attempt_checks, (
            attempt_checks
        )
        assert "ix_provider_requests_scope_id_created_at" in request_indexes, request_indexes
        assert "ix_provider_attempts_dispatch_status_started_at" in attempt_indexes, attempt_indexes
        assert "ix_provider_request_attempts_completed_at" in attempt_indexes, attempt_indexes

        with runtime.engine.connect() as connection:
            triggers = set(
                connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE NOT tgisinternal AND tgrelid IN "
                        "('collection_scopes'::regclass, 'provider_requests'::regclass, "
                        "'provider_request_attempts'::regclass)"
                    )
                ).scalars()
            )
            function_body = connection.scalar(
                text("SELECT pg_get_functiondef('guard_provider_attempt_lineage()'::regprocedure)")
            )

        assert triggers == {
            "trg_collection_scope_provider_identity_immutable",
            "trg_provider_request_lineage_immutable",
            "trg_provider_attempt_lineage_immutable",
        }, triggers
        assert function_body is not None
        assert "completed/unknown" in function_body
        assert "已绑定的 Raw 引用不可修改" in function_body
    finally:
        runtime.dispose()
