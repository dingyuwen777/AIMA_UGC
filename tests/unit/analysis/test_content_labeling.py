from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aima_ugc.contracts.analysis import ContentLabelAnalysisV1, UnifiedContentRecordV1
from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
)
from aima_ugc.modules.analysis.content_labeling import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    ContentLabelingValidationError,
    FakeContentLabelingLLM,
    PromptTaxonomy,
    PromptTaxonomyError,
    PromptTaxonomyLoader,
    RuntimeTaxonomyValidator,
)

OBSERVED_AT = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def _analysis_docs() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "docs" / "appendix" / "07_AI舆情打标与分析实现.md").read_text(encoding="utf-8")


def _prompt_with_taxonomy_mutation(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> Path:
    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"(<!-- AIMA_TAXONOMY_START -->\s*```json\s*)(.*?)(\s*```\s*<!-- AIMA_TAXONOMY_END -->)",
        prompt,
        flags=re.DOTALL,
    )
    assert match is not None
    payload: dict[str, Any] = json.loads(match.group(2))
    mutate(payload)
    replacement = json.dumps(payload, ensure_ascii=False, indent=2)
    mutated = prompt[: match.start(2)] + replacement + prompt[match.end(2) :]
    path = tmp_path / "content_labeling_v1.md"
    path.write_text(mutated, encoding="utf-8")
    return path


def _valid_response(taxonomy: PromptTaxonomy, item_nos: tuple[int, ...]) -> str:
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    sentiment = taxonomy.sentiments[0]
    return json.dumps(
        {
            "items": [
                {
                    "item_no": item_no,
                    "relevance": "relevant",
                    "voice_type": "无法判断",
                    "sentiment": sentiment,
                    "labels": [{"primary_label": primary, "secondary_label": secondary}],
                }
                for item_no in item_nos
            ]
        },
        ensure_ascii=False,
    )


def _label_content(
    *,
    external_content_id: str,
    title: str | None = "爱玛体验",
    text: str | None = "正文",
    author_display_name: str | None = "作者",
) -> CanonicalContentV1:
    author = (
        CanonicalAuthorV1(
            display_name=author_display_name,
            external_account_id="private-account-id",
            follower_count=98765,
        )
        if author_display_name is not None
        else None
    )
    observed_fields = [
        "title",
        "text",
        "canonical_url",
        "metrics.like_count",
    ]
    if author is not None:
        observed_fields.extend(
            [
                "author.display_name",
                "author.external_account_id",
                "author.follower_count",
            ]
        )
    return CanonicalContentV1(
        observed_fields=observed_fields,
        platform="xiaohongshu",
        external_content_id=external_content_id,
        content_type="note",
        title=title,
        text=text,
        canonical_url=f"https://www.xiaohongshu.com/explore/{external_content_id}",
        author=author,
        observed_at=OBSERVED_AT,
        metrics=CanonicalMetricsV1(like_count=1234),
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="aima-monitoring-excel.v1",
            source_value="source.xlsx",
            item_locator="sheet=文章;row=2",
            observed_at=OBSERVED_AT,
        ),
    )


def test_prompt_taxonomy_has_expected_baseline_and_documented_bootstrap_source() -> None:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    docs = _analysis_docs()

    assert len(taxonomy.primary_labels) == 10
    assert len(taxonomy.all_secondary_labels) == 40
    assert "backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md" in docs
    assert "active Analysis Scheme Version" in docs
    assert "bootstrap/灾备基线" in docs


def test_production_python_does_not_copy_concrete_taxonomy_labels() -> None:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    root = Path(__file__).resolve().parents[3] / "backend" / "src" / "aima_ugc"
    python_files = [
        *sorted((root / "contracts" / "analysis").rglob("*.py")),
        *sorted((root / "modules" / "analysis").rglob("*.py")),
    ]
    labels = (*taxonomy.primary_labels, *taxonomy.all_secondary_labels)

    for path in python_files:
        source = path.read_text(encoding="utf-8")
        copied = [label for label in labels if label in source]
        assert copied == [], f"{path} 不得硬编码具体标签: {copied}"


def test_prompt_contains_required_human_judgment_sections() -> None:
    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")

    assert "## 情感判断标准" in prompt
    assert "## 一级/二级标签判断标准" in prompt
    assert "### 一级/二级标签高混淆场景" in prompt
    assert "### 一级/二级标签示例" in prompt
    assert "典型表达只作理解辅助" in prompt


def test_prompt_taxonomy_changes_are_runtime_driven_without_python_changes(tmp_path: Path) -> None:
    original = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    def add_label(payload: dict[str, Any]) -> None:
        payload["labels"]["临时测试一级"] = ["临时测试二级"]

    changed = PromptTaxonomyLoader(_prompt_with_taxonomy_mutation(tmp_path, add_label)).load()

    assert changed.primary_labels == (*original.primary_labels, "临时测试一级")
    assert changed.labels["临时测试一级"] == ("临时测试二级",)
    assert changed.taxonomy_sha256 != original.taxonomy_sha256


def test_removed_prompt_label_is_immediately_rejected_by_runtime_validator(tmp_path: Path) -> None:
    original = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = original.primary_labels[0]
    removed_secondary = original.labels[primary][0]

    def remove_label(payload: dict[str, Any]) -> None:
        payload["labels"][primary].remove(removed_secondary)

    changed = PromptTaxonomyLoader(_prompt_with_taxonomy_mutation(tmp_path, remove_label)).load()
    validator = RuntimeTaxonomyValidator(changed)

    with pytest.raises(ContentLabelingValidationError) as exc_info:
        validator.validate_labels(
            sentiment=changed.sentiments[0],
            primary_label=primary,
            secondary_label=removed_secondary,
        )

    assert "invalid_secondary_for_primary" in exc_info.value.error_codes


def test_runtime_validator_rejects_secondary_from_another_primary() -> None:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    first_primary, second_primary = taxonomy.primary_labels[:2]
    validator = RuntimeTaxonomyValidator(taxonomy)

    with pytest.raises(ContentLabelingValidationError) as exc_info:
        validator.validate_labels(
            sentiment=taxonomy.sentiments[0],
            primary_label=first_primary,
            secondary_label=taxonomy.labels[second_primary][0],
        )

    assert exc_info.value.error_codes == ("invalid_secondary_for_primary",)


@pytest.mark.parametrize(
    "failure_kind", ["duplicate_sentiment", "duplicate_secondary", "empty_secondary"]
)
def test_invalid_prompt_taxonomy_fails_before_llm_call(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()

    def mutate(payload: dict[str, Any]) -> None:
        if failure_kind == "duplicate_sentiment":
            payload["sentiments"].append(payload["sentiments"][0])
        elif failure_kind == "duplicate_secondary":
            first_primary, second_primary = list(payload["labels"])[:2]
            payload["labels"][second_primary].append(payload["labels"][first_primary][0])
        else:
            first_primary = next(iter(payload["labels"]))
            payload["labels"][first_primary][0] = ""

    loader = PromptTaxonomyLoader(_prompt_with_taxonomy_mutation(tmp_path, mutate))
    fake = FakeContentLabelingLLM(responses=["{}"])
    service = ContentLabelingService(prompt_loader=loader, llm=fake)

    with pytest.raises(PromptTaxonomyError):
        service.label_contents(
            [_label_content(external_content_id="content-1")],
            max_validation_retries=0,
        )

    assert fake.calls == []


def test_invalid_taxonomy_json_is_rejected(tmp_path: Path) -> None:
    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"(<!-- AIMA_TAXONOMY_START -->\s*```json\s*)(.*?)(\s*```\s*<!-- AIMA_TAXONOMY_END -->)",
        prompt,
        flags=re.DOTALL,
    )
    assert match is not None
    broken = prompt[: match.start(2)] + "{not-json}" + prompt[match.end(2) :]
    path = tmp_path / "content_labeling_v1.md"
    path.write_text(broken, encoding="utf-8")

    with pytest.raises(PromptTaxonomyError):
        PromptTaxonomyLoader(path).load()


def test_model_request_only_contains_approved_business_fields_and_fills_missing_values() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    fake = FakeContentLabelingLLM(responses=[_valid_response(taxonomy, (1,))])
    service = ContentLabelingService(prompt_loader=loader, llm=fake)

    result = service.label_contents(
        [
            _label_content(
                external_content_id="secret-content-id",
                title=None,
                text=None,
                author_display_name=None,
            )
        ],
        max_validation_retries=0,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert fake.calls[0].model_payload() == [
        {
            "item_no": 1,
            "title": "",
            "text": "",
            "author": {"display_name": "", "bio": "", "verification_label": ""},
        }
    ]
    serialized = json.dumps(fake.calls[0].model_payload(), ensure_ascii=False)
    for forbidden in (
        "secret-content-id",
        "xiaohongshu",
        "imports",
        "source.xlsx",
        "sheet=文章;row=2",
        "private-account-id",
        "98765",
        "1234",
    ):
        assert forbidden not in serialized


def test_prompt_and_taxonomy_hashes_change_at_the_correct_boundary(tmp_path: Path) -> None:
    original = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    text_only_path = tmp_path / "text-only.md"
    text_only_path.write_text(
        CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8") + "\n<!-- text-only-change -->\n",
        encoding="utf-8",
    )
    text_only = PromptTaxonomyLoader(text_only_path).load()

    def add_label(payload: dict[str, Any]) -> None:
        payload["labels"]["临时Hash一级"] = ["临时Hash二级"]

    taxonomy_changed = PromptTaxonomyLoader(
        _prompt_with_taxonomy_mutation(tmp_path, add_label)
    ).load()

    assert text_only.prompt_sha256 != original.prompt_sha256
    assert text_only.taxonomy_sha256 == original.taxonomy_sha256
    assert taxonomy_changed.prompt_sha256 != original.prompt_sha256
    assert taxonomy_changed.taxonomy_sha256 != original.taxonomy_sha256


@pytest.mark.parametrize(
    ("bad_response_factory", "expected_code"),
    [
        (lambda taxonomy: "not-json", "invalid_json"),
        (
            lambda taxonomy: json.dumps(
                {
                    "items": [
                        {
                            "item_no": 1,
                            "relevance": "relevant",
                            "voice_type": "无法判断",
                            "sentiment": "不存在的情感",
                            "labels": [
                                {
                                    "primary_label": taxonomy.primary_labels[0],
                                    "secondary_label": taxonomy.labels[taxonomy.primary_labels[0]][
                                        0
                                    ],
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "unknown_sentiment",
        ),
        (
            lambda taxonomy: json.dumps(
                {
                    "items": [
                        {
                            "item_no": 1,
                            "relevance": "relevant",
                            "voice_type": "无法判断",
                            "sentiment": taxonomy.sentiments[0],
                            "labels": [
                                {
                                    "primary_label": taxonomy.primary_labels[0],
                                    "secondary_label": taxonomy.labels[taxonomy.primary_labels[1]][
                                        0
                                    ],
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "invalid_secondary_for_primary",
        ),
        (lambda taxonomy: json.dumps({"items": []}), "missing_item"),
    ],
)
def test_fake_invalid_responses_trigger_validation_retry(
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
    service = ContentLabelingService(prompt_loader=loader, llm=fake)

    result = service.label_contents(
        [_label_content(external_content_id="content-1")],
        max_validation_retries=1,
    )

    assert result.items[0].analysis_status == "succeeded"
    assert len(fake.calls) == 2
    assert expected_code in result.attempts[0].validation_error_codes
    assert expected_code in fake.calls[1].previous_validation_error_codes


@pytest.mark.parametrize("max_validation_retries", [0, 1, 2])
def test_validation_retry_limit_has_exact_total_request_semantics(
    max_validation_retries: int,
) -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    fake = FakeContentLabelingLLM(responses=["not-json"] * (max_validation_retries + 1))
    service = ContentLabelingService(prompt_loader=loader, llm=fake)

    result = service.label_contents(
        [_label_content(external_content_id="content-1")],
        max_validation_retries=max_validation_retries,
    )

    assert len(fake.calls) == max_validation_retries + 1
    assert [attempt.attempt_no for attempt in result.attempts] == list(
        range(1, max_validation_retries + 2)
    )
    assert result.items[0].analysis_status == "failed"
    assert result.items[0].analysis is None
    assert result.items[0].validation_error_codes == ("invalid_json",)


def test_successful_item_is_not_retried_when_another_item_needs_validation_retry() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    sentiment = taxonomy.sentiments[0]
    first_response = json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": "relevant",
                    "voice_type": "无法判断",
                    "sentiment": sentiment,
                    "labels": [{"primary_label": primary, "secondary_label": secondary}],
                },
                {
                    "item_no": 2,
                    "relevance": "relevant",
                    "voice_type": "无法判断",
                    "sentiment": "不存在的情感",
                    "labels": [{"primary_label": primary, "secondary_label": secondary}],
                },
            ]
        },
        ensure_ascii=False,
    )
    fake = FakeContentLabelingLLM(
        responses=[
            first_response,
            _valid_response(taxonomy, (2,)),
        ]
    )
    service = ContentLabelingService(prompt_loader=loader, llm=fake)

    result = service.label_contents(
        [
            _label_content(external_content_id="content-1"),
            _label_content(external_content_id="content-2"),
        ],
        max_validation_retries=1,
    )

    assert [item.analysis_status for item in result.items] == ["succeeded", "succeeded"]
    assert [item.item_no for item in fake.calls[0].items] == [1, 2]
    assert [item.item_no for item in fake.calls[1].items] == [2]
    assert result.attempts[0].validation_error_codes == ("unknown_sentiment",)


def test_analysis_contract_uses_strings_and_unified_record_accepts_valid_analysis() -> None:
    loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    taxonomy = loader.load()
    fake = FakeContentLabelingLLM(responses=[_valid_response(taxonomy, (1,))])
    content = _label_content(external_content_id="content-1")
    result = ContentLabelingService(prompt_loader=loader, llm=fake).label_contents(
        [content],
        max_validation_retries=0,
    )
    analysis = result.items[0].analysis

    assert analysis is not None
    assert ContentLabelAnalysisV1.model_fields["sentiment"].annotation is str
    assert ContentLabelAnalysisV1.model_fields["primary_label"].annotation is str
    assert ContentLabelAnalysisV1.model_fields["secondary_label"].annotation is str
    record = UnifiedContentRecordV1(
        content=content,
        matched_keywords=["爱玛"],
        analysis=analysis,
    )
    assert record.analysis == analysis
