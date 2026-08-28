from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.http import (
    ContentAnalysisResponse,
    ContentFilterSnapshot,
    ContentLabelPairResponse,
)
from pydantic import ValidationError

ANALYZED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_content_analysis_response_exposes_relevance_and_voice_type_only() -> None:
    relevant = ContentAnalysisResponse(
        status="completed",
        relevance="relevant",
        voice_type="真实用户发声",
        sentiment="正面",
        labels=(
            ContentLabelPairResponse(
                primary_label="品牌评价",
                secondary_label="口碑与信任",
            ),
        ),
        analyzed_at=ANALYZED_AT,
        model_provider="fake",
        model="fake-v3",
    )
    irrelevant = ContentAnalysisResponse(
        status="completed",
        relevance="irrelevant",
        voice_type="媒体机构发声",
        sentiment=None,
        labels=(),
        analyzed_at=ANALYZED_AT,
        model_provider="fake",
        model="fake-v3",
    )

    assert relevant.relevance == "relevant"
    assert relevant.voice_type == "真实用户发声"
    assert "is_user_voice" not in relevant.model_dump()
    assert irrelevant.relevance == "irrelevant"
    assert irrelevant.voice_type == "媒体机构发声"
    assert irrelevant.sentiment is None
    assert irrelevant.labels == ()

    with pytest.raises(ValidationError):
        ContentAnalysisResponse(
            status="completed",
            relevance="irrelevant",
            voice_type="无法判断",
            sentiment="中性",
            labels=(),
            analyzed_at=ANALYZED_AT,
        )


def test_content_filter_snapshot_can_explicitly_query_relevance_and_voice_type() -> None:
    filters = ContentFilterSnapshot(
        relevance="irrelevant",
        voice_type="媒体机构发声",
    )

    assert filters.relevance == "irrelevant"
    assert filters.voice_type == "媒体机构发声"
