from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.adapters.llm import OpenAICompatibleLLMError
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis import (
    CONTENT_LABELING_PROMPT_PATH,
    ContentLabelingLLMRequest,
    ContentLabelingService,
    FrozenPromptTaxonomyLoader,
    PromptTaxonomyLoader,
    label_unified_content_jsonl,
)

_OBSERVED_AT = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)


class _FatalLLM:
    calls = 0

    @property
    def provider_name(self) -> str:
        return "api.deepseek.com"

    @property
    def model_name(self) -> str:
        return "model-a"

    def complete(self, request: ContentLabelingLLMRequest):
        self.calls += 1
        raise OpenAICompatibleLLMError(
            "OpenAI-compatible LLM 请求失败: HTTP 401",
            error_code="http_401",
            retryable=False,
            status_code=401,
        )


def _record(content_id: str) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            observed_fields=["title", "text"],
            platform="xiaohongshu",
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


def test_fatal_canary_error_stops_before_expanding_to_250_requests(tmp_path: Path) -> None:
    input_path = tmp_path / "deduplicated" / "contents.jsonl"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(
        "".join(_record(f"content-{index}").model_dump_json() + "\n" for index in range(10)),
        encoding="utf-8",
    )
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    llm = _FatalLLM()
    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=llm,
    )

    with pytest.raises(OpenAICompatibleLLMError) as exc_info:
        label_unified_content_jsonl(
            input_path=input_path,
            analysis_dir=tmp_path / "analysis",
            service=service,
            max_validation_retries=2,
            max_concurrency=250,
            recovery_taxonomy=taxonomy,
        )

    assert exc_info.value.status_code == 401
    assert llm.calls == 1
