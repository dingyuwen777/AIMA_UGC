from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aima_ugc.adapters.providers.imports_test import test as imports_test_entry
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from openpyxl import load_workbook


def test_imports_test_export_raw_excel_reads_only_deduplicated_jsonl(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    deduplicated = output_root / "deduplicated" / "contents.jsonl"
    deduplicated.parent.mkdir(parents=True)
    observed_at = datetime(2026, 8, 18, 6, 0, tzinfo=UTC)
    record = UnifiedContentRecordV1(
        content=CanonicalContentV1(
            platform="imports",
            external_content_id="source-001",
            alternate_ids={"source_article_id": "article-001"},
            content_type="unknown",
            title="离线内容",
            text="正文",
            observed_at=observed_at,
            source=CanonicalSourceV1(
                provider_name="imports",
                operation="excel_import",
                source_type="aima-monitoring-excel.v1",
                source_value="source.xlsx",
                item_locator="sheet=文章;row=2",
                observed_at=observed_at,
            ),
            observed_fields=[],
        ),
        matched_keywords=["keyword-a"],
    )
    deduplicated.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    monkeypatch.setattr(imports_test_entry, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(imports_test_entry, "INPUT_XLSX", tmp_path / "must-not-be-read.xlsx")

    summary = imports_test_entry.export_raw_excel()

    assert summary.output_path == output_root / "raw_data.xlsx"
    assert summary.content_rows == 1
    assert summary.comment_rows == 0
    workbook = load_workbook(summary.output_path, data_only=False, read_only=True)
    try:
        assert workbook.sheetnames == ["内容", "评论"]
        content_row = next(workbook["内容"].iter_rows(min_row=2, max_row=2, values_only=True))
        assert content_row[0] == "imports"
        assert content_row[1] == "source-001"
        assert content_row[2] == "article-001"
        assert content_row[23] == "keyword-a"
        assert content_row[24:30] == (None, None, None, None, None, None)
    finally:
        workbook.close()
