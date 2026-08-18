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

OBSERVED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _record(content_id: str) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            observed_fields=["title", "text"],
            platform="imports",
            external_content_id=content_id,
            content_type="unknown",
            title=f"爱玛 {content_id}",
            text="正文",
            observed_at=OBSERVED_AT,
            source=CanonicalSourceV1(
                provider_name="imports",
                operation="excel_import",
                source_type="aima-monitoring-excel.v1",
                source_value="source.xlsx",
                item_locator=f"sheet=文章;row={content_id}",
                observed_at=OBSERVED_AT,
            ),
        ),
        matched_keywords=["爱玛"],
    )


def _write_records(path: Path, records: list[UnifiedContentRecordV1]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _response(*, first_valid: bool, second_valid: bool) -> str:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    secondary = taxonomy.labels[primary][0]
    sentiment = taxonomy.sentiments[0]
    items: list[dict[str, object]] = []
    if first_valid:
        items.append(
            {
                "item_no": 1,
                "sentiment": sentiment,
                "primary_label": primary,
                "secondary_label": secondary,
            }
        )
    if second_valid:
        items.append(
            {
                "item_no": 2,
                "sentiment": sentiment,
                "primary_label": primary,
                "secondary_label": secondary,
            }
        )
    else:
        items.append(
            {
                "item_no": 2,
                "sentiment": "不存在的情感",
                "primary_label": primary,
                "secondary_label": secondary,
            }
        )
    return json.dumps({"items": items}, ensure_ascii=False)


def test_offline_labeling_checkpoints_success_and_rewrites_only_validated_analysis(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(input_path, [_record("content-1"), _record("content-2")])
    fake = FakeContentLabelingLLM(responses=[_response(first_valid=True, second_valid=False)])
    service = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
        llm=fake,
    )

    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=service,
        max_validation_retries=0,
        batch_size=2,
    )

    assert summary.rows_seen == 2
    assert summary.rows_succeeded == 1
    assert summary.rows_failed == 1
    assert summary.llm_attempts == 1
    records = [UnifiedContentRecordV1.model_validate(item) for item in _read_jsonl(input_path)]
    assert records[0].analysis is not None
    assert records[1].analysis is None

    checkpoints = _read_jsonl(analysis_dir / "checkpoints.jsonl")
    attempts = _read_jsonl(analysis_dir / "attempts.jsonl")
    failed = _read_jsonl(analysis_dir / "failed.jsonl")
    assert len(checkpoints) == 1
    assert checkpoints[0]["external_content_id"] == "content-1"
    assert checkpoints[0]["analysis"]["analysis_status"] == "succeeded"
    assert len(attempts) == 1
    assert attempts[0]["item_nos"] == [1, 2]
    assert attempts[0]["validation_error_codes"] == ["unknown_sentiment"]
    assert len(failed) == 1
    assert failed[0]["external_content_id"] == "content-2"
    assert failed[0]["analysis_status"] == "failed"
    assert failed[0]["validation_error_codes"] == ["unknown_sentiment"]


def test_offline_labeling_validation_retry_only_retries_unresolved_item(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(input_path, [_record("content-1"), _record("content-2")])
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    valid_second_only = json.dumps(
        {
            "items": [
                {
                    "item_no": 2,
                    "sentiment": taxonomy.sentiments[0],
                    "primary_label": primary,
                    "secondary_label": taxonomy.labels[primary][0],
                }
            ]
        },
        ensure_ascii=False,
    )
    fake = FakeContentLabelingLLM(
        responses=[
            _response(first_valid=True, second_valid=False),
            valid_second_only,
        ]
    )
    service = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
        llm=fake,
    )

    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=service,
        max_validation_retries=1,
        batch_size=2,
    )

    assert summary.rows_succeeded == 2
    assert summary.rows_failed == 0
    assert summary.llm_attempts == 2
    assert [item.item_no for item in fake.calls[0].items] == [1, 2]
    assert [item.item_no for item in fake.calls[1].items] == [2]
    assert len(_read_jsonl(analysis_dir / "checkpoints.jsonl")) == 2
    attempts = _read_jsonl(analysis_dir / "attempts.jsonl")
    assert [item["item_nos"] for item in attempts] == [[1, 2], [2]]
    assert not (analysis_dir / "failed.jsonl").read_text(encoding="utf-8")


def test_offline_labeling_checkpoint_survives_if_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    original = _record("content-1")
    _write_records(input_path, [original])
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    valid = json.dumps(
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
    service = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
        llm=FakeContentLabelingLLM(responses=[valid]),
    )

    def fail_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("aima_ugc.modules.analysis.offline_labeling.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        label_unified_content_jsonl(
            input_path=input_path,
            analysis_dir=analysis_dir,
            service=service,
            max_validation_retries=0,
            batch_size=1,
        )

    current = UnifiedContentRecordV1.model_validate_json(input_path.read_bytes())
    assert current.analysis is None
    checkpoints = _read_jsonl(analysis_dir / "checkpoints.jsonl")
    assert len(checkpoints) == 1
    assert checkpoints[0]["external_content_id"] == "content-1"
    assert not (input_path.parent / ".contents.jsonl.labeling.tmp").exists()


def test_offline_labeling_skips_records_already_labeled_in_business_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(input_path, [_record("content-1")])
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    valid = json.dumps(
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
    first_service = ContentLabelingService(
        prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
        llm=FakeContentLabelingLLM(responses=[valid]),
    )
    label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=first_service,
        max_validation_retries=0,
        batch_size=1,
    )

    second_fake = FakeContentLabelingLLM(responses=[])
    second_summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=ContentLabelingService(
            prompt_loader=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH),
            llm=second_fake,
        ),
        max_validation_retries=0,
        batch_size=1,
    )

    assert second_summary.rows_seen == 1
    assert second_summary.rows_already_labeled == 1
    assert second_summary.rows_succeeded == 0
    assert second_summary.rows_failed == 0
    assert second_summary.llm_attempts == 0
    assert second_fake.calls == []
