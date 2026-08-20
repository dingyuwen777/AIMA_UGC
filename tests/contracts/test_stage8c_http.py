from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.http import ImportBatchListQuery
from aima_ugc.entrypoints.api_main import create_app
from pydantic import ValidationError


def test_stage8c_openapi_exposes_list_summary_and_stable_error_contracts() -> None:
    paths = create_app().openapi()["paths"]

    list_operation = paths["/api/v1/import-batches"]["get"]
    summary_operation = paths["/api/v1/import-batches/summary"]["get"]
    assert list_operation["operationId"] == "listImportBatches"
    assert summary_operation["operationId"] == "getImportBatchSummary"
    assert {parameter["name"] for parameter in list_operation["parameters"]} == {
        "identifier",
        "status",
        "stage",
        "created_from",
        "created_to",
        "cursor",
        "limit",
    }
    assert list_operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ImportBatchListResponse")
    assert summary_operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ImportBatchSummaryResponse")
    for operation in (list_operation, summary_operation):
        for status_code in ("422", "500"):
            assert operation["responses"][status_code]["content"]["application/json"]["schema"][
                "$ref"
            ].endswith("/HttpErrorResponse")
    for status_code in ("400", "503"):
        assert list_operation["responses"][status_code]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/HttpErrorResponse")


def test_import_batch_list_query_requires_aware_ordered_datetimes() -> None:
    valid = ImportBatchListQuery(
        created_from=datetime(2026, 8, 19, tzinfo=UTC),
        created_to=datetime(2026, 8, 20, tzinfo=UTC),
    )
    assert valid.limit == 20

    with pytest.raises(ValidationError):
        ImportBatchListQuery(created_from=datetime(2026, 8, 20))
    with pytest.raises(ValidationError):
        ImportBatchListQuery(
            created_from=datetime(2026, 8, 21, tzinfo=UTC),
            created_to=datetime(2026, 8, 20, tzinfo=UTC),
        )
