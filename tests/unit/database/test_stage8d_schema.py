"""Stage 8D Analysis 与 Reporting 数据契约。"""

from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_request_items_table,
    analysis_content_requests_table,
    analysis_content_results_table,
)
from aima_ugc.modules.reporting.tables import (
    reporting_data_export_items_table,
    reporting_data_exports_table,
    reporting_user_export_column_defaults_table,
)
from sqlalchemy import CheckConstraint, UniqueConstraint


def test_analysis_result_and_ordered_label_pair_schema() -> None:
    assert analysis_content_results_table.info["owner"] == "analysis"
    assert analysis_content_label_pairs_table.info["owner"] == "analysis"
    assert analysis_content_results_table.c.content_version.nullable is False
    assert analysis_content_results_table.c.analysis_run_id.nullable is False
    assert analysis_content_results_table.c.job_id.nullable is False

    identities = {
        tuple(column.name for column in constraint.columns)
        for constraint in analysis_content_results_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("analysis_run_id", "content_id", "content_version") in identities

    assert analysis_content_label_pairs_table.primary_key.columns.keys() == [
        "analysis_result_id",
        "ordinal",
    ]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in analysis_content_label_pairs_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert any("ordinal" in expression and ">= 0" in expression for expression in checks.values())


def test_reporting_export_links_job_and_artifact_without_duplicate_status() -> None:
    assert reporting_data_exports_table.info["owner"] == "reporting"
    assert reporting_data_exports_table.c.job_id.nullable is False
    assert reporting_data_exports_table.c.artifact_id.nullable is True
    assert "status" not in reporting_data_exports_table.c
    uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in reporting_data_exports_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("job_id",) in uniques
    assert ("artifact_id",) in uniques
    checks = {
        str(constraint.sqltext)
        for constraint in reporting_data_exports_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert any(
        "artifact_id is null" in expression
        and "stats is null" in expression
        and "completed_at is null" in expression
        for expression in checks
    )


def test_analysis_and_export_requests_freeze_content_version_targets() -> None:
    assert analysis_content_requests_table.info["owner"] == "analysis"
    assert analysis_content_request_items_table.info["owner"] == "analysis"
    assert reporting_data_export_items_table.info["owner"] == "reporting"
    assert analysis_content_request_items_table.primary_key.columns.keys() == [
        "request_id",
        "content_id",
    ]
    assert reporting_data_export_items_table.primary_key.columns.keys() == [
        "export_id",
        "content_id",
    ]
    assert analysis_content_request_items_table.c.content_version.nullable is False
    assert reporting_data_export_items_table.c.content_version.nullable is False
    item_checks = {
        str(constraint.sqltext)
        for constraint in analysis_content_request_items_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert any(
        "status = 'succeeded'" in expression
        and "analysis_result_id is not null" in expression
        and "error_code is null" in expression
        for expression in item_checks
    )


def test_export_owner_index_and_personal_defaults_have_reporting_owner() -> None:
    """未知历史归属可为空；开发身份的配置不依赖正式外部身份表。"""
    assert reporting_data_exports_table.c.created_by.nullable is True
    index = next(
        item
        for item in reporting_data_exports_table.indexes
        if item.name == "ix_reporting_data_exports_owner_recent"
    )
    assert [str(expression) for expression in index.expressions] == [
        "reporting_data_exports.created_by",
        "reporting_data_exports.created_at DESC",
        "reporting_data_exports.id DESC",
    ]
    defaults = reporting_user_export_column_defaults_table
    assert defaults.info["owner"] == "reporting"
    assert list(defaults.primary_key.columns.keys()) == ["principal_id"]
    assert not defaults.foreign_keys
    assert defaults.c.selected_columns.nullable is True
    assert defaults.c.revision.nullable is False
