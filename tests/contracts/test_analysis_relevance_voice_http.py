from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.http import (
    ContentAnalysisResponse,
    ContentFilterSnapshot,
    ContentLabelPairResponse,
)
from pydantic import ValidationError

ANALYZED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_content_analysis_response_exposes_relevance_voice_type_and_derived_user_voice() -> None:
    relevant = ContentAnalysisResponse(
        status="completed",
        relevance="relevant",
        voice_type="user_voice",
        is_user_voice=True,
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
        voice_type="media_information",
        is_user_voice=False,
        sentiment=None,
        labels=(),
        analyzed_at=ANALYZED_AT,
        model_provider="fake",
        model="fake-v3",
    )

    assert relevant.relevance == "relevant"
    assert relevant.voice_type == "user_voice"
    assert relevant.is_user_voice is True
    assert irrelevant.relevance == "irrelevant"
    assert irrelevant.sentiment is None
    assert irrelevant.labels == ()

    # is_user_voice 是 voice_type 的确定性派生值，Contract 必须拒绝两者互相矛盾。
    with pytest.raises(ValidationError):
        ContentAnalysisResponse(
            status="completed",
            relevance="relevant",
            voice_type="user_voice",
            is_user_voice=False,
            sentiment="正面",
            labels=(
                ContentLabelPairResponse(
                    primary_label="品牌评价",
                    secondary_label="口碑与信任",
                ),
            ),
            analyzed_at=ANALYZED_AT,
        )
    with pytest.raises(ValidationError):
        ContentAnalysisResponse(
            status="completed",
            relevance="irrelevant",
            voice_type="unknown",
            is_user_voice=False,
            sentiment="中性",
            labels=(),
            analyzed_at=ANALYZED_AT,
        )


def test_content_filter_snapshot_can_explicitly_query_relevance_and_voice_type() -> None:
    filters = ContentFilterSnapshot(
        relevance="irrelevant",
        voice_type="media_information",
    )

    assert filters.relevance == "irrelevant"
    assert filters.voice_type == "media_information"
