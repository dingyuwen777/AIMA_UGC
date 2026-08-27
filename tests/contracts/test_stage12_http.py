"""Stage 12 Historical Campaign 与 Analysis Run HTTP Contract。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.contracts.http import (
    HistoricalCampaignCreateRequest,
    HistoricalCampaignResponse,
    HistoricalDirectoryListQuery,
    LocalDataImportCampaignCreateRequest,
)
from pydantic import ValidationError


def test_historical_campaign_request_accepts_relative_selection_and_frozen_keyword_packs() -> None:
    pack_id = uuid4()
    request = HistoricalCampaignCreateRequest(
        client_idempotency_key="stage12-import-001",
        relative_paths=("2024/history.xlsx",),
        recursive=False,
        keyword_pack_ids=(pack_id,),
    )
    assert request.relative_paths == ("2024/history.xlsx",)
    assert request.keyword_pack_ids == (pack_id,)
    assert request.ingestion_policy == "historical_fill_only"


def test_local_campaign_manifest_keeps_relative_paths_and_policy_independent() -> None:
    pack_id = uuid4()
    request = LocalDataImportCampaignCreateRequest(
        client_idempotency_key="local-folder-001",
        files=(
            {"relative_path": "folder/a.xlsx", "byte_size": 128},
            {"relative_path": "folder/nested/b.xlsx", "byte_size": 256},
        ),
        keyword_pack_ids=(pack_id,),
        ingestion_policy="historical_fill_only",
    )

    assert request.ingestion_policy == "historical_fill_only"
    assert tuple(item.relative_path for item in request.files) == (
        "folder/a.xlsx",
        "folder/nested/b.xlsx",
    )


@pytest.mark.parametrize("value", ("../escape.xlsx", "/absolute.xlsx", r"a\b.xlsx", "a.csv"))
def test_local_campaign_manifest_rejects_unsafe_or_non_xlsx_paths(value: str) -> None:
    with pytest.raises(ValidationError):
        LocalDataImportCampaignCreateRequest(
            client_idempotency_key="local-folder-002",
            files=({"relative_path": value, "byte_size": 1},),
            keyword_pack_ids=(uuid4(),),
        )


@pytest.mark.parametrize("value", ("../escape", "/absolute", r"C:\absolute", r"a\b"))
def test_historical_campaign_request_rejects_unsafe_paths(value: str) -> None:
    with pytest.raises(ValidationError):
        HistoricalCampaignCreateRequest(
            client_idempotency_key="stage12-import-002",
            relative_paths=(value,),
            keyword_pack_ids=(uuid4(),),
        )


def test_historical_directory_query_has_bounded_page_size() -> None:
    assert HistoricalDirectoryListQuery(relative_path="", limit=500).limit == 500
    with pytest.raises(ValidationError):
        HistoricalDirectoryListQuery(relative_path="", limit=501)


def test_campaign_response_exposes_preflight_and_fill_only_outcomes() -> None:
    response = HistoricalCampaignResponse(
        id=uuid4(),
        status="ready",
        source_kind="local_upload",
        ingestion_policy="standard_observation",
        declared_file_count=2,
        root_relative_path="2024",
        recursive=True,
        discovered_file_count=2,
        ready_item_count=2,
        total_rows=100,
        progress={
            "preflight_completed_file_count": 2,
            "preflight_percent": 100,
            "migration_completed_row_count": 25,
            "migration_percent": 25,
        },
        stats={
            "created": 1,
            "filled": 2,
            "unchanged": 3,
            "conflict": 4,
            "filtered": 5,
            "duplicate": 6,
            "invalid": 7,
            "failed": 8,
        },
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    assert response.can_start is True
    assert response.stats.conflict == 4
    assert response.progress.preflight_completed_file_count == 2
    assert response.progress.migration_percent == 25
    assert response.source_kind == "local_upload"
    assert response.ingestion_policy == "standard_observation"


def test_campaign_progress_rejects_percent_outside_contract_range() -> None:
    with pytest.raises(ValidationError):
        HistoricalCampaignResponse(
            id=uuid4(),
            status="running",
            root_relative_path="2024",
            recursive=True,
            discovered_file_count=2,
            ready_item_count=2,
            total_rows=100,
            progress={
                "preflight_completed_file_count": 2,
                "preflight_percent": 100,
                "migration_completed_row_count": 25,
                "migration_percent": 101,
            },
            created_at=datetime(2026, 8, 26, tzinfo=UTC),
        )
