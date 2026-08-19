from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.analysis import (
    ContentLabelAnalysisV1,
    ContentLabelAnalysisV2,
    ContentLabelPairV2,
    UnifiedContentRecordV1,
)
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomyLoader,
)
from pydantic import ValidationError

OBSERVED_AT = datetime(2026, 8, 19, 6, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _content() -> CanonicalContentV1:
    return CanonicalContentV1(
        observed_fields=["title", "text"],
        platform="xiaohongshu",
        external_content_id="multi-label-content",
        content_type="note",
        title="爱玛骑行舒服但售后客服态度差",
        text="动力不错，座椅舒服，但售后客服态度很差。",
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _analysis_v1() -> ContentLabelAnalysisV1:
    return ContentLabelAnalysisV1(
        sentiment="负面",
        primary_label="售后服务",
        secondary_label="客服与服务态度",
        prompt_version="content-labeling.v1",
        prompt_sha256=HASH_A,
        taxonomy_sha256=HASH_B,
        model_provider="legacy-provider",
        model="legacy-model",
        input_hash=HASH_C,
        analyzed_at=OBSERVED_AT,
    )


def _analysis_v2() -> ContentLabelAnalysisV2:
    return ContentLabelAnalysisV2(
        sentiment="混合",
        labels=(
            ContentLabelPairV2(
                primary_label="骑行性能",
                secondary_label="舒适性",
            ),
            ContentLabelPairV2(
                primary_label="售后服务",
                secondary_label="客服与服务态度",
            ),
        ),
        prompt_version="content-labeling.v2",
        prompt_sha256=HASH_A,
        taxonomy_sha256=HASH_B,
        model_provider="api.example.test",
        model="model-v2",
        input_hash=HASH_C,
        analyzed_at=OBSERVED_AT,
    )


def test_content_label_analysis_v2_preserves_label_pairs_and_rejects_duplicates() -> None:
    analysis = _analysis_v2()

    assert analysis.schema_version == "content-label-analysis.v2"
    assert [pair.primary_label for pair in analysis.labels] == ["骑行性能", "售后服务"]
    assert [pair.secondary_label for pair in analysis.labels] == ["舒适性", "客服与服务态度"]

    with pytest.raises(ValidationError):
        ContentLabelAnalysisV2(
            sentiment="混合",
            labels=(analysis.labels[0], analysis.labels[0]),
            prompt_version="content-labeling.v2",
            prompt_sha256=HASH_A,
            taxonomy_sha256=HASH_B,
            model_provider="api.example.test",
            model="model-v2",
            input_hash=HASH_C,
            analyzed_at=OBSERVED_AT,
        )


def test_unified_content_record_accepts_legacy_v1_and_new_v2_analysis() -> None:
    content = _content()

    legacy = UnifiedContentRecordV1(
        content=content,
        matched_keywords=["爱玛"],
        analysis=_analysis_v1(),
    )
    current = UnifiedContentRecordV1(
        content=content,
        matched_keywords=["爱玛"],
        analysis=_analysis_v2(),
    )

    assert legacy.analysis is not None
    assert legacy.analysis.schema_version == "content-label-analysis.v1"
    assert current.analysis is not None
    assert current.analysis.schema_version == "content-label-analysis.v2"
    assert UnifiedContentRecordV1.model_validate_json(legacy.model_dump_json()) == legacy
    assert UnifiedContentRecordV1.model_validate_json(current.model_dump_json()) == current


def test_service_returns_v2_with_multiple_valid_label_pairs() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    first_primary, second_primary = taxonomy.primary_labels[:2]
    response = json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "sentiment": taxonomy.sentiments[0],
                    "labels": [
                        {
                            "primary_label": first_primary,
                            "secondary_label": taxonomy.labels[first_primary][0],
                        },
                        {
                            "primary_label": second_primary,
                            "secondary_label": taxonomy.labels[second_primary][0],
                        },
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )
    fake = FakeContentLabelingLLM(responses=[response])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=0,
    )

    analysis = result.items[0].analysis
    assert result.items[0].analysis_status == "succeeded"
    assert isinstance(analysis, ContentLabelAnalysisV2)
    assert analysis is not None
    assert [(pair.primary_label, pair.secondary_label) for pair in analysis.labels] == [
        (first_primary, taxonomy.labels[first_primary][0]),
        (second_primary, taxonomy.labels[second_primary][0]),
    ]


def test_duplicate_label_pair_is_retryable_and_not_silently_deduplicated() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    pair = {
        "primary_label": primary,
        "secondary_label": taxonomy.labels[primary][0],
    }
    bad = json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "sentiment": taxonomy.sentiments[0],
                    "labels": [pair, pair],
                }
            ]
        },
        ensure_ascii=False,
    )
    good = json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "sentiment": taxonomy.sentiments[0],
                    "labels": [pair],
                }
            ]
        },
        ensure_ascii=False,
    )
    fake = FakeContentLabelingLLM(responses=[bad, good])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content()],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert len(fake.calls) == 2
    assert "duplicate_label_pair" in result.attempts[0].validation_error_codes
    assert "duplicate_label_pair" in fake.calls[1].previous_validation_error_codes
