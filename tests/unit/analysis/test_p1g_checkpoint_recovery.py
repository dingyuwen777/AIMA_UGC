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
            platform="imports",
            external_content_id="content-1",
            content_type="unknown",
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


def _valid_response() -> str:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    return json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "sentiment": taxonomy.sentiments[0],
                    "primary_label": primary,
                    "secondary_label": taxonomy.labels[primary][0],
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

    first_service = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
        llm=FakeContentLabelingLLM(responses=[_valid_response()]),
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
            )

    before_recovery = UnifiedContentRecordV1.model_validate_json(input_path.read_bytes())
    assert before_recovery.analysis is None

    second_fake = FakeContentLabelingLLM(responses=[])
    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=ContentLabelingService(
            prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
            llm=second_fake,
        ),
        max_validation_retries=0,
        batch_size=1,
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
