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
)
from sqlalchemy import CheckConstraint, UniqueConstraint


def test_analysis_result_and_ordered_label_pair_schema() -> None:
    assert analysis_content_results_table.info["owner"] == "analysis"
    assert analysis_content_label_pairs_table.info["owner"] == "analysis"
    assert analysis_content_results_table.c.content_version.nullable is False
    assert analysis_content_results_table.c.job_id.nullable is False

    identities = {
        tuple(column.name for column in constraint.columns)
        for constraint in analysis_content_results_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert (
        "content_id",
        "content_version",
        "input_hash",
        "prompt_sha256",
        "taxonomy_sha256",
        "model_provider",
        "model",
    ) in identities

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
