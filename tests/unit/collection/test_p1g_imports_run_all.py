from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aima_ugc.adapters.providers.imports_test import test as imports_test_entry


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
    assert summary.run_summary_path == output_root / "run_summary.json"
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "20260818T160000Z"
    assert [item["stage"] for item in payload["stages"]] == calls


def test_p1g_export_labeled_excel_uses_source_and_run_id_filename(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "爱玛监测.xlsx"
    captured: dict[str, object] = {}
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX", source)

    def fake_export(*, input_path: Path, output_path: Path, include_analysis: bool):
        captured.update(
            input_path=input_path,
            output_path=output_path,
            include_analysis=include_analysis,
        )
        return _DummySummary(stage="export_labeled_excel")

    monkeypatch.setattr(imports_test_entry, "export_unified_content_jsonl_to_excel", fake_export)

    imports_test_entry.export_labeled_excel(run_id="20260818T160000Z")

    assert captured == {
        "input_path": output_root / "deduplicated" / "contents.jsonl",
        "output_path": output_root / "爱玛监测_20260818T160000Z_labeled_data.xlsx",
        "include_analysis": True,
    }
