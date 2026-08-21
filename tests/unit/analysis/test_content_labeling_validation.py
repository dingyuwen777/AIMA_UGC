from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis.content_labeling import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomy,
    PromptTaxonomyLoader,
)

OBSERVED_AT = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def _content(external_content_id: str) -> CanonicalContentV1:
    return CanonicalContentV1(
        observed_fields=["title", "text"],
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="note",
        title="爱玛体验",
        text="正文",
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            observed_at=OBSERVED_AT,
        ),
    )


def _label_item(taxonomy: PromptTaxonomy, *, item_no: int) -> dict[str, object]:
    primary = taxonomy.primary_labels[0]
    return {
        "item_no": item_no,
        "relevance": "relevant",
        "voice_type": "unknown",
        "sentiment": taxonomy.sentiments[0],
        "labels": [
            {
                "primary_label": primary,
                "secondary_label": taxonomy.labels[primary][0],
            }
        ],
    }


def _valid_response(taxonomy: PromptTaxonomy, item_nos: tuple[int, ...]) -> str:
    return json.dumps(
        {"items": [_label_item(taxonomy, item_no=item_no) for item_no in item_nos]},
        ensure_ascii=False,
    )


def _missing_required_field(taxonomy: PromptTaxonomy) -> str:
    item = _label_item(taxonomy, item_no=1)
    item.pop("voice_type")
    return json.dumps({"items": [item]}, ensure_ascii=False)


def _extra_field(taxonomy: PromptTaxonomy) -> str:
    item = _label_item(taxonomy, item_no=1)
    item["explanation"] = "不得输出"
    return json.dumps({"items": [item]}, ensure_ascii=False)


def _duplicate_item(taxonomy: PromptTaxonomy) -> str:
    item = _label_item(taxonomy, item_no=1)
    return json.dumps({"items": [item, dict(item)]}, ensure_ascii=False)


def _unexpected_item_no(taxonomy: PromptTaxonomy) -> str:
    return json.dumps(
        {"items": [_label_item(taxonomy, item_no=2)]},
        ensure_ascii=False,
    )


def _first_label(item: dict[str, object]) -> dict[str, object]:
    labels = item["labels"]
    assert isinstance(labels, list) and len(labels) == 1
    label = labels[0]
    assert isinstance(label, dict)
    return label


def _unknown_primary(taxonomy: PromptTaxonomy) -> str:
    item = _label_item(taxonomy, item_no=1)
    _first_label(item)["primary_label"] = "不存在的一级标签"
    return json.dumps({"items": [item]}, ensure_ascii=False)


def _array_label(taxonomy: PromptTaxonomy) -> str:
    item = _label_item(taxonomy, item_no=1)
    _first_label(item)["primary_label"] = [taxonomy.primary_labels[0]]
    return json.dumps({"items": [item]}, ensure_ascii=False)


def _empty_label(taxonomy: PromptTaxonomy) -> str:
    item = _label_item(taxonomy, item_no=1)
    _first_label(item)["secondary_label"] = ""
    return json.dumps({"items": [item]}, ensure_ascii=False)


def _top_level_extra_field(taxonomy: PromptTaxonomy) -> str:
    return json.dumps(
        {
            "items": [_label_item(taxonomy, item_no=1)],
            "explanation": "不得输出",
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    ("bad_response_factory", "expected_code"),
    [
        (_missing_required_field, "invalid_item_structure"),
        (_extra_field, "invalid_item_structure"),
        (_duplicate_item, "duplicate_item"),
        (_unexpected_item_no, "unexpected_item_no"),
        (_unknown_primary, "unknown_primary_label"),
        (_array_label, "invalid_item_structure"),
        (_empty_label, "invalid_item_structure"),
        (_top_level_extra_field, "invalid_response_structure"),
    ],
)
def test_explicit_invalid_output_categories_are_validation_retryable(
    bad_response_factory: Callable[[PromptTaxonomy], str],
    expected_code: str,
) -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    fake = FakeContentLabelingLLM(
        responses=[
            bad_response_factory(taxonomy),
            _valid_response(taxonomy, (1,)),
        ]
    )

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content("content-1")],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert len(fake.calls) == 2
    assert expected_code in result.attempts[0].validation_error_codes
    assert expected_code in fake.calls[1].previous_validation_error_codes


def test_item_order_mismatch_retries_the_whole_unresolved_batch() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    bad = json.dumps(
        {
            "items": [
                _label_item(taxonomy, item_no=2),
                _label_item(taxonomy, item_no=1),
            ]
        },
        ensure_ascii=False,
    )
    fake = FakeContentLabelingLLM(responses=[bad, _valid_response(taxonomy, (1, 2))])

    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [_content("content-1"), _content("content-2")],
        max_validation_retries=1,
    )

    assert [item.analysis_status for item in result.items] == ["succeeded", "succeeded"]
    assert len(fake.calls) == 2
    assert result.attempts[0].validation_error_codes == ("item_order_mismatch",)
    assert [item.item_no for item in fake.calls[1].items] == [1, 2]
