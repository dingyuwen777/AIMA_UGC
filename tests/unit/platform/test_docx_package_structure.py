from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from aima_ugc.platform.reporting import convert_markdown_to_docx
from aima_ugc.platform.reporting.docx_package import DocxBuilder, verify_docx
from openpyxl import load_workbook

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
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
        "xychart-beta\n"
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

        chart_xml_bytes = archive.read("word/charts/chart1.xml")
        chart_xml = chart_xml_bytes.decode("utf-8")
        assert "抖音" in chart_xml
        assert "小红书" in chart_xml
        chart = ET.fromstring(chart_xml_bytes)
        assert chart.find(f"./{{{_C}}}spPr/{{{_A}}}ln/{{{_A}}}noFill") is not None
        line_outlines = chart.findall(f".//{{{_C}}}lineChart/{{{_C}}}ser/{{{_C}}}spPr/{{{_A}}}ln")
        assert len(line_outlines) == 2
        assert all(outline.get("w") == "28575" for outline in line_outlines)

        workbook = load_workbook(
            BytesIO(archive.read("word/embeddings/chart1.xlsx")), data_only=False
        )
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


def test_word_pie_charts_have_no_outer_border_and_show_two_decimal_percentages(
    tmp_path: Path,
) -> None:
    markdown_path = tmp_path / "report.md"
    output_path = tmp_path / "report.docx"
    markdown_path.write_text(
        "# 情感结构\n\n"
        "```mermaid\n"
        "pie showData\n"
        '    title "情感结构"\n'
        '    "正面" : 10\n'
        '    "负面" : 2\n'
        "```\n\n"
        "```mermaid\n"
        "pie showData\n"
        '    title "平台分布"\n'
        '    "抖音" : 7\n'
        '    "小红书" : 3\n'
        "```\n",
        encoding="utf-8",
    )

    convert_markdown_to_docx(markdown_path, output_path)

    with zipfile.ZipFile(output_path) as archive:
        charts = [ET.fromstring(archive.read(f"word/charts/chart{index}.xml")) for index in (1, 2)]
    for chart in charts:
        assert chart.find(f"./{{{_C}}}spPr/{{{_A}}}ln/{{{_A}}}noFill") is not None
        number_format = chart.find(f".//{{{_C}}}pieChart/{{{_C}}}dLbls/{{{_C}}}numFmt")
        assert number_format is not None
        assert number_format.get("formatCode") == "0.00%"
        assert number_format.get("sourceLinked") == "0"


def test_word_table_uses_readable_full_width_report_style(tmp_path: Path) -> None:
    output_path = tmp_path / "report.docx"
    builder = DocxBuilder()
    builder.add_table(
        ("情感标签", "内容量", "内容占比"),
        (("中性", "28886", "65.31%"), ("正面", "14710", "33.26%")),
    )
    builder.save(output_path)

    with zipfile.ZipFile(output_path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))

    table = document.find(f".//{{{_W}}}tbl")
    assert table is not None
    tbl_width = table.find(f"./{{{_W}}}tblPr/{{{_W}}}tblW")
    assert tbl_width is not None
    assert tbl_width.get(f"{{{_W}}}type") == "pct"
    assert tbl_width.get(f"{{{_W}}}w") == "5000"
    assert table.find(f"./{{{_W}}}tblPr/{{{_W}}}tblLayout").get(f"{{{_W}}}type") == "fixed"
    assert table.find(f"./{{{_W}}}tblPr/{{{_W}}}tblCellMar") is not None

    grid_columns = table.findall(f"./{{{_W}}}tblGrid/{{{_W}}}gridCol")
    assert len(grid_columns) == 3
    assert sum(int(column.get(f"{{{_W}}}w", "0")) for column in grid_columns) == 9300

    rows = table.findall(f"./{{{_W}}}tr")
    header_fill = rows[0].find(f".//{{{_W}}}shd").get(f"{{{_W}}}fill")
    assert header_fill == "1F4E78"
    assert rows[0].find(f".//{{{_W}}}color").get(f"{{{_W}}}val") == "FFFFFF"
    alternate_fill = rows[2].find(f".//{{{_W}}}shd").get(f"{{{_W}}}fill")
    assert alternate_fill == "F4F7FA"
    assert all(row.find(f"./{{{_W}}}trPr/{{{_W}}}cantSplit") is not None for row in rows)

    numeric_cell_alignment = (
        rows[1].findall(f"./{{{_W}}}tc")[1].find(f"./{{{_W}}}p/{{{_W}}}pPr/{{{_W}}}jc")
    )
    assert numeric_cell_alignment is not None
    assert numeric_cell_alignment.get(f"{{{_W}}}val") == "right"
