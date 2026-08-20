from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from aima_ugc.platform.reporting.docx_package import DocxBuilder, verify_docx

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


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
