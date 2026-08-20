from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from aima_ugc.adapters.providers.imports_test import test as imports_entry
from aima_ugc.platform.reporting import (
    DEFAULT_REPORT_TEMPLATE_PATH,
    ReportGenerationSummary,
)
from pytest import MonkeyPatch


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
        template_path=DEFAULT_REPORT_TEMPLATE_PATH,
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
    report_date_range = (date(2026, 8, 13), date(2026, 8, 19))
    captured: dict[str, object] = {}

    def fake_generate_excel_report(
        *,
        input_path: Path,
        output_dir: Path,
        template_path: Path | None = None,
        report_date_range: tuple[date, date] | None = None,
    ) -> ReportGenerationSummary:
        captured["input_path"] = input_path
        captured["output_dir"] = output_dir
        captured["report_date_range"] = report_date_range
        assert template_path is None
        return _report_summary(excel_path=input_path, output_dir=output_dir)

    monkeypatch.setattr(imports_entry, "generate_excel_report", fake_generate_excel_report)

    result = imports_entry.generate_report(
        excel_path=excel_path,
        output_dir=output_dir,
        report_date_range=report_date_range,
    )

    assert result.source_excel_path == excel_path
    assert result.markdown_path == output_dir / "report.md"
    assert result.word_path == output_dir / "report.docx"
    assert captured == {
        "input_path": excel_path,
        "output_dir": output_dir,
        "report_date_range": report_date_range,
    }


def test_run_all_appends_report_after_labeled_excel(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "source.xlsx"
    monkeypatch.setattr(imports_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_entry, "INPUT_XLSX_FILES", source)
    report_date_range = (date(2026, 8, 13), date(2026, 8, 19))
    monkeypatch.setattr(imports_entry, "REPORT_DATE_RANGE", report_date_range)
    calls: list[str] = []

    def fake_stage(name: str) -> _StageSummary:
        calls.append(name)
        return _StageSummary()

    monkeypatch.setattr(imports_entry, "convert", lambda *, run_dir: fake_stage("convert"))
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
    monkeypatch.setattr(
        imports_entry,
        "label_sentiment",
        lambda *, run_dir: fake_stage("label_sentiment"),
    )

    def fake_export(*, run_dir: Path) -> _StageSummary:
        calls.append("export_labeled_excel")
        (run_dir / "labeled_data.xlsx").write_bytes(b"xlsx")
        return _StageSummary()

    monkeypatch.setattr(imports_entry, "export_labeled_excel", fake_export)

    def fake_generate_report(
        *,
        excel_path: Path | None = None,
        run_dir: Path | None = None,
        output_dir: Path | None = None,
        report_date_range: tuple[date, date] | None = None,
    ) -> ReportGenerationSummary:
        assert run_dir is None
        assert excel_path is not None
        assert output_dir is not None
        assert report_date_range == (date(2026, 8, 13), date(2026, 8, 19))
        calls.append("generate_report")
        return _report_summary(excel_path=excel_path, output_dir=output_dir)

    monkeypatch.setattr(imports_entry, "generate_report", fake_generate_report)

    result = imports_entry.run_all(run_id="report-hook", write_to_database=False)

    payload = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    expected_report_dir = result.run_dir / "reports"
    assert calls == [
        "convert",
        "filter_keywords",
        "deduplicate",
        "label_sentiment",
        "export_labeled_excel",
        "generate_report",
    ]
    assert [item["stage"] for item in payload["stages"]] == calls
    assert payload["report_input_excel"] == str(result.labeled_excel_path)
    assert payload["report_markdown"] == str(expected_report_dir / "report.md")
    assert payload["report_word"] == str(expected_report_dir / "report.docx")
    assert result.report_markdown_path == expected_report_dir / "report.md"
    assert result.report_word_path == expected_report_dir / "report.docx"


def test_run_all_can_override_report_input_excel(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    source = tmp_path / "source.xlsx"
    processed_excel = tmp_path / "processed.xlsx"
    processed_excel.write_bytes(b"xlsx")
    monkeypatch.setattr(imports_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_entry, "INPUT_XLSX_FILES", source)
    report_date_range = (date(2026, 8, 13), date(2026, 8, 19))
    monkeypatch.setattr(imports_entry, "REPORT_DATE_RANGE", report_date_range)

    monkeypatch.setattr(imports_entry, "convert", lambda *, run_dir: _StageSummary())
    monkeypatch.setattr(imports_entry, "filter_keywords", lambda *, run_dir: _StageSummary())
    monkeypatch.setattr(imports_entry, "deduplicate", lambda *, run_dir: _StageSummary())
    monkeypatch.setattr(imports_entry, "label_sentiment", lambda *, run_dir: _StageSummary())

    def fake_export(*, run_dir: Path) -> _StageSummary:
        (run_dir / "labeled_data.xlsx").write_bytes(b"xlsx")
        return _StageSummary()

    monkeypatch.setattr(imports_entry, "export_labeled_excel", fake_export)

    captured: dict[str, Path] = {}

    def fake_generate_report(
        *,
        excel_path: Path | None = None,
        run_dir: Path | None = None,
        output_dir: Path | None = None,
        report_date_range: tuple[date, date] | None = None,
    ) -> ReportGenerationSummary:
        assert excel_path is not None
        assert output_dir is not None
        assert run_dir is None
        assert report_date_range == (date(2026, 8, 13), date(2026, 8, 19))
        captured["excel_path"] = excel_path
        return _report_summary(excel_path=excel_path, output_dir=output_dir)

    monkeypatch.setattr(imports_entry, "generate_report", fake_generate_report)

    result = imports_entry.run_all(
        run_id="report-override",
        write_to_database=False,
        report_excel_path=processed_excel,
    )

    payload = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert captured["excel_path"] == processed_excel
    assert payload["report_input_excel"] == str(processed_excel)
