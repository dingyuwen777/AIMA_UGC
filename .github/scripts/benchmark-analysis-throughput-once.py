from __future__ import annotations

import json
import runpy
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

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

CONCURRENCY = 4
ROW_COUNT = 8
REQUEST_LATENCY_SECONDS = 3.0
MIN_FORMAL_TO_OFFLINE_THROUGHPUT_RATIO = 0.90
OBSERVED_AT = datetime(2026, 9, 4, 1, 0, tzinfo=UTC)


def record(content_id: str) -> UnifiedContentRecordV1:
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            observed_fields=["title", "text"],
            platform="xiaohongshu",
            external_content_id=content_id,
            content_type="无法判断",
            title=f"爱玛 {content_id}",
            text="受控吞吐基准正文",
            observed_at=OBSERVED_AT,
            source=CanonicalSourceV1(
                provider_name="imports",
                operation="excel_import",
                source_type="aima-monitoring-excel.v1",
                source_value="throughput-benchmark.xlsx",
                item_locator=f"sheet=文章;row={content_id}",
                observed_at=OBSERVED_AT,
            ),
        ),
        matched_keywords=["爱玛"],
    )


def write_records(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(record(f"benchmark-{index}").model_dump_json() + "\n" for index in range(ROW_COUNT)),
        encoding="utf-8",
    )


class LatencyFakeLLM:
    provider_name = "fake-db"
    model_name = "fake-content-labeler-v1"

    def __init__(self, raw_response: str) -> None:
        self._raw_response = raw_response
        self._lock = Lock()
        self._active = 0
        self.peak_active = 0
        self.item_sizes: list[int] = []

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        with self._lock:
            self._active += 1
            self.peak_active = max(self.peak_active, self._active)
            self.item_sizes.append(len(request.items))
        try:
            time.sleep(REQUEST_LATENCY_SECONDS)
            return ContentLabelingLLMResponse(raw_text=self._raw_response)
        finally:
            with self._lock:
                self._active -= 1


def measure_offline(root: Path, raw_response: str) -> tuple[float, int]:
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    llm = LatencyFakeLLM(raw_response)
    service = ContentLabelingService(
        prompt_loader=FrozenPromptTaxonomyLoader(taxonomy),
        llm=llm,
    )
    input_path = root / "offline" / "contents.jsonl"
    write_records(input_path)
    started = time.perf_counter()
    summary = label_unified_content_jsonl(
        input_path=input_path,
        analysis_dir=root / "offline-analysis",
        service=service,
        max_validation_retries=0,
        max_concurrency=CONCURRENCY,
        recovery_taxonomy=taxonomy,
    )
    elapsed = time.perf_counter() - started
    assert summary.rows_succeeded == ROW_COUNT
    assert summary.peak_in_flight == CONCURRENCY
    assert llm.peak_active == CONCURRENCY
    assert llm.item_sizes == [1] * ROW_COUNT
    return elapsed, summary.rows_succeeded


def measure_formal(root: Path, raw_response: str) -> tuple[float, int]:
    namespace = runpy.run_path("tests/integration/content/test_analysis_provider_concurrency.py")
    runtime_factory = namespace["_runtime"]
    seed_provider = namespace["_seed_provider"]
    client_factory = namespace["_client"]
    seed_contents = namespace["_seed_contents"]
    create_run = namespace["_create_run"]
    drain = namespace["_drain"]

    runtime = runtime_factory(root / "formal")
    try:
        seed_provider(runtime, max_concurrency=CONCURRENCY)
        client = client_factory(runtime)
        content_ids = seed_contents(client, runtime)
        assert len(content_ids) == ROW_COUNT
        run_id = create_run(client, content_ids, key="controlled-throughput-benchmark")
        llm = LatencyFakeLLM(raw_response)
        started = time.perf_counter()
        job_count = drain(runtime, llm, worker_id="controlled-throughput-benchmark")
        elapsed = time.perf_counter() - started
        assert job_count == 2
        assert llm.peak_active == CONCURRENCY
        assert llm.item_sizes == [1] * ROW_COUNT
        run = client.get(f"/api/v1/analysis/content-runs/{run_id}")
        assert run.status_code == 200
        payload = run.json()
        assert payload["status"] == "succeeded"
        assert payload["stats"]["succeeded"] == ROW_COUNT
        return elapsed, ROW_COUNT
    finally:
        runtime.close()


def main() -> None:
    namespace = runpy.run_path("tests/integration/content/test_analysis_provider_concurrency.py")
    raw_response = namespace["_valid_response"]()
    with TemporaryDirectory(prefix="aima-analysis-throughput-") as temp_dir:
        root = Path(temp_dir)
        offline_elapsed, offline_count = measure_offline(root, raw_response)
        formal_elapsed, formal_count = measure_formal(root, raw_response)

    offline_throughput = offline_count / offline_elapsed
    formal_throughput = formal_count / formal_elapsed
    ratio = formal_throughput / offline_throughput
    evidence = {
        "concurrency": CONCURRENCY,
        "row_count": ROW_COUNT,
        "request_latency_seconds": REQUEST_LATENCY_SECONDS,
        "offline_elapsed_seconds": round(offline_elapsed, 3),
        "formal_elapsed_seconds": round(formal_elapsed, 3),
        "offline_items_per_second": round(offline_throughput, 3),
        "formal_items_per_second": round(formal_throughput, 3),
        "formal_to_offline_throughput_ratio": round(ratio, 4),
        "required_ratio": MIN_FORMAL_TO_OFFLINE_THROUGHPUT_RATIO,
    }
    print("ANALYSIS_THROUGHPUT_EVIDENCE=" + json.dumps(evidence, sort_keys=True))
    if ratio < MIN_FORMAL_TO_OFFLINE_THROUGHPUT_RATIO:
        raise SystemExit(
            f"Formal throughput ratio {ratio:.4f} is below required "
            f"{MIN_FORMAL_TO_OFFLINE_THROUGHPUT_RATIO:.2f}"
        )


if __name__ == "__main__":
    main()
