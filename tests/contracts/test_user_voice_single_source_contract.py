from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.export import UnifiedDataExcelAnalysisV1
from aima_ugc.contracts.http import (
    ContentAnalysisResponse,
    ContentLabelPairResponse,
)
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    PROMPT_VERSION,
    PromptTaxonomyLoader,
)
from pydantic import ValidationError

ANALYZED_AT = datetime(2026, 8, 21, 13, 35, tzinfo=UTC)


def test_production_prompt_directory_has_one_content_labeling_asset() -> None:
    """生产目录只保留唯一打标 Prompt，并继续保留代表内容筛选 Prompt。"""

    prompt_directory = CONTENT_LABELING_PROMPT_PATH.parent

    assert CONTENT_LABELING_PROMPT_PATH.name == "content_labeling.md"
    assert sorted(path.name for path in prompt_directory.glob("content_labeling*")) == [
        "content_labeling.md"
    ]
    assert not (prompt_directory / "jingpin_shaixuan.md").exists()
    assert (prompt_directory / "zhengfu_shaixuan.md").is_file()


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


def test_bootstrap_prompt_separates_source_intent_and_evidence_without_parallel_flag() -> None:
    taxonomy = PromptTaxonomyLoader().load()
    assert PROMPT_VERSION == "content-labeling.v3.0"
    assert taxonomy.prompt_version == PROMPT_VERSION
    assert taxonomy.output_protocol_version == PROMPT_VERSION

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    assert "is_user_voice" not in prompt
    assert "source_type" in prompt
    assert "content_intent" in prompt
    assert "voice_evidence" in prompt
    assert "品牌官方发声" in prompt
    assert "真实用户发声" in prompt
    assert "营销推广发声" in prompt
    assert "个人交易发声" not in taxonomy.voice_types
    for input_field in (
        "title",
        "text",
        "author.display_name",
        "author.bio",
        "author.verification_label",
    ):
        assert input_field in prompt
    assert "无法判断" not in taxonomy.voice_types
