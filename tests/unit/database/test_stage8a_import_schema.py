"""Stage 8A Processing/Import Batch 与 Provider 来源父级 Schema 契约。"""

from aima_ugc.modules.collection.tables import provider_requests_table
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from sqlalchemy import CheckConstraint, UniqueConstraint


def test_processing_import_batch_is_minimal_owner_table() -> None:
    assert processing_import_batches_table.info["owner"] == "ingestion"
    assert set(processing_import_batches_table.c.keys()) == {
        "id",
        "input_artifact_id",
        "job_id",
        "historical_mode",
        "historical_campaign_item_id",
        "historical_policy_version",
        "retry_of_batch_id",
        "status",
        "stats",
        "error_summary",
        "created_at",
        "started_at",
        "finished_at",
    }
    assert processing_import_batches_table.c.input_artifact_id.nullable is False
    assert processing_import_batches_table.c.job_id.nullable is True
    assert processing_import_batches_table.c.historical_mode.nullable is False
    assert processing_import_batches_table.c.historical_campaign_item_id.nullable is True
    assert processing_import_batches_table.c.historical_policy_version.nullable is True
    assert processing_import_batches_table.c.retry_of_batch_id.nullable is True


def test_processing_import_batch_accepts_both_unified_import_policies() -> None:
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in processing_import_batches_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    historical_fields = next(
        (
            sql
            for name, sql in checks.items()
            if name is not None and name.endswith("historical_fields_consistent")
        ),
        None,
    )

    assert historical_fields is not None
    assert "historical-fill-only.v1" in historical_fields
    assert "standard-observation.v1" in historical_fields
    assert "historical_mode =" in historical_fields


def test_provider_request_has_exactly_one_source_parent() -> None:
    assert provider_requests_table.c.scope_id.nullable is True
    assert provider_requests_table.c.import_batch_id.nullable is True

    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in provider_requests_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    source_parent = next(
        (
            sql
            for name, sql in checks.items()
            if name is not None and name.endswith("source_parent_exactly_one")
        ),
        None,
    )
    assert source_parent is not None
    assert "scope_id" in source_parent
    assert "import_batch_id" in source_parent

    uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in provider_requests_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("scope_id", "request_fingerprint") in uniques
    assert ("import_batch_id", "request_fingerprint") in uniques
