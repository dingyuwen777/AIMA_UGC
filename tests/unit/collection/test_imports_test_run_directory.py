from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from aima_ugc.adapters.providers.imports_test import test as imports_test
from aima_ugc.platform.reporting import DEFAULT_REPORT_TEMPLATE_PATH


def test_default_run_id_uses_beijing_offset_format() -> None:
    run_id = imports_test._resolve_run_id(None)

    assert re.fullmatch(r"\d{8}T\d{6}\.\d{6}\+0800", run_id)


def test_run_all_uses_one_isolated_run_directory_for_every_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "20260819T142000.000001+0800"
    monkeypatch.setattr(imports_test, "OUTPUT_ROOT", tmp_path)
    calls: list[tuple[str, Path]] = []

    def stage(name: str):
        def run(*, run_dir: Path):
            calls.append((name, run_dir))
            return {"stage": name, "path": str(run_dir / name)}

        return run

    def export_labeled_excel(*, run_dir: Path):
        calls.append(("export_labeled_excel", run_dir))
        output_path = run_dir / "labeled_data.xlsx"
        output_path.touch()
        return {"stage": "export_labeled_excel", "path": str(output_path)}

    def generate_report(
        *,
        excel_path: Path | None = None,
        run_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> imports_test.ReportGenerationSummary:
        assert excel_path is not None
        assert run_dir is None
        assert output_dir is not None
        report_dir = Path(output_dir)
        calls.append(("generate_report", report_dir.parent))
        return imports_test.ReportGenerationSummary(
            source_excel_path=Path(excel_path),
            template_path=DEFAULT_REPORT_TEMPLATE_PATH,
            markdown_path=report_dir / "report.md",
            word_path=report_dir / "report.docx",
            content_rows=0,
            label_rows=0,
            comment_rows=0,
            start_date=None,
            end_date=None,
            word_chart_count=0,
        )

    monkeypatch.setattr(imports_test, "convert", stage("convert"))
    monkeypatch.setattr(imports_test, "filter_keywords", stage("filter_keywords"))
    monkeypatch.setattr(imports_test, "deduplicate", stage("deduplicate"))
    monkeypatch.setattr(imports_test, "label_sentiment", stage("label_sentiment"))
    monkeypatch.setattr(imports_test, "export_labeled_excel", export_labeled_excel)
    monkeypatch.setattr(imports_test, "generate_report", generate_report)

    result = imports_test.run_all(run_id=run_id)

    run_dir = tmp_path / "runs" / run_id
    assert result.run_dir == run_dir
    assert result.run_summary_path == run_dir / "run_summary.json"
    assert result.labeled_excel_path == run_dir / "labeled_data.xlsx"
    assert result.report_markdown_path == run_dir / "reports" / "report.md"
    assert result.report_word_path == run_dir / "reports" / "report.docx"
    assert calls == [
        ("convert", run_dir),
        ("filter_keywords", run_dir),
        ("deduplicate", run_dir),
        ("label_sentiment", run_dir),
        ("export_labeled_excel", run_dir),
        ("generate_report", run_dir),
    ]
    payload = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["run_dir"] == str(run_dir)
    assert payload["labeled_excel"] == str(run_dir / "labeled_data.xlsx")
    assert payload["report_input_excel"] == str(run_dir / "labeled_data.xlsx")
    assert payload["report_markdown"] == str(run_dir / "reports" / "report.md")
    assert payload["report_word"] == str(run_dir / "reports" / "report.docx")
    assert not (tmp_path / "run_summary.json").exists()


def test_prepare_run_dir_refuses_to_reuse_existing_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(imports_test, "OUTPUT_ROOT", tmp_path)
    run_id = "20260819T142000.000001+0800"

    first = imports_test.prepare_run_dir(run_id=run_id)
    assert first == tmp_path / "runs" / run_id

    with pytest.raises(FileExistsError):
        imports_test.prepare_run_dir(run_id=run_id)
