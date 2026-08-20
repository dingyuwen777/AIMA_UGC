from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from aima_ugc.adapters.providers.imports import (
    ExcelBatchConversionSummary,
    ExcelConversionSummary,
    ExcelSourceConversionSummary,
)
from aima_ugc.adapters.providers.imports_test import test as imports_test_entry
from aima_ugc.bootstrap import manual_ingestion
from aima_ugc.modules.analysis import OfflineContentLabelingSummary


@dataclass(frozen=True, slots=True)
class _DummySummary:
    stage: str


def test_p1g_run_all_preserves_current_manual_chain_and_records_report_skip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []
    output_root = tmp_path / "output"
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX_FILES", tmp_path / "source.xlsx")

    def stage(name: str):
        def run(*args, **kwargs):
            calls.append(name)
            return _DummySummary(stage=name)

        return run

    monkeypatch.setattr(imports_test_entry, "convert", stage("convert"))
    monkeypatch.setattr(imports_test_entry, "filter_keywords", stage("filter_keywords"))
    monkeypatch.setattr(imports_test_entry, "deduplicate", stage("deduplicate"))

    def disabled_stage_must_not_run(*args, **kwargs):
        raise AssertionError("当前人工 run_all 不得调用已禁用阶段")

    monkeypatch.setattr(imports_test_entry, "label_sentiment", disabled_stage_must_not_run)
    monkeypatch.setattr(imports_test_entry, "export_labeled_excel", disabled_stage_must_not_run)
    monkeypatch.setattr(imports_test_entry, "export_raw_excel", disabled_stage_must_not_run)
    monkeypatch.setattr(imports_test_entry, "generate_report", disabled_stage_must_not_run)

    summary = imports_test_entry.run_all(run_id="20260818T160000Z")

    assert calls == ["convert", "filter_keywords", "deduplicate"]
    assert summary.run_id == "20260818T160000Z"
    run_dir = output_root / "runs" / "20260818T160000Z"
    assert summary.run_dir == run_dir
    assert summary.run_summary_path == run_dir / "run_summary.json"
    assert summary.report_markdown_path is None
    assert summary.report_word_path is None
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "20260818T160000Z"
    assert [item["stage"] for item in payload["stages"]] == [
        "convert",
        "filter_keywords",
        "deduplicate",
        "generate_report",
    ]
    assert payload["stages"][-1]["summary"]["status"] == "skipped"
    assert payload["stages"][-1]["summary"]["reason"] == "report_input_excel_not_found"


def test_p1g_export_labeled_excel_uses_source_run_id_and_column_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "爱玛监测.xlsx"
    captured: dict[str, object] = {}
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX_FILES", source)

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

    class FakeAuditWriter:
        def __init__(self, path: Path) -> None:
            captured["audit_path"] = path
            self.session_request_count = 17
            self.summary = SimpleNamespace(
                request_count=17,
                calculated_request_count=17,
                uncalculated_request_count=0,
                input_tokens=310,
                input_cache_hit_tokens=200,
                input_cache_miss_tokens=110,
                output_tokens=170,
                total_cost_amount=Decimal("0.001355"),
                cost_currency="CNY",
            )

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def record(self, _audit: object) -> None:
            return None

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
    monkeypatch.setattr(imports_test_entry, "LLMRequestAuditWriter", FakeAuditWriter)
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
    assert "pricing_catalog" in captured
    assert callable(captured["request_audit"])
    assert "provider_name" not in captured
    assert "use_json_mode" not in captured
    assert captured["retry_kwargs"]["max_retries"] == 4
    assert captured["label_kwargs"]["max_concurrency"] == 250
    assert result.llm_total_cost_amount == Decimal("0.001355")
    assert result.llm_cost_currency == "CNY"


def test_imports_test_convert_uses_multiple_excel_files_in_one_configured_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    output_root = tmp_path / "output"
    run_dir = output_root / "runs" / "multi"
    run_dir.mkdir(parents=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX_FILES", (first, second))

    def fake_convert(**kwargs):
        captured.update(kwargs)
        output_path = kwargs["output_path"]
        return ExcelBatchConversionSummary(
            input_paths=(first, second),
            output_path=output_path,
            error_path=output_path.with_name("conversion_errors.jsonl"),
            files=(
                ExcelSourceConversionSummary(first, 2, 2, 0),
                ExcelSourceConversionSummary(second, 3, 3, 0),
            ),
            rows_seen=5,
            rows_written=5,
            rows_rejected=0,
        )

    monkeypatch.setattr(imports_test_entry, "convert_excel_files_to_canonical_jsonl", fake_convert)

    imports_test_entry.convert(run_dir=run_dir)

    assert captured == {
        "input_paths": (first, second),
        "output_path": run_dir / "canonical" / "contents.jsonl",
        "profile_name": imports_test_entry.PROFILE,
        "sheet_name": imports_test_entry.SHEET_NAME,
    }
    manifest = json.loads(
        (run_dir / "canonical" / "conversion_summary.json").read_text(encoding="utf-8")
    )
    assert manifest["sources"] == [
        {"input_path": str(first), "rows_seen": 2},
        {"input_path": str(second), "rows_seen": 3},
    ]


def test_imports_test_convert_uses_single_path_from_the_only_input_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "single.xlsx"
    output_root = tmp_path / "output"
    run_dir = output_root / "runs" / "single"
    run_dir.mkdir(parents=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX_FILES", source)

    def fake_convert(**kwargs):
        captured.update(kwargs)
        output_path = kwargs["output_path"]
        return ExcelConversionSummary(
            input_path=source,
            output_path=output_path,
            error_path=output_path.with_name("conversion_errors.jsonl"),
            rows_seen=2,
            rows_written=2,
            rows_rejected=0,
        )

    def multi_must_not_run(**kwargs):
        raise AssertionError("单个 Path 不得调用多文件 Converter")

    monkeypatch.setattr(imports_test_entry, "convert_excel_to_canonical_jsonl", fake_convert)
    monkeypatch.setattr(
        imports_test_entry,
        "convert_excel_files_to_canonical_jsonl",
        multi_must_not_run,
    )

    imports_test_entry.convert(run_dir=run_dir)

    assert not hasattr(imports_test_entry, "INPUT_XLSX")
    assert captured == {
        "input_path": source,
        "output_path": run_dir / "canonical" / "contents.jsonl",
        "profile_name": imports_test_entry.PROFILE,
        "sheet_name": imports_test_entry.SHEET_NAME,
    }
    manifest = json.loads(
        (run_dir / "canonical" / "conversion_summary.json").read_text(encoding="utf-8")
    )
    assert manifest["sources"] == [{"input_path": str(source), "rows_seen": 2}]


def test_imports_test_convert_rejects_empty_input_config_before_conversion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "output" / "runs" / "empty"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX_FILES", ())

    with pytest.raises(ValueError, match="至少需要配置一个 Excel"):
        imports_test_entry.convert(run_dir=run_dir)


def test_run_summary_lists_all_source_excel_files_and_report_skip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    output_root = tmp_path / "output"
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX_FILES", (first, second))

    def stage(name: str):
        def run(*args, **kwargs):
            return _DummySummary(stage=name)

        return run

    monkeypatch.setattr(imports_test_entry, "convert", stage("convert"))
    monkeypatch.setattr(imports_test_entry, "filter_keywords", stage("filter_keywords"))
    monkeypatch.setattr(imports_test_entry, "deduplicate", stage("deduplicate"))

    summary = imports_test_entry.run_all(run_id="multi")
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "p1-run-summary.v2"
    assert payload["source_xlsx_files"] == [str(first), str(second)]
    assert "source_xlsx" not in payload
    assert payload["stages"][-1]["stage"] == "generate_report"
    assert payload["stages"][-1]["summary"]["status"] == "skipped"
    assert "report_markdown" not in payload
    assert "report_word" not in payload


def test_multi_file_database_stage_recovers_source_rows_from_conversion_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    run_dir = tmp_path / "output" / "runs" / "multi"
    (run_dir / "canonical").mkdir(parents=True)
    (run_dir / "deduplicated").mkdir()
    (run_dir / "canonical" / "contents.jsonl").write_text("", encoding="utf-8")
    (run_dir / "deduplicated" / "contents.jsonl").write_text("", encoding="utf-8")
    imports_test_entry._write_conversion_manifest(
        run_dir,
        ((first, 2), (second, 3)),
    )
    captured: dict[str, object] = {}

    def fake_multi(**kwargs):
        captured.update(kwargs)
        return _DummySummary(stage="database_ingestion")

    monkeypatch.setattr(manual_ingestion, "ingest_excel_files_run_to_postgres", fake_multi)

    imports_test_entry.ingest_database(run_dir=run_dir, rows_seen=5)

    assert captured == {
        "source_rows": ((first, 2), (second, 3)),
        "unified_content_path": run_dir / "deduplicated" / "contents.jsonl",
        "rows_rejected": 0,
    }
