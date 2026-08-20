"""Stage 8D 声音广场公共 HTTP Contract。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.api import create_app
from aima_ugc.contracts.http import (
    ContentAnalysisResponse,
    ContentAnalysisSubmitRequest,
    ContentLabelPairResponse,
    ContentListItemResponse,
    ContentListQuery,
    ContentListResponse,
    ContentMetricsResponse,
    ContentSourceResponse,
    ContentTargetSelection,
    DataExportSubmitRequest,
)
from pydantic import ValidationError


def _item() -> ContentListItemResponse:
    now = datetime(2026, 8, 21, tzinfo=UTC)
    return ContentListItemResponse(
        id=uuid4(),
        platform="xiaohongshu",
        external_content_id="note-1",
        content_type="note",
        title="续航体验",
        text="正文",
        author_display_name="用户甲",
        published_at=now,
        last_seen_at=now,
        content_url="https://example.com/note-1",
        metrics=ContentMetricsResponse(like_count=12, comment_count=3),
        analysis=ContentAnalysisResponse(
            status="completed",
            sentiment="负面",
            labels=(
                ContentLabelPairResponse(primary_label="产品体验", secondary_label="续航表现"),
                ContentLabelPairResponse(primary_label="服务体验", secondary_label="门店服务"),
            ),
            analyzed_at=now,
        ),
        source=ContentSourceResponse(provider_name="file-import"),
    )


def test_content_response_preserves_every_ordered_ai_label() -> None:
    response = ContentListResponse(items=(_item(),), next_cursor=None, has_more=False)

    assert [
        (label.primary_label, label.secondary_label) for label in response.items[0].analysis.labels
    ] == [("产品体验", "续航表现"), ("服务体验", "门店服务")]


def test_content_query_rejects_naive_or_reversed_dates() -> None:
    with pytest.raises(ValidationError):
        ContentListQuery(published_from=datetime(2026, 8, 21))
    with pytest.raises(ValidationError):
        ContentListQuery(
            published_from=datetime(2026, 8, 22, tzinfo=UTC),
            published_to=datetime(2026, 8, 21, tzinfo=UTC),
        )


def test_analysis_and_export_require_a_nonempty_frozen_target_selection() -> None:
    selected = ContentTargetSelection(scope="selected", content_ids=(uuid4(), uuid4()))
    assert ContentAnalysisSubmitRequest(targets=selected).targets.scope == "selected"
    assert DataExportSubmitRequest(targets=selected).format == "xlsx"

    with pytest.raises(ValidationError):
        ContentTargetSelection(scope="selected", content_ids=())
    with pytest.raises(ValidationError):
        ContentTargetSelection(scope="query", content_ids=(uuid4(),))


def test_excel_download_openapi_response_is_binary() -> None:
    response = create_app().openapi()["paths"]["/api/v1/data-exports/{export_id}/download"]["get"][
        "responses"
    ]["200"]["content"]["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"][
        "schema"
    ]

    assert response == {"type": "string", "format": "binary"}
