from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pytest import MonkeyPatch

from aima_ugc.adapters.providers.imports_test import test as imports_entry
from aima_ugc.platform.reporting import ReportGenerationSummary


@dataclass(frozen=True, slots=True)
class _StageSummary:
    rows_seen: int = 3


def _report_summary(*, excel_path: Path, output_dir: Path) -> ReportGenerationSummary:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "report.md"
    word_path = output_dir / "report.docx"
    markdown_path.write_text("# report\n", encoding="utf-8")
    word_path.write_bytes(b"docx")
    return ReportGenerationSummary(
        source_excel_path=excel_path,
        template_path=imports_entry.REPORT_TEMPLATE_FILE,
        markdown_path=markdown_path,
        word_path=word_path,
        content_rows=3,
        label_rows=4,
        comment_rows=1,
        start_date="2026-08-18",
        end_date="2026-08-19",
        word_chart_count=9,
    )


def test_generate_report_accepts_explicit_processed_excel(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    excel_path = tmp_path / "finished.xlsx"
    output_dir = tmp_path / "custom-reports"
    excel_path.write_bytes(b"xlsx")
    captured: dict[str, Path] = {}

    def fake_generate_excel_report(
        *,
        input_path: Path,
        output_dir: Path,
        template_path: Path,
    ) -> ReportGenerationSummary:
        captured["input_path"] = input_path
        captured["output_dir"] = output_dir
        captured["template_path"] = template_path
        return _report_summary(excel_path=input_path, output_dir=output_dir)

    monkeypatch.setattr(
        imports_entry,
        "generate_excel_report",
        fake_generate_excel_report,
    )

    result = imports_entry.generate_report(
        excel_path=excel_path,
        output_dir=output_dir,
    )

    assert result.source_excel_path == excel_path
    assert result.markdown_path == output_dir / "report.md"
    assert result.word_path == output_dir / "report.docx"
    assert captured == {
        "input_path": excel_path,
        "output_dir": output_dir,
        "template_path": imports_entry.REPORT_TEMPLATE_FILE,
    }


def test_run_all_uses_explicit_processed_excel_without_reenabling_disabled_stages(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "source.xlsx"
    processed_excel = tmp_path / "processed.xlsx"
    processed_excel.write_bytes(b"xlsx")
    monkeypatch.setattr(imports_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_entry, "INPUT_XLSX_FILES", source)
    calls: list[str] = []

    def fake_stage(name: str) -> _StageSummary:
        calls.append(name)
        return _StageSummary()

    monkeypatch.setattr(
        imports_entry,
        "convert",
        lambda *, run_dir: fake_stage("convert"),
    )
    monkeypatch.setattr(
        imports_entry,
        "filter_keywords",
        lambda *, run_dir: fake_stage("filter_keywords"),
    )
    monkeypatch.setattr(
        imports_entry,
        "deduplicate",
        lambda *, run_dir: fake_stage("deduplicate"),
    )

    def disabled_stage_must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("当前人工 run_all 不得静默恢复 AI/最终 Excel 阶段")

    monkeypatch.setattr(imports_entry, "label_sentiment", disabled_stage_must_not_run)
    monkeypatch.setattr(imports_entry, "export_labeled_excel", disabled_stage_must_not_run)

    def fake_generate_report(
        *,
        excel_path: Path | None = None,
        run_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> ReportGenerationSummary:
        assert excel_path == processed_excel
        assert run_dir is None
        assert output_dir is not None
        calls.append("generate_report")
        return _report_summary(excel_path=processed_excel, output_dir=output_dir)

    monkeypatch.setattr(imports_entry, "generate_report", fake_generate_report)

    result = imports_entry.run_all(
        run_id="report-hook",
        write_to_database=False,
        report_excel_path=processed_excel,
    )

    payload = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    expected_report_dir = result.run_dir / "reports"
    assert calls == ["convert", "filter_keywords", "deduplicate", "generate_report"]
    assert [item["stage"] for item in payload["stages"]] == [
        "convert",
        "filter_keywords",
        "deduplicate",
        "generate_report",
    ]
    assert payload["report_input_excel"] == str(processed_excel)
    assert payload["report_markdown"] == str(expected_report_dir / "report.md")
    assert payload["report_word"] == str(expected_report_dir / "report.docx")
    assert result.report_markdown_path == expected_report_dir / "report.md"
    assert result.report_word_path == expected_report_dir / "report.docx"


def test_run_all_records_report_skip_when_default_labeled_excel_is_absent(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "source.xlsx"
    monkeypatch.setattr(imports_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_entry, "INPUT_XLSX_FILES", source)

    monkeypatch.setattr(imports_entry, "convert", lambda *, run_dir: _StageSummary())
    monkeypatch.setattr(imports_entry, "filter_keywords", lambda *, run_dir: _StageSummary())
    monkeypatch.setattr(imports_entry, "deduplicate", lambda *, run_dir: _StageSummary())

    def report_must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("没有实际报告 Excel 时不得调用 Report Renderer")

    monkeypatch.setattr(imports_entry, "generate_report", report_must_not_run)

    result = imports_entry.run_all(run_id="report-skip", write_to_database=False)

    payload = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    report_stage = payload["stages"][-1]
    assert report_stage["stage"] == "generate_report"
    assert report_stage["summary"]["status"] == "skipped"
    assert report_stage["summary"]["reason"] == "report_input_excel_not_found"
    assert payload["report_input_excel"] == str(result.run_dir / "labeled_data.xlsx")
    assert "report_markdown" not in payload
    assert "report_word" not in payload
    assert result.report_markdown_path is None
    assert result.report_word_path is None
