from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.export import UnifiedDataExcelAnalysisV1
from aima_ugc.contracts.http import (
    ContentAnalysisResponse,
    ContentLabelPairResponse,
)
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PROMPT_VERSION
from pydantic import ValidationError

ANALYZED_AT = datetime(2026, 8, 21, 13, 35, tzinfo=UTC)


def _completed_http_analysis(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "completed",
        "relevance": "relevant",
        "voice_type": "真实用户发声",
        "sentiment": "正面",
        "labels": (
            ContentLabelPairResponse(
                primary_label="品牌评价",
                secondary_label="口碑与信任",
            ),
        ),
        "analyzed_at": ANALYZED_AT,
    }
    payload.update(overrides)
    return payload


def test_http_analysis_uses_voice_type_as_the_only_user_voice_fact() -> None:
    response = ContentAnalysisResponse(**_completed_http_analysis())

    assert "is_user_voice" not in ContentAnalysisResponse.model_fields
    assert "is_user_voice" not in response.model_dump()

    with pytest.raises(ValidationError):
        ContentAnalysisResponse(**_completed_http_analysis(is_user_voice=True))


def test_excel_analysis_uses_voice_type_as_the_only_user_voice_fact() -> None:
    analysis = UnifiedDataExcelAnalysisV1(
        voice_type="真实用户发声",
        sentiment="正面",
        primary_label="品牌评价",
        secondary_label="口碑与信任",
    )

    assert "is_user_voice" not in UnifiedDataExcelAnalysisV1.model_fields
    assert "is_user_voice" not in analysis.model_dump()

    with pytest.raises(ValidationError):
        UnifiedDataExcelAnalysisV1(
            voice_type="真实用户发声",
            is_user_voice=True,
            sentiment="正面",
            primary_label="品牌评价",
            secondary_label="口碑与信任",
        )


def test_prompt_v3_focuses_voice_classification_on_combined_visible_evidence() -> None:
    assert PROMPT_VERSION == "content-labeling.v3"
    assert CONTENT_LABELING_PROMPT_PATH.name == "content_labeling_v3.md"

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    assert "is_user_voice" not in prompt
    assert "主体证据" in prompt
    assert "表达目的证据" in prompt
    assert "作者展示名" in prompt
    assert "公开简介" in prompt
    assert "认证文案" in prompt
    assert "标题" in prompt
    assert "正文" in prompt
    assert "证据不足" in prompt
    assert "无法判断" in prompt
