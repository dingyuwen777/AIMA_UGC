from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aima_ugc.contracts.analysis import (
    ContentLabelAnalysisV3,
    ContentLabelPairV2,
    UnifiedContentRecordV1,
)
from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    PROMPT_VERSION,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomyLoader,
)

OBSERVED_AT = datetime(2026, 8, 21, 11, 30, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _content() -> CanonicalContentV1:
    return CanonicalContentV1(
        observed_fields=[
            "title",
            "text",
            "author.display_name",
            "author.bio",
            "author.verification_label",
        ],
        platform="xiaohongshu",
        external_content_id="voice-v3-content",
        content_type="note",
        title="爱玛骑了一年，续航还可以",
        text="我每天通勤骑，冬天续航会短一些，但总体够用。",
        author=CanonicalAuthorV1(
            display_name="通勤小林",
            bio="分享日常通勤和骑行体验",
            verification_label="",
        ),
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _base_fields() -> dict[str, object]:
    return {
        "prompt_version": "content-labeling.v3",
        "prompt_sha256": HASH_A,
        "taxonomy_sha256": HASH_B,
        "model_provider": "fake",
        "model": "fake-v3",
        "input_hash": HASH_C,
        "analyzed_at": OBSERVED_AT,
    }


def test_v3_contract_enforces_relevance_dependent_shape_and_voice_type() -> None:
    relevant = ContentLabelAnalysisV3(
        relevance="relevant",
        voice_type="user_voice",
        sentiment="正面",
        labels=(
            ContentLabelPairV2(
                primary_label="电池、续航与充电",
                secondary_label="实际续航表现",
            ),
        ),
        **_base_fields(),
    )
    irrelevant = ContentLabelAnalysisV3(
        relevance="irrelevant",
        voice_type="media_information",
        sentiment=None,
        labels=(),
        **_base_fields(),
    )

    assert relevant.schema_version == "content-label-analysis.v3"
    assert relevant.is_relevant is True
    assert relevant.is_user_voice is True
    assert irrelevant.is_relevant is False
    assert irrelevant.is_user_voice is False

    record = UnifiedContentRecordV1(
        content=_content(),
        matched_keywords=["爱玛"],
        analysis=irrelevant,
    )
    assert UnifiedContentRecordV1.model_validate_json(record.model_dump_json()) == record

    with pytest.raises(ValidationError):
        ContentLabelAnalysisV3(
            relevance="irrelevant",
            voice_type="unknown",
            sentiment="中性",
            labels=(),
            **_base_fields(),
        )
    with pytest.raises(ValidationError):
        ContentLabelAnalysisV3(
            relevance="relevant",
            voice_type="not-a-real-type",
            sentiment="中性",
            labels=(
                ContentLabelPairV2(primary_label="品牌评价", secondary_label="口碑与信任"),
            ),
            **_base_fields(),
        )


def test_service_returns_v3_and_sends_only_approved_public_author_context() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    fake = FakeContentLabelingLLM(
        responses=[
            json.dumps(
                {
                    "items": [
                        {
                            "item_no": 1,
                            "relevance": "relevant",
                            "voice_type": "user_voice",
                            "sentiment": taxonomy.sentiments[0],
                            "labels": [
                                {
                                    "primary_label": primary,
                                    "secondary_label": secondary,
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    analysis = result.items[0].analysis
    assert result.items[0].analysis_status == "succeeded"
    assert isinstance(analysis, ContentLabelAnalysisV3)
    assert analysis.relevance == "relevant"
    assert analysis.voice_type == "user_voice"
    assert PROMPT_VERSION == "content-labeling.v3"
    assert CONTENT_LABELING_PROMPT_PATH.name == "content_labeling_v3.md"

    payload = fake.calls[0].model_payload()[0]
    assert payload == {
        "item_no": 1,
        "title": "爱玛骑了一年，续航还可以",
        "text": "我每天通勤骑，冬天续航会短一些，但总体够用。",
        "author": {
            "display_name": "通勤小林",
            "bio": "分享日常通勤和骑行体验",
            "verification_label": "",
        },
    }


def test_service_accepts_irrelevant_without_forcing_sentiment_or_labels() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    fake = FakeContentLabelingLLM(
        responses=[
            json.dumps(
                {
                    "items": [
                        {
                            "item_no": 1,
                            "relevance": "irrelevant",
                            "voice_type": "media_information",
                            "sentiment": None,
                            "labels": [],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    analysis = result.items[0].analysis
    assert result.items[0].analysis_status == "succeeded"
    assert isinstance(analysis, ContentLabelAnalysisV3)
    assert analysis.relevance == "irrelevant"
    assert analysis.sentiment is None
    assert analysis.labels == ()
