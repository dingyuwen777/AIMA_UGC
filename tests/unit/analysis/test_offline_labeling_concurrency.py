from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock

import pytest
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingLLMRequest,
    ContentLabelingLLMResponse,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomyLoader,
    label_unified_content_jsonl,
)

_OBSERVED_AT = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)


def _record(content_id: str) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            observed_fields=["title", "text"],
            platform="imports",
            external_content_id=content_id,
            content_type="unknown",
            title=f"爱玛 {content_id}",
            text="正文",
            observed_at=_OBSERVED_AT,
            source=CanonicalSourceV1(
                provider_name="imports",
                operation="excel_import",
                source_type="aima-monitoring-excel.v1",
                source_value="source.xlsx",
                item_locator=f"sheet=文章;row={content_id}",
                observed_at=_OBSERVED_AT,
            ),
        ),
        matched_keywords=["爱玛"],
    )


def _write(path: Path, records: list[UnifiedContentRecordV1]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )


def _valid_response() -> str:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    primary = taxonomy.primary_labels[0]
    return json.dumps(
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
                            "secondary_label": taxonomy.labels[primary][0],
                        }
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )


class _ConcurrencyProbeLLM:
    def __init__(self, *, expected_parallel: int) -> None:
        self._expected_parallel = expected_parallel
        self._lock = Lock()
        self._release = Event()
        self._call_count = 0
        self.active = 0
        self.peak_active = 0
        self.item_counts: list[int] = []

    @property
    def provider_name(self) -> str:
        return "probe"

    @property
    def model_name(self) -> str:
        return "probe-model"

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        with self._lock:
            self._call_count += 1
            call_no = self._call_count
            self.item_counts.append(len(request.items))
            if call_no == 1:  # Canary 不占并发测量窗口。
                return ContentLabelingLLMResponse(raw_text=_valid_response())
            self.active += 1
            self.peak_active = max(self.peak_active, self.active)
            if self.active == self._expected_parallel:
                self._release.set()
        assert self._release.wait(timeout=5)
        with self._lock:
            self.active -= 1
        return ContentLabelingLLMResponse(raw_text=_valid_response())


def _service(llm) -> ContentLabelingService:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    return ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=llm,
    )


def test_offline_labeling_uses_single_item_requests_and_bounded_sliding_window(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    records = [_record(f"content-{index}") for index in range(1, 8)]
    _write(input_path, records)
    llm = _ConcurrencyProbeLLM(expected_parallel=3)

    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=tmp_path / "analysis",
        service=_service(llm),
        max_validation_retries=0,
        max_concurrency=3,
        recovery_taxonomy=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load(),
    )

    assert summary.rows_succeeded == 7
    assert summary.rows_irrelevant_removed == 0
    assert summary.peak_in_flight == 3
    assert llm.peak_active == 3
    assert llm.item_counts == [1] * 7
    rewritten = [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record.content.external_content_id for record in rewritten] == [
        record.content.external_content_id for record in records
    ]
    assert all(record.analysis is not None for record in rewritten)


def test_duplicate_stable_identity_fails_before_any_llm_request(tmp_path: Path) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    duplicate = _record("same-id")
    _write(input_path, [duplicate, duplicate])
    llm = _ConcurrencyProbeLLM(expected_parallel=1)

    with pytest.raises(ValueError, match="重复稳定内容身份"):
        label_unified_content_jsonl(
            input_path=input_path,
            analysis_dir=tmp_path / "analysis",
            service=_service(llm),
            max_validation_retries=0,
            max_concurrency=3,
            recovery_taxonomy=PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load(),
        )

    assert llm.item_counts == []
