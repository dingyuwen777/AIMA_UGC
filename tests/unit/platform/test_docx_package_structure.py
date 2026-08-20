from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from aima_ugc.platform.reporting import convert_markdown_to_docx
from aima_ugc.platform.reporting.docx_package import DocxBuilder, verify_docx
from openpyxl import load_workbook

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def test_docx_line_break_is_nested_in_run(tmp_path: Path) -> None:
    output_path = tmp_path / "report.docx"
    builder = DocxBuilder()
    builder.add_paragraph("第一行\n第二行")
    builder.save(output_path)
    verify_docx(output_path, expected_charts=0)

    with zipfile.ZipFile(output_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    assert root.findall(f".//{{{_W}}}p/{{{_W}}}br") == []
    assert len(root.findall(f".//{{{_W}}}r/{{{_W}}}br")) == 1


def test_word_chart_is_editable_office_chart_with_embedded_workbook(tmp_path: Path) -> None:
    markdown_path = tmp_path / "report.md"
    output_path = tmp_path / "report.docx"
    markdown_path.write_text(
        "# 趋势\n\n"
        "```mermaid\n"
        "xychart\n"
        '    title "平台每日声量"\n'
        '    %% series ["抖音", "小红书"]\n'
        '    x-axis ["2026-08-18", "2026-08-19"]\n'
        '    y-axis "数量" 0 --> 10\n'
        "    line [3, 5]\n"
        "    line [2, 4]\n"
        "```\n",
        encoding="utf-8",
    )

    summary = convert_markdown_to_docx(markdown_path, output_path)
    assert summary.chart_count == 1

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        assert "word/charts/chart1.xml" in names
        assert "word/charts/_rels/chart1.xml.rels" in names
        assert "word/embeddings/chart1.xlsx" in names
        assert not any(name.startswith("word/media/chart-") for name in names)

        document = ET.fromstring(archive.read("word/document.xml"))
        assert len(document.findall(f".//{{{_C}}}chart")) == 1

        chart_xml = archive.read("word/charts/chart1.xml").decode("utf-8")
        assert "抖音" in chart_xml
        assert "小红书" in chart_xml

        workbook = load_workbook(BytesIO(archive.read("word/embeddings/chart1.xlsx")), data_only=False)
        try:
            sheet = workbook.active
            assert sheet["A1"].value == "日期/分类"
            assert sheet["B1"].value == "抖音"
            assert sheet["C1"].value == "小红书"
            assert sheet["A2"].value == "2026-08-18"
            assert sheet["B2"].value == 3
            assert sheet["C3"].value == 4
        finally:
            workbook.close()
