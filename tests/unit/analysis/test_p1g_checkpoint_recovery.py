from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FakeContentLabelingLLM,
    PromptTaxonomyLoader,
    label_unified_content_jsonl,
)

_OBSERVED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _record() -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            observed_fields=["title", "text"],
            platform="xiaohongshu",
            external_content_id="content-1",
            content_type="无法判断",
            title="爱玛新品",
            text="正文",
            observed_at=_OBSERVED_AT,
            source=CanonicalSourceV1(
                provider_name="imports",
                operation="excel_import",
                source_type="aima-monitoring-excel.v1",
                source_value="source.xlsx",
                item_locator="sheet=文章;row=2",
                observed_at=_OBSERVED_AT,
            ),
        ),
        matched_keywords=["爱玛"],
    )


def _valid_response(loader: PromptTaxonomyLoader | None = None) -> str:
    taxonomy = (loader or PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)).load()
    primary = taxonomy.primary_labels[0]
    return json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": "relevant",
                    "voice_type": "真实用户发声",
                    "sentiment": taxonomy.sentiments[0],
                    "labels": [
                        {
                            "primary_label": primary,
                            "secondary_label": taxonomy.labels[primary][0],
                        }
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )


def test_p1g_recovers_successful_checkpoint_without_second_llm_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(_record().model_dump_json() + "\n", encoding="utf-8")

    prompt_loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    recovery_taxonomy = prompt_loader.load()
    first_service = ContentLabelingService(
        prompt_loader=prompt_loader,
        llm=FakeContentLabelingLLM(responses=[_valid_response(prompt_loader)]),
    )

    def fail_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
        raise OSError("replace failed")

    with monkeypatch.context() as patch:
        patch.setattr("aima_ugc.modules.analysis.offline_labeling.os.replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            label_unified_content_jsonl(
                input_path=input_path,
                analysis_dir=analysis_dir,
                service=first_service,
                max_validation_retries=0,
                batch_size=1,
                recovery_taxonomy=recovery_taxonomy,
            )

    before_recovery = UnifiedContentRecordV1.model_validate_json(input_path.read_bytes())
    assert before_recovery.analysis is None

    second_fake = FakeContentLabelingLLM(responses=[])
    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=ContentLabelingService(
            prompt_loader=prompt_loader,
            llm=second_fake,
        ),
        max_validation_retries=0,
        batch_size=1,
        recovery_taxonomy=recovery_taxonomy,
    )

    recovered = UnifiedContentRecordV1.model_validate_json(input_path.read_bytes())
    assert recovered.analysis is not None
    assert summary.rows_seen == 1
    assert summary.rows_recovered == 1
    assert summary.rows_succeeded == 0
    assert summary.llm_attempts == 0
    assert second_fake.calls == []
    checkpoints = analysis_dir / "checkpoints.jsonl"
    assert len(checkpoints.read_text(encoding="utf-8").splitlines()) == 1


def test_p1g_does_not_recover_checkpoint_from_different_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(_record().model_dump_json() + "\n", encoding="utf-8")

    first_loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    first_taxonomy = first_loader.load()
    first_service = ContentLabelingService(
        prompt_loader=first_loader,
        llm=FakeContentLabelingLLM(responses=[_valid_response(first_loader)]),
    )

    def fail_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
        raise OSError("replace failed")

    with monkeypatch.context() as patch:
        patch.setattr("aima_ugc.modules.analysis.offline_labeling.os.replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            label_unified_content_jsonl(
                input_path=input_path,
                analysis_dir=analysis_dir,
                service=first_service,
                max_validation_retries=0,
                batch_size=1,
                recovery_taxonomy=first_taxonomy,
            )

    changed_prompt = tmp_path / "content_labeling_changed.md"
    changed_prompt.write_text(
        CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
        + "\n<!-- P1G prompt revision -->\n",
        encoding="utf-8",
    )
    second_loader = PromptTaxonomyLoader(changed_prompt)
    second_taxonomy = second_loader.load()
    second_fake = FakeContentLabelingLLM(responses=[_valid_response(second_loader)])
    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=ContentLabelingService(prompt_loader=second_loader, llm=second_fake),
        max_validation_retries=0,
        batch_size=1,
        recovery_taxonomy=second_taxonomy,
    )

    rewritten = UnifiedContentRecordV1.model_validate_json(input_path.read_bytes())
    assert rewritten.analysis is not None
    assert rewritten.analysis.prompt_sha256 == second_taxonomy.prompt_sha256
    assert summary.rows_recovered == 0
    assert summary.rows_succeeded == 1
    assert summary.llm_attempts == 1
    assert len(second_fake.calls) == 1


@pytest.mark.parametrize(
    ("second_provider", "second_model"),
    [
        ("provider-b", "model-a"),
        ("provider-a", "model-b"),
    ],
)
def test_p1g_does_not_recover_checkpoint_from_different_model_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    second_provider: str,
    second_model: str,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(_record().model_dump_json() + "\n", encoding="utf-8")

    prompt_loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    recovery_taxonomy = prompt_loader.load()
    first_fake = FakeContentLabelingLLM(
        responses=[_valid_response(prompt_loader)],
        provider_name="provider-a",
        model_name="model-a",
    )
    first_service = ContentLabelingService(prompt_loader=prompt_loader, llm=first_fake)

    def fail_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
        raise OSError("replace failed")

    with monkeypatch.context() as patch:
        patch.setattr("aima_ugc.modules.analysis.offline_labeling.os.replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            label_unified_content_jsonl(
                input_path=input_path,
                analysis_dir=analysis_dir,
                service=first_service,
                max_validation_retries=0,
                batch_size=1,
                recovery_taxonomy=recovery_taxonomy,
            )

    second_fake = FakeContentLabelingLLM(
        responses=[_valid_response(prompt_loader)],
        provider_name=second_provider,
        model_name=second_model,
    )
    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=ContentLabelingService(prompt_loader=prompt_loader, llm=second_fake),
        max_validation_retries=0,
        batch_size=1,
        recovery_taxonomy=recovery_taxonomy,
    )

    rewritten = UnifiedContentRecordV1.model_validate_json(input_path.read_bytes())
    assert rewritten.analysis is not None
    assert rewritten.analysis.model_provider == second_provider
    assert rewritten.analysis.model == second_model
    assert summary.rows_recovered == 0
    assert summary.rows_succeeded == 1
    assert summary.llm_attempts == 1
    assert len(second_fake.calls) == 1
