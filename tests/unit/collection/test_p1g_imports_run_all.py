from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aima_ugc.adapters.providers.imports_test import test as imports_test_entry
from aima_ugc.modules.analysis import OfflineContentLabelingSummary


@dataclass(frozen=True, slots=True)
class _DummySummary:
    stage: str


def test_p1g_run_all_uses_default_chain_without_raw_excel(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []
    output_root = tmp_path / "output"
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX", tmp_path / "source.xlsx")

    def stage(name: str):
        def run(*args, **kwargs):
            calls.append(name)
            return _DummySummary(stage=name)

        return run

    monkeypatch.setattr(imports_test_entry, "convert", stage("convert"))
    monkeypatch.setattr(imports_test_entry, "filter_keywords", stage("filter_keywords"))
    monkeypatch.setattr(imports_test_entry, "deduplicate", stage("deduplicate"))
    monkeypatch.setattr(imports_test_entry, "label_sentiment", stage("label_sentiment"))
    monkeypatch.setattr(
        imports_test_entry, "export_labeled_excel", stage("export_labeled_excel"), raising=False
    )

    def raw_must_not_run(*args, **kwargs):
        raise AssertionError("run_all 不得调用 export_raw_excel")

    monkeypatch.setattr(imports_test_entry, "export_raw_excel", raw_must_not_run)

    summary = imports_test_entry.run_all(run_id="20260818T160000Z")

    assert calls == [
        "convert",
        "filter_keywords",
        "deduplicate",
        "label_sentiment",
        "export_labeled_excel",
    ]
    assert summary.run_id == "20260818T160000Z"
    run_dir = output_root / "runs" / "20260818T160000Z"
    assert summary.run_dir == run_dir
    assert summary.run_summary_path == run_dir / "run_summary.json"
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "20260818T160000Z"
    assert [item["stage"] for item in payload["stages"]] == calls


def test_p1g_export_labeled_excel_uses_source_run_id_and_column_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "爱玛监测.xlsx"
    captured: dict[str, object] = {}
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX", source)

    def fake_export(
        *,
        input_path: Path,
        output_path: Path,
        include_analysis: bool,
        content_columns: tuple[str, ...],
    ):
        captured.update(
            input_path=input_path,
            output_path=output_path,
            include_analysis=include_analysis,
            content_columns=content_columns,
        )
        return _DummySummary(stage="export_labeled_excel")

    monkeypatch.setattr(imports_test_entry, "export_unified_content_jsonl_to_excel", fake_export)

    imports_test_entry.export_labeled_excel(run_id="20260818T160000Z")

    run_dir = output_root / "runs" / "20260818T160000Z"
    assert captured == {
        "input_path": run_dir / "deduplicated" / "contents.jsonl",
        "output_path": run_dir / "labeled_data.xlsx",
        "include_analysis": True,
        "content_columns": imports_test_entry.EXCEL_CONTENT_COLUMNS,
    }


def test_label_sentiment_only_requires_three_llm_env_values_and_wires_concurrency(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIMA_LLM_BASE_URL=https://llm.example/v1\n"
        "AIMA_LLM_API_KEY=dummy-key\n"
        "AIMA_LLM_MODEL=model-a\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAdapter:
        provider_name = "llm.example"
        model_name = "model-a"

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class FakeRetrying:
        provider_name = "llm.example"
        model_name = "model-a"
        total_requests = 17
        total_retries = 2

        def __init__(self, **kwargs):
            captured["retry_kwargs"] = kwargs

    def fake_adapter(**kwargs):
        captured.update(kwargs)
        return FakeAdapter()

    def fake_label(**kwargs):
        captured["label_kwargs"] = kwargs
        return OfflineContentLabelingSummary(
            input_path=kwargs["input_path"],
            analysis_dir=kwargs["analysis_dir"],
            rows_seen=1,
            rows_already_labeled=0,
            rows_recovered=0,
            rows_succeeded=1,
            rows_failed=0,
            llm_attempts=1,
            peak_in_flight=1,
        )

    monkeypatch.setattr(imports_test_entry, "ENABLE_REAL_LLM", True)
    monkeypatch.setattr(imports_test_entry, "ENV_FILE", env_file)
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setattr(imports_test_entry, "OpenAICompatibleContentLabelingLLM", fake_adapter)
    monkeypatch.setattr(imports_test_entry, "RetryingContentLabelingLLM", FakeRetrying)
    monkeypatch.setattr(imports_test_entry, "label_unified_content_jsonl", fake_label)

    result = imports_test_entry.label_sentiment()

    assert result.rows_succeeded == 1
    assert result.llm_http_requests == 17
    assert result.transport_retries == 2
    assert captured["base_url"] == "https://llm.example/v1"
    assert captured["model"] == "model-a"
    assert captured["timeout_seconds"] == 60.0
    assert captured["max_connections"] == 250
    assert "api_key" in captured
    assert "provider_name" not in captured
    assert "use_json_mode" not in captured
    assert captured["retry_kwargs"]["max_retries"] == 4
    assert captured["label_kwargs"]["max_concurrency"] == 250
