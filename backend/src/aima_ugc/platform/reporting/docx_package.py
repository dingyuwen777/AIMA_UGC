"""以最小 OOXML 子集生成并校验报告 DOCX。"""

from __future__ import annotations

import os
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from .chart_png import ChartSpec, render_chart_png

_W: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WP: Final = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A: Final = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PIC: Final = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_XML: Final = "http://www.w3.org/XML/1998/namespace"
_CP: Final = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC: Final = "http://purl.org/dc/elements/1.1/"
_DCTERMS: Final = "http://purl.org/dc/terms/"
_XSI: Final = "http://www.w3.org/2001/XMLSchema-instance"

for prefix, uri in (("w", _W), ("r", _R), ("wp", _WP), ("a", _A), ("pic", _PIC)):
    ET.register_namespace(prefix, uri)


class DocxBuilder:
    """把已解析的报告块写成一个最小但完整的 DOCX 包。"""

    def __init__(self) -> None:
        self.document = ET.Element(f"{{{_W}}}document")
        self.body = ET.SubElement(self.document, f"{{{_W}}}body")
        self.images: list[tuple[str, bytes, int, int]] = []
        self.paragraph_count = 0
        self.table_count = 0
        self.chart_count = 0

    def add_paragraph(
        self,
        text: str = "",
        *,
        style: str | None = None,
        bold: bool = False,
        italic: bool = False,
        code: bool = False,
        align: str | None = None,
    ) -> None:
        paragraph = ET.SubElement(self.body, f"{{{_W}}}p")
        self.paragraph_count += 1
        if style is not None or align is not None:
            p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
            if style is not None:
                ET.SubElement(p_pr, f"{{{_W}}}pStyle", {f"{{{_W}}}val": style})
            if align is not None:
                ET.SubElement(p_pr, f"{{{_W}}}jc", {f"{{{_W}}}val": align})
        self._add_inline_runs(paragraph, text, bold=bold, italic=italic, code=code)

    def add_table(self, headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
        table = ET.SubElement(self.body, f"{{{_W}}}tbl")
        self.table_count += 1
        tbl_pr = ET.SubElement(table, f"{{{_W}}}tblPr")
        ET.SubElement(
            tbl_pr,
            f"{{{_W}}}tblW",
            {f"{{{_W}}}w": "0", f"{{{_W}}}type": "auto"},
        )
        borders = ET.SubElement(tbl_pr, f"{{{_W}}}tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            ET.SubElement(
                borders,
                f"{{{_W}}}{side}",
                {
                    f"{{{_W}}}val": "single",
                    f"{{{_W}}}sz": "4",
                    f"{{{_W}}}color": "D9D9D9",
                },
            )
        self._add_table_row(table, headers, header=True)
        for row in rows:
            self._add_table_row(table, row, header=False)

    def add_code_block(self, code: str) -> None:
        for line in code.splitlines() or ("",):
            self.add_paragraph(line, style="Code", code=True)

    def add_chart(self, spec: ChartSpec) -> None:
        png, width, height = render_chart_png(spec)
        self.chart_count += 1
        name = f"chart-{self.chart_count}.png"
        self.images.append((name, png, width, height))
        if spec.title:
            self.add_paragraph(spec.title, bold=True, align="center")
        self._add_image(name, width, height, image_index=len(self.images))
        if spec.kind == "pie" and spec.pie_labels:
            total = sum(spec.series[0]) if spec.series else 0.0
            rows: list[tuple[str, str, str]] = []
            for label, value in zip(spec.pie_labels, spec.series[0], strict=True):
                share = f"{value / total * 100:.2f}%" if total > 0 else "0.00%"
                rows.append((label, _number_text(value), share))
            self.add_table(("图例", "数量", "占比"), tuple(rows))

    def save(self, path: Path) -> None:
        self._add_section_properties()
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("[Content_Types].xml", _content_types_xml())
                archive.writestr("_rels/.rels", _root_rels_xml())
                archive.writestr("docProps/core.xml", _core_props_xml())
                archive.writestr("docProps/app.xml", _app_props_xml())
                archive.writestr("word/document.xml", _serialize_xml(self.document))
                archive.writestr("word/styles.xml", _styles_xml())
                archive.writestr(
                    "word/_rels/document.xml.rels",
                    _document_rels_xml(self.images),
                )
                for name, data, _, _ in self.images:
                    archive.writestr(f"word/media/{name}", data)
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    def _add_table_row(
        self,
        table: ET.Element,
        values: tuple[str, ...],
        *,
        header: bool,
    ) -> None:
        row = ET.SubElement(table, f"{{{_W}}}tr")
        if header:
            tr_pr = ET.SubElement(row, f"{{{_W}}}trPr")
            ET.SubElement(tr_pr, f"{{{_W}}}tblHeader")
        for value in values:
            cell = ET.SubElement(row, f"{{{_W}}}tc")
            tc_pr = ET.SubElement(cell, f"{{{_W}}}tcPr")
            if header:
                ET.SubElement(tc_pr, f"{{{_W}}}shd", {f"{{{_W}}}fill": "EAF2F8"})
            paragraph = ET.SubElement(cell, f"{{{_W}}}p")
            self._add_inline_runs(paragraph, value.replace("<br>", "\n"), bold=header)

    def _add_inline_runs(
        self,
        paragraph: ET.Element,
        text: str,
        *,
        bold: bool = False,
        italic: bool = False,
        code: bool = False,
    ) -> None:
        token_re = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
        cursor = 0
        for match in token_re.finditer(text):
            if match.start() > cursor:
                self._add_run(
                    paragraph,
                    text[cursor : match.start()],
                    bold=bold,
                    italic=italic,
                    code=code,
                )
            token = match.group(0)
            if token.startswith("**"):
                self._add_run(
                    paragraph,
                    token[2:-2],
                    bold=True,
                    italic=italic,
                    code=code,
                )
            else:
                self._add_run(
                    paragraph,
                    token[1:-1],
                    bold=bold,
                    italic=italic,
                    code=True,
                )
            cursor = match.end()
        if cursor < len(text) or not text:
            self._add_run(
                paragraph,
                text[cursor:],
                bold=bold,
                italic=italic,
                code=code,
            )

    def _add_run(
        self,
        paragraph: ET.Element,
        text: str,
        *,
        bold: bool,
        italic: bool,
        code: bool,
    ) -> None:
        pieces = text.split("\n")
        for index, piece in enumerate(pieces):
            if index > 0:
                break_run = ET.SubElement(paragraph, f"{{{_W}}}r")
                ET.SubElement(break_run, f"{{{_W}}}br")
            if not piece and len(pieces) > 1:
                continue
            run = ET.SubElement(paragraph, f"{{{_W}}}r")
            if bold or italic or code:
                r_pr = ET.SubElement(run, f"{{{_W}}}rPr")
                if bold:
                    ET.SubElement(r_pr, f"{{{_W}}}b")
                if italic:
                    ET.SubElement(r_pr, f"{{{_W}}}i")
                if code:
                    fonts = ET.SubElement(r_pr, f"{{{_W}}}rFonts")
                    fonts.set(f"{{{_W}}}ascii", "Consolas")
                    fonts.set(f"{{{_W}}}hAnsi", "Consolas")
                    fonts.set(f"{{{_W}}}eastAsia", "Microsoft YaHei")
            node = ET.SubElement(run, f"{{{_W}}}t")
            node.set(f"{{{_XML}}}space", "preserve")
            node.text = piece

    def _add_image(
        self,
        name: str,
        width_px: int,
        height_px: int,
        *,
        image_index: int,
    ) -> None:
        paragraph = ET.SubElement(self.body, f"{{{_W}}}p")
        self.paragraph_count += 1
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}jc", {f"{{{_W}}}val": "center"})
        run = ET.SubElement(paragraph, f"{{{_W}}}r")
        drawing = ET.SubElement(run, f"{{{_W}}}drawing")
        aspect = height_px / width_px if width_px else 0.5
        width_emu = 5_850_000
        height_emu = int(width_emu * aspect)
        inline = ET.SubElement(
            drawing,
            f"{{{_WP}}}inline",
            {"distT": "0", "distB": "0", "distL": "0", "distR": "0"},
        )
        ET.SubElement(
            inline,
            f"{{{_WP}}}extent",
            {"cx": str(width_emu), "cy": str(height_emu)},
        )
        ET.SubElement(
            inline,
            f"{{{_WP}}}docPr",
            {"id": str(image_index), "name": name, "descr": "数据图表"},
        )
        graphic = ET.SubElement(inline, f"{{{_A}}}graphic")
        graphic_data = ET.SubElement(
            graphic,
            f"{{{_A}}}graphicData",
            {"uri": "http://schemas.openxmlformats.org/drawingml/2006/picture"},
        )
        pic = ET.SubElement(graphic_data, f"{{{_PIC}}}pic")
        nv = ET.SubElement(pic, f"{{{_PIC}}}nvPicPr")
        ET.SubElement(nv, f"{{{_PIC}}}cNvPr", {"id": "0", "name": name})
        ET.SubElement(nv, f"{{{_PIC}}}cNvPicPr")
        blip_fill = ET.SubElement(pic, f"{{{_PIC}}}blipFill")
        ET.SubElement(
            blip_fill,
            f"{{{_A}}}blip",
            {f"{{{_R}}}embed": f"rId{image_index + 1}"},
        )
        stretch = ET.SubElement(blip_fill, f"{{{_A}}}stretch")
        ET.SubElement(stretch, f"{{{_A}}}fillRect")
        sp_pr = ET.SubElement(pic, f"{{{_PIC}}}spPr")
        xfrm = ET.SubElement(sp_pr, f"{{{_A}}}xfrm")
        ET.SubElement(xfrm, f"{{{_A}}}off", {"x": "0", "y": "0"})
        ET.SubElement(
            xfrm,
            f"{{{_A}}}ext",
            {"cx": str(width_emu), "cy": str(height_emu)},
        )
        prst = ET.SubElement(sp_pr, f"{{{_A}}}prstGeom", {"prst": "rect"})
        ET.SubElement(prst, f"{{{_A}}}avLst")

    def _add_section_properties(self) -> None:
        section = ET.SubElement(self.body, f"{{{_W}}}sectPr")
        ET.SubElement(
            section,
            f"{{{_W}}}pgSz",
            {f"{{{_W}}}w": "11906", f"{{{_W}}}h": "16838"},
        )
        ET.SubElement(
            section,
            f"{{{_W}}}pgMar",
            {
                f"{{{_W}}}top": "1134",
                f"{{{_W}}}right": "1134",
                f"{{{_W}}}bottom": "1134",
                f"{{{_W}}}left": "1134",
                f"{{{_W}}}header": "567",
                f"{{{_W}}}footer": "567",
                f"{{{_W}}}gutter": "0",
            },
        )


def verify_docx(path: Path, *, expected_charts: int) -> None:
    """重新打开 DOCX 包并校验 ZIP、关键 XML 和图表媒体数量。"""

    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
        "word/styles.xml",
        "word/_rels/document.xml.rels",
    }
    with zipfile.ZipFile(path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise OSError(f"DOCX ZIP CRC 校验失败: {corrupt_member}")
        names = set(archive.namelist())
        missing = required.difference(names)
        if missing:
            raise OSError(f"DOCX 包结构缺失: {'、'.join(sorted(missing))}")
        for xml_name in required:
            ET.fromstring(archive.read(xml_name))
        media = [name for name in names if name.startswith("word/media/") and name.endswith(".png")]
        if len(media) != expected_charts:
            raise OSError("DOCX 图表媒体数量校验失败")


def _number_text(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _serialize_xml(element: ET.Element) -> bytes:
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels"
           ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml"
            ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml"
            ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
                Target="word/document.xml"/>
  <Relationship Id="rId2"
                Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
                Target="docProps/core.xml"/>
  <Relationship Id="rId3"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
                Target="docProps/app.xml"/>
</Relationships>"""


def _document_rels_xml(images: list[tuple[str, bytes, int, int]]) -> str:
    relationships = [
        (
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
        )
    ]
    for index, (name, _, _, _) in enumerate(images, start=2):
        relationships.append(
            (
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="media/{escape(name)}"/>'
            )
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  '
        + "\n  ".join(relationships)
        + "\n</Relationships>"
    )


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr><w:spacing w:before="300" w:after="160"/></w:pPr>
    <w:rPr>
      <w:b/><w:sz w:val="36"/><w:szCs w:val="36"/><w:color w:val="1F4E79"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
    <w:rPr>
      <w:b/><w:sz w:val="28"/><w:szCs w:val="28"/><w:color w:val="2F5597"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Code">
    <w:name w:val="Code"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/>
      <w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="404040"/>
    </w:rPr>
  </w:style>
</w:styles>"""


def _core_props_xml() -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="{_CP}"
                   xmlns:dc="{_DC}"
                   xmlns:dcterms="{_DCTERMS}"
                   xmlns:xsi="{_XSI}">
  <dc:title>AIMA_UGC 数据报告</dc:title>
  <dc:creator>AIMA_UGC</dc:creator>
  <cp:lastModifiedBy>AIMA_UGC</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def _app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>AIMA_UGC</Application>
</Properties>"""
