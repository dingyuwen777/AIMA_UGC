from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingService,
    FakeContentLabelingLLM,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomyLoader,
    label_unified_content_jsonl,
)
from aima_ugc.modules.analysis.content_labeling import ContentLabelingLLMResponse

OBSERVED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _record(content_id: str) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            observed_fields=["title", "text"],
            platform="xiaohongshu",
            external_content_id=content_id,
            content_type="无法判断",
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


def _valid_response() -> str:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
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


def _invalid_response() -> str:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    return json.dumps(
        {
            "items": [
                {
                    "item_no": 1,
                    "relevance": "relevant",
                    "voice_type": "真实用户发声",
                    "sentiment": "不存在的情感",
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


def _service(fake: FakeContentLabelingLLM) -> ContentLabelingService:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    return ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=fake,
    )


def test_offline_labeling_checkpoints_success_and_isolates_failed_item(tmp_path: Path) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(input_path, [_record("content-1"), _record("content-2")])
    fake = FakeContentLabelingLLM(responses=[_valid_response(), _invalid_response()])

    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=_service(fake),
        max_validation_retries=0,
        max_concurrency=1,
    )

    assert summary.rows_seen == 2
    assert summary.rows_succeeded == 1
    assert summary.rows_failed == 1
    assert summary.rows_irrelevant_removed == 0
    assert summary.llm_attempts == 2
    assert all(len(call.items) == 1 for call in fake.calls)
    records = [UnifiedContentRecordV1.model_validate(item) for item in _read_jsonl(input_path)]
    assert records[0].analysis is not None
    assert records[1].analysis is None

    checkpoints = _read_jsonl(analysis_dir / "checkpoints.jsonl")
    attempts = _read_jsonl(analysis_dir / "attempts.jsonl")
    failed = _read_jsonl(analysis_dir / "failed.jsonl")
    assert [item["external_content_id"] for item in checkpoints] == ["content-1"]
    assert [item["item_nos"] for item in attempts] == [[1], [1]]
    assert failed[0]["external_content_id"] == "content-2"
    assert failed[0]["validation_error_codes"] == ["unknown_sentiment"]


def test_offline_labeling_validation_retry_retries_only_same_single_content(tmp_path: Path) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(input_path, [_record("content-1")])
    fake = FakeContentLabelingLLM(responses=[_invalid_response(), _valid_response()])

    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=_service(fake),
        max_validation_retries=1,
        max_concurrency=1,
    )

    assert summary.rows_succeeded == 1
    assert summary.rows_failed == 0
    assert summary.rows_irrelevant_removed == 0
    assert summary.llm_attempts == 2
    assert len(fake.calls) == 2
    assert [item.item_no for item in fake.calls[0].items] == [1]
    assert [item.item_no for item in fake.calls[1].items] == [1]
    attempts = _read_jsonl(analysis_dir / "attempts.jsonl")
    assert [item["item_nos"] for item in attempts] == [[1], [1]]
    assert not (analysis_dir / "failed.jsonl").read_text(encoding="utf-8")


def test_offline_labeling_checkpoint_survives_if_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    original = _record("content-1")
    _write_records(input_path, [original])
    service = _service(FakeContentLabelingLLM(responses=[_valid_response()]))

    def fail_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("aima_ugc.modules.analysis.offline_labeling.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        label_unified_content_jsonl(
            input_path=input_path,
            analysis_dir=analysis_dir,
            service=service,
            max_validation_retries=0,
            max_concurrency=1,
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
    first_fake = FakeContentLabelingLLM(responses=[_valid_response()])
    label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=_service(first_fake),
        max_validation_retries=0,
        max_concurrency=1,
    )

    second_fake = FakeContentLabelingLLM(responses=[])
    second_summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=_service(second_fake),
        max_validation_retries=0,
        max_concurrency=1,
    )

    assert second_summary.rows_seen == 1
    assert second_summary.rows_already_labeled == 1
    assert second_summary.rows_succeeded == 0
    assert second_summary.rows_failed == 0
    assert second_summary.rows_irrelevant_removed == 0
    assert second_summary.llm_attempts == 0
    assert second_fake.calls == []


def test_offline_labeling_attempt_keeps_usage_and_pricing_snapshot(tmp_path: Path) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    analysis_dir = tmp_path / "analysis"
    _write_records(input_path, [_record("content-1")])
    fake = FakeContentLabelingLLM(
        responses=[
            ContentLabelingLLMResponse(
                raw_text=_valid_response(),
                input_tokens=31,
                input_cache_hit_tokens=20,
                input_cache_miss_tokens=11,
                output_tokens=17,
                cost_amount=Decimal("0.0001355"),
                cost_currency="CNY",
                pricing_snapshot_sha256="a" * 64,
                pricing_source_url="https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
            )
        ]
    )

    label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=analysis_dir,
        service=_service(fake),
        max_validation_retries=0,
        max_concurrency=1,
    )

    attempt = _read_jsonl(analysis_dir / "attempts.jsonl")[0]
    assert attempt["schema_version"] == "content-label-attempt.v2"
    assert attempt["logical_request_id"]
    assert attempt["input_tokens"] == 31
    assert attempt["input_cache_hit_tokens"] == 20
    assert attempt["input_cache_miss_tokens"] == 11
    assert attempt["output_tokens"] == 17
    assert attempt["cost_amount"] == "0.0001355"
    assert attempt["cost_currency"] == "CNY"
    assert attempt["pricing_snapshot_sha256"] == "a" * 64
