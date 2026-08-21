"""横向 A4 报告的高保真 Word 视觉组合组件。"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from .chart_spec import ChartSpec
from .docx_package import DocxBuilder, _A, _C, _PIC, _R, _W, _WP, _ImageAsset
from .visuals import theme

_PRIMARY_LEFT_WIDTH = 8_050
_PRIMARY_RIGHT_WIDTH = theme.CONTENT_WIDTH_TWIPS - _PRIMARY_LEFT_WIDTH
_VISUAL_LEFT_WIDTH = 7_500
_VISUAL_RIGHT_WIDTH = theme.CONTENT_WIDTH_TWIPS - _VISUAL_LEFT_WIDTH
_COMPACT_DAILY_DIMENSIONS_PER_TABLE = 5


class ReportDocxBuilder(DocxBuilder):
    """在基础 OOXML Builder 上增加报告专用的组合式视觉。"""

    def add_primary_overview(
        self,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
        *,
        image_path: Path,
        alt_text: str,
    ) -> None:
        """把一级议题 KPI、精确排名和词云组合在一个横向视觉区域。"""

        if len(headers) < 3 or not rows:
            raise ValueError("一级议题组合视图需要标签、数量、占比数据")
        total = sum(_parse_integer(row[1]) for row in rows)
        outer = self._new_layout_table(
            self.body,
            (_PRIMARY_LEFT_WIDTH, _PRIMARY_RIGHT_WIDTH),
            caption="AIMAPrimaryOverview",
        )
        kpi_row = ET.SubElement(outer, f"{{{_W}}}tr")
        kpi_row_pr = ET.SubElement(kpi_row, f"{{{_W}}}trPr")
        ET.SubElement(kpi_row_pr, f"{{{_W}}}cantSplit")
        kpi_cell = ET.SubElement(kpi_row, f"{{{_W}}}tc")
        kpi_cell_pr = ET.SubElement(kpi_cell, f"{{{_W}}}tcPr")
        ET.SubElement(kpi_cell_pr, f"{{{_W}}}gridSpan", {f"{{{_W}}}val": "2"})
        ET.SubElement(
            kpi_cell_pr,
            f"{{{_W}}}tcW",
            {f"{{{_W}}}w": str(theme.CONTENT_WIDTH_TWIPS), f"{{{_W}}}type": "dxa"},
        )
        self._append_kpi_strip(
            kpi_cell,
            (
                ("标签对总量", f"{total:,}"),
                ("一级议题", str(len(rows))),
                ("TOP1 占比", rows[0][2]),
            ),
        )
        ET.SubElement(kpi_cell, f"{{{_W}}}p")

        visual_row = ET.SubElement(outer, f"{{{_W}}}tr")
        visual_row_pr = ET.SubElement(visual_row, f"{{{_W}}}trPr")
        ET.SubElement(visual_row_pr, f"{{{_W}}}cantSplit")
        left = self._new_cell(visual_row, _PRIMARY_LEFT_WIDTH, pad=105)
        right = self._new_cell(visual_row, _PRIMARY_RIGHT_WIDTH, pad=150)
        self._append_section_label(left, "一级议题 Top 分布")
        self._append_ranking_table(left, rows, start_rank=1, show_progress=True)
        self._append_section_label(right, "一级议题词云")
        self._append_image(
            right,
            image_path,
            alt_text=alt_text,
            max_width_emu=4_400_000,
            max_height_emu=3_150_000,
        )
        ET.SubElement(left, f"{{{_W}}}p")
        ET.SubElement(right, f"{{{_W}}}p")
        self._add_after_layout_spacing()

    def add_ranking_visual(
        self,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
        *,
        top_n: int,
        chart: ChartSpec | None = None,
        image_path: Path | None = None,
        alt_text: str = "",
    ) -> None:
        """左侧展示 Top Ranking，右侧展示 Chart/词云，剩余数据转紧凑明细。"""

        if len(headers) < 3:
            raise ValueError("Ranking 组合视图至少需要标签、数量、占比三列")
        if (chart is None) == (image_path is None):
            raise ValueError("Ranking 组合视图必须且只能提供 Chart 或图片")
        limit = max(1, min(top_n, len(rows)))
        top_rows = rows[:limit]
        remainder = rows[limit:]
        caption = "AIMARankingChart" if chart is not None else "AIMARankingImage"
        outer = self._new_layout_table(
            self.body,
            (_VISUAL_LEFT_WIDTH, _VISUAL_RIGHT_WIDTH),
            caption=caption,
        )
        visual_row = ET.SubElement(outer, f"{{{_W}}}tr")
        visual_row_pr = ET.SubElement(visual_row, f"{{{_W}}}trPr")
        ET.SubElement(visual_row_pr, f"{{{_W}}}cantSplit")
        left = self._new_cell(visual_row, _VISUAL_LEFT_WIDTH, pad=100)
        right = self._new_cell(visual_row, _VISUAL_RIGHT_WIDTH, pad=145)
        self._append_section_label(left, f"Top {limit}")
        self._append_ranking_table(left, top_rows, start_rank=1, show_progress=True)
        if chart is not None:
            self._append_chart(right, chart, width_emu=5_000_000, height_emu=3_250_000)
        else:
            assert image_path is not None
            self._append_image(
                right,
                image_path,
                alt_text=alt_text,
                max_width_emu=5_000_000,
                max_height_emu=3_300_000,
            )
        ET.SubElement(left, f"{{{_W}}}p")
        ET.SubElement(right, f"{{{_W}}}p")
        if remainder:
            self._append_compact_remainder(remainder, start_rank=limit + 1)
        self._add_after_layout_spacing()

    def add_table_visual(
        self,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
        *,
        chart: ChartSpec,
    ) -> None:
        """把短数据表与对应 Office Chart 放在同一横向区域。"""

        outer = self._new_layout_table(
            self.body,
            (_VISUAL_LEFT_WIDTH, _VISUAL_RIGHT_WIDTH),
            caption="AIMATableChart",
        )
        visual_row = ET.SubElement(outer, f"{{{_W}}}tr")
        visual_row_pr = ET.SubElement(visual_row, f"{{{_W}}}trPr")
        ET.SubElement(visual_row_pr, f"{{{_W}}}cantSplit")
        left = self._new_cell(visual_row, _VISUAL_LEFT_WIDTH, pad=80)
        right = self._new_cell(visual_row, _VISUAL_RIGHT_WIDTH, pad=130)
        self._append_editorial_table(left, headers, rows)
        self._append_chart(right, chart, width_emu=5_000_000, height_emu=3_250_000)
        ET.SubElement(left, f"{{{_W}}}p")
        ET.SubElement(right, f"{{{_W}}}p")
        self._add_after_layout_spacing()

    def add_compact_daily(
        self,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
    ) -> None:
        """把日期/维度/数量长表仅在 Word 中透视为横向紧凑矩阵。"""

        if len(headers) != 3:
            self.add_table(headers, rows)
            return
        dates: list[str] = []
        dimensions: list[str] = []
        values: dict[tuple[str, str], str] = {}
        for day, dimension, value in rows:
            if day not in dates:
                dates.append(day)
            if dimension not in dimensions:
                dimensions.append(dimension)
            values[(day, dimension)] = value
        if not dates or not dimensions:
            self.add_table(headers, rows)
            return
        for start in range(0, len(dimensions), _COMPACT_DAILY_DIMENSIONS_PER_TABLE):
            chunk = dimensions[start : start + _COMPACT_DAILY_DIMENSIONS_PER_TABLE]
            matrix_headers = (headers[0], *chunk)
            matrix_rows = tuple(
                (day, *(values.get((day, dimension), "—") for dimension in chunk))
                for day in dates
            )
            self._append_compact_matrix(matrix_headers, matrix_rows)
        self._add_after_layout_spacing()

    def add_compact_chart(self, spec: ChartSpec) -> None:
        """为分层趋势图使用较矮的横向 Office Chart，避免一张图占满整页。"""

        self.charts.append(spec)
        self.chart_count += 1
        paragraph = ET.SubElement(self.body, f"{{{_W}}}p")
        self.paragraph_count += 1
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}jc", {f"{{{_W}}}val": "center"})
        ET.SubElement(p_pr, f"{{{_W}}}keepLines")
        ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "30", f"{{{_W}}}after": "70"})
        self._append_chart_inline(
            paragraph,
            self.chart_count,
            width_emu=8_900_000,
            height_emu=3_000_000,
        )

    def _new_layout_table(
        self,
        parent: ET.Element,
        widths: tuple[int, ...],
        *,
        caption: str,
    ) -> ET.Element:
        table = ET.SubElement(parent, f"{{{_W}}}tbl")
        self.table_count += 1
        tbl_pr = ET.SubElement(table, f"{{{_W}}}tblPr")
        ET.SubElement(tbl_pr, f"{{{_W}}}tblCaption", {f"{{{_W}}}val": caption})
        ET.SubElement(
            tbl_pr,
            f"{{{_W}}}tblW",
            {f"{{{_W}}}w": "5000", f"{{{_W}}}type": "pct"},
        )
        ET.SubElement(tbl_pr, f"{{{_W}}}tblLayout", {f"{{{_W}}}type": "fixed"})
        borders = ET.SubElement(tbl_pr, f"{{{_W}}}tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            ET.SubElement(borders, f"{{{_W}}}{side}", {f"{{{_W}}}val": "nil"})
        grid = ET.SubElement(table, f"{{{_W}}}tblGrid")
        for width in widths:
            ET.SubElement(grid, f"{{{_W}}}gridCol", {f"{{{_W}}}w": str(width)})
        return table

    def _new_cell(self, row: ET.Element, width: int, *, pad: int) -> ET.Element:
        cell = ET.SubElement(row, f"{{{_W}}}tc")
        tc_pr = ET.SubElement(cell, f"{{{_W}}}tcPr")
        ET.SubElement(
            tc_pr,
            f"{{{_W}}}tcW",
            {f"{{{_W}}}w": str(width), f"{{{_W}}}type": "dxa"},
        )
        margins = ET.SubElement(tc_pr, f"{{{_W}}}tcMar")
        for side in ("top", "left", "bottom", "right"):
            ET.SubElement(
                margins,
                f"{{{_W}}}{side}",
                {f"{{{_W}}}w": str(pad), f"{{{_W}}}type": "dxa"},
            )
        ET.SubElement(tc_pr, f"{{{_W}}}vAlign", {f"{{{_W}}}val": "top"})
        return cell

    def _append_kpi_strip(
        self,
        parent: ET.Element,
        items: tuple[tuple[str, str], ...],
    ) -> None:
        width = theme.CONTENT_WIDTH_TWIPS // len(items)
        table = self._new_layout_table(
            parent,
            tuple(width for _ in items),
            caption="AIMAKpiStrip",
        )
        row = ET.SubElement(table, f"{{{_W}}}tr")
        row_pr = ET.SubElement(row, f"{{{_W}}}trPr")
        ET.SubElement(row_pr, f"{{{_W}}}cantSplit")
        for label, value in items:
            cell = self._new_cell(row, width, pad=120)
            cell_pr = cell.find(f"./{{{_W}}}tcPr")
            assert cell_pr is not None
            ET.SubElement(cell_pr, f"{{{_W}}}shd", {f"{{{_W}}}fill": theme.SOFT_BACKGROUND})
            label_p = ET.SubElement(cell, f"{{{_W}}}p")
            label_pr = ET.SubElement(label_p, f"{{{_W}}}pPr")
            ET.SubElement(label_pr, f"{{{_W}}}spacing", {f"{{{_W}}}after": "18"})
            self._add_run(
                label_p,
                label,
                bold=False,
                italic=False,
                code=False,
                color=theme.SECONDARY_TEXT_COLOR,
                font_size="17",
            )
            value_p = ET.SubElement(cell, f"{{{_W}}}p")
            value_pr = ET.SubElement(value_p, f"{{{_W}}}pPr")
            ET.SubElement(value_pr, f"{{{_W}}}spacing", {f"{{{_W}}}after": "35"})
            self._add_run(
                value_p,
                value,
                bold=True,
                italic=False,
                code=False,
                color=theme.TITLE_COLOR,
                font_size="26",
            )

    def _append_section_label(self, parent: ET.Element, text: str) -> None:
        paragraph = ET.SubElement(parent, f"{{{_W}}}p")
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "50", f"{{{_W}}}after": "65"})
        self._add_run(
            paragraph,
            text,
            bold=True,
            italic=False,
            code=False,
            color=theme.TITLE_COLOR,
            font_size="21",
        )

    def _append_ranking_table(
        self,
        parent: ET.Element,
        rows: tuple[tuple[str, ...], ...],
        *,
        start_rank: int,
        show_progress: bool,
    ) -> None:
        table = self._new_layout_table(parent, (760, 3_420, 1_500, 1_450), caption="AIMARankingTop")
        for offset, row_values in enumerate(rows):
            rank = start_rank + offset
            tr = ET.SubElement(table, f"{{{_W}}}tr")
            tr_pr = ET.SubElement(tr, f"{{{_W}}}trPr")
            ET.SubElement(tr_pr, f"{{{_W}}}cantSplit")
            for column, value in enumerate((f"{rank:02d}", row_values[0], row_values[1], row_values[2])):
                width = (760, 3_420, 1_500, 1_450)[column]
                cell = self._new_cell(tr, width, pad=45)
                p = ET.SubElement(cell, f"{{{_W}}}p")
                p_pr = ET.SubElement(p, f"{{{_W}}}pPr")
                ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "16", f"{{{_W}}}after": "12"})
                align = "right" if column >= 2 else "left"
                ET.SubElement(p_pr, f"{{{_W}}}jc", {f"{{{_W}}}val": align})
                self._add_run(
                    p,
                    value,
                    bold=(column == 0 or (column == 1 and rank == 1) or column == 2),
                    italic=False,
                    code=False,
                    color=(
                        theme.ACCENT_BLUE
                        if rank == 1 and column in {0, 1, 3}
                        else theme.SECONDARY_TEXT_COLOR
                        if column in {0, 3}
                        else theme.TEXT_COLOR
                    ),
                    font_size="18",
                )
            if show_progress:
                bar_row = ET.SubElement(table, f"{{{_W}}}tr")
                bar_row_pr = ET.SubElement(bar_row, f"{{{_W}}}trPr")
                ET.SubElement(bar_row_pr, f"{{{_W}}}cantSplit")
                spacer = self._new_cell(bar_row, 760, pad=0)
                ET.SubElement(spacer, f"{{{_W}}}p")
                bar_cell = self._new_cell(bar_row, 4_920, pad=0)
                bar_cell_pr = bar_cell.find(f"./{{{_W}}}tcPr")
                assert bar_cell_pr is not None
                ET.SubElement(bar_cell_pr, f"{{{_W}}}gridSpan", {f"{{{_W}}}val": "3"})
                self._append_progress_bar(bar_cell, _parse_percentage(row_values[2]), top=rank == 1)
                ET.SubElement(bar_cell, f"{{{_W}}}p")

    def _append_progress_bar(self, parent: ET.Element, percentage: float, *, top: bool) -> None:
        total = 10_000
        filled = max(1, round(total * min(100.0, max(0.0, percentage)) / 100))
        empty = max(1, total - filled)
        table = self._new_layout_table(parent, (filled, empty), caption="AIMAProgress")
        tr = ET.SubElement(table, f"{{{_W}}}tr")
        tr_pr = ET.SubElement(tr, f"{{{_W}}}trPr")
        ET.SubElement(tr_pr, f"{{{_W}}}cantSplit")
        ET.SubElement(tr_pr, f"{{{_W}}}trHeight", {f"{{{_W}}}val": "52", f"{{{_W}}}hRule": "exact"})
        for width, fill in (
            (filled, theme.ACCENT_BLUE if top else "8EAADB"),
            (empty, theme.BAR_TRACK_COLOR),
        ):
            cell = self._new_cell(tr, width, pad=0)
            cell_pr = cell.find(f"./{{{_W}}}tcPr")
            assert cell_pr is not None
            ET.SubElement(cell_pr, f"{{{_W}}}shd", {f"{{{_W}}}fill": fill})
            ET.SubElement(cell, f"{{{_W}}}p")

    def _append_compact_remainder(
        self,
        rows: tuple[tuple[str, ...], ...],
        *,
        start_rank: int,
    ) -> None:
        self._append_body_label(f"完整明细 · 其余 {len(rows)} 项")
        half = (len(rows) + 1) // 2
        left_rows = rows[:half]
        right_rows = rows[half:]
        widths = (620, 3_350, 1_140, 1_100, 620, 3_350, 1_140, 1_100)
        table = self._new_layout_table(self.body, widths, caption="AIMACompactRemainder")
        for index in range(half):
            tr = ET.SubElement(table, f"{{{_W}}}tr")
            tr_pr = ET.SubElement(tr, f"{{{_W}}}trPr")
            ET.SubElement(tr_pr, f"{{{_W}}}cantSplit")
            pairs: list[tuple[str, str, str, str] | None] = []
            left = left_rows[index]
            pairs.append((f"{start_rank + index:02d}", left[0], left[1], left[2]))
            if index < len(right_rows):
                right = right_rows[index]
                pairs.append((f"{start_rank + half + index:02d}", right[0], right[1], right[2]))
            else:
                pairs.append(None)
            for pair_index, pair in enumerate(pairs):
                for column in range(4):
                    width = widths[pair_index * 4 + column]
                    cell = self._new_cell(tr, width, pad=38)
                    if pair is None:
                        ET.SubElement(cell, f"{{{_W}}}p")
                        continue
                    p = ET.SubElement(cell, f"{{{_W}}}p")
                    p_pr = ET.SubElement(p, f"{{{_W}}}pPr")
                    ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "10", f"{{{_W}}}after": "10"})
                    ET.SubElement(
                        p_pr,
                        f"{{{_W}}}jc",
                        {f"{{{_W}}}val": "right" if column >= 2 else "left"},
                    )
                    value = pair[column]
                    self._add_run(
                        p,
                        value,
                        bold=column == 2,
                        italic=False,
                        code=False,
                        color=theme.SECONDARY_TEXT_COLOR if column in {0, 3} else theme.TEXT_COLOR,
                        font_size="16",
                    )

    def _append_editorial_table(
        self,
        parent: ET.Element,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
    ) -> None:
        if not headers:
            return
        total_width = _VISUAL_LEFT_WIDTH - 260
        weights = [max(6, min(24, len(header) * 2)) for header in headers]
        weight_total = sum(weights)
        widths = [round(total_width * weight / weight_total) for weight in weights]
        widths[-1] += total_width - sum(widths)
        table = self._new_layout_table(parent, tuple(widths), caption="AIMAEditorialNested")
        for row_index, values in enumerate((headers, *rows)):
            tr = ET.SubElement(table, f"{{{_W}}}tr")
            tr_pr = ET.SubElement(tr, f"{{{_W}}}trPr")
            ET.SubElement(tr_pr, f"{{{_W}}}cantSplit")
            if row_index == 0:
                ET.SubElement(tr_pr, f"{{{_W}}}tblHeader")
            for column, value in enumerate(values):
                cell = self._new_cell(tr, widths[column], pad=55)
                cell_pr = cell.find(f"./{{{_W}}}tcPr")
                assert cell_pr is not None
                if row_index == 0:
                    ET.SubElement(cell_pr, f"{{{_W}}}shd", {f"{{{_W}}}fill": theme.SOFT_BACKGROUND})
                p = ET.SubElement(cell, f"{{{_W}}}p")
                p_pr = ET.SubElement(p, f"{{{_W}}}pPr")
                ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "10", f"{{{_W}}}after": "10"})
                ET.SubElement(
                    p_pr,
                    f"{{{_W}}}jc",
                    {f"{{{_W}}}val": "right" if row_index and column else "left"},
                )
                self._add_run(
                    p,
                    value,
                    bold=row_index == 0,
                    italic=False,
                    code=False,
                    color=theme.TITLE_COLOR if row_index == 0 else theme.TEXT_COLOR,
                    font_size="17",
                )

    def _append_compact_matrix(
        self,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
    ) -> None:
        column_count = len(headers)
        first_width = 2_450
        other_width = max(1, (theme.CONTENT_WIDTH_TWIPS - first_width) // (column_count - 1))
        widths = (first_width, *(other_width for _ in range(column_count - 1)))
        table = self._new_layout_table(self.body, tuple(widths), caption="AIMACompactDaily")
        for row_index, values in enumerate((headers, *rows)):
            tr = ET.SubElement(table, f"{{{_W}}}tr")
            tr_pr = ET.SubElement(tr, f"{{{_W}}}trPr")
            ET.SubElement(tr_pr, f"{{{_W}}}cantSplit")
            if row_index == 0:
                ET.SubElement(tr_pr, f"{{{_W}}}tblHeader")
            for column, value in enumerate(values):
                cell = self._new_cell(tr, widths[column], pad=52)
                cell_pr = cell.find(f"./{{{_W}}}tcPr")
                assert cell_pr is not None
                if row_index == 0:
                    ET.SubElement(cell_pr, f"{{{_W}}}shd", {f"{{{_W}}}fill": theme.SOFT_BACKGROUND})
                p = ET.SubElement(cell, f"{{{_W}}}p")
                p_pr = ET.SubElement(p, f"{{{_W}}}pPr")
                ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "9", f"{{{_W}}}after": "9"})
                ET.SubElement(
                    p_pr,
                    f"{{{_W}}}jc",
                    {f"{{{_W}}}val": "right" if row_index and column else "left"},
                )
                self._add_run(
                    p,
                    value,
                    bold=row_index == 0,
                    italic=False,
                    code=False,
                    color=theme.TITLE_COLOR if row_index == 0 else theme.TEXT_COLOR,
                    font_size="16",
                )
        self._add_after_layout_spacing()

    def _append_body_label(self, text: str) -> None:
        paragraph = ET.SubElement(self.body, f"{{{_W}}}p")
        self.paragraph_count += 1
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}before": "110", f"{{{_W}}}after": "55"})
        self._add_run(
            paragraph,
            text,
            bold=True,
            italic=False,
            code=False,
            color=theme.SECONDARY_TEXT_COLOR,
            font_size="18",
        )

    def _append_chart(
        self,
        parent: ET.Element,
        spec: ChartSpec,
        *,
        width_emu: int,
        height_emu: int,
    ) -> None:
        self.charts.append(spec)
        self.chart_count += 1
        paragraph = ET.SubElement(parent, f"{{{_W}}}p")
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}jc", {f"{{{_W}}}val": "center"})
        self._append_chart_inline(paragraph, self.chart_count, width_emu=width_emu, height_emu=height_emu)

    def _append_chart_inline(
        self,
        paragraph: ET.Element,
        chart_index: int,
        *,
        width_emu: int,
        height_emu: int,
    ) -> None:
        run = ET.SubElement(paragraph, f"{{{_W}}}r")
        drawing = ET.SubElement(run, f"{{{_W}}}drawing")
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
            {
                "id": str(3000 + chart_index),
                "name": f"chart-layout-{chart_index}",
                "descr": "可编辑数据图表",
            },
        )
        frame_pr = ET.SubElement(inline, f"{{{_WP}}}cNvGraphicFramePr")
        ET.SubElement(frame_pr, f"{{{_A}}}graphicFrameLocks", {"noChangeAspect": "1"})
        graphic = ET.SubElement(inline, f"{{{_A}}}graphic")
        graphic_data = ET.SubElement(graphic, f"{{{_A}}}graphicData", {"uri": _C})
        ET.SubElement(
            graphic_data,
            f"{{{_C}}}chart",
            {f"{{{_R}}}id": f"rId{chart_index + 1}"},
        )

    def _append_image(
        self,
        parent: ET.Element,
        image_path: Path,
        *,
        alt_text: str,
        max_width_emu: int,
        max_height_emu: int,
    ) -> None:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() != ".png":
            raise ValueError("Word 报告当前只支持 PNG 图片")
        with Image.open(path) as image:
            width_px, height_px = image.size
        width_emu = max_width_emu
        height_emu = round(width_emu * height_px / width_px)
        if height_emu > max_height_emu:
            height_emu = max_height_emu
            width_emu = round(height_emu * width_px / height_px)
        asset = _ImageAsset(path, alt_text, width_emu, height_emu)
        self.images.append(asset)
        self.image_count += 1
        paragraph = ET.SubElement(parent, f"{{{_W}}}p")
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}jc", {f"{{{_W}}}val": "center"})
        run = ET.SubElement(paragraph, f"{{{_W}}}r")
        drawing = ET.SubElement(run, f"{{{_W}}}drawing")
        inline = ET.SubElement(
            drawing,
            f"{{{_WP}}}inline",
            {"distT": "0", "distB": "0", "distL": "0", "distR": "0"},
        )
        ET.SubElement(
            inline,
            f"{{{_WP}}}extent",
            {"cx": str(asset.width_emu), "cy": str(asset.height_emu)},
        )
        ET.SubElement(
            inline,
            f"{{{_WP}}}docPr",
            {
                "id": str(4000 + self.image_count),
                "name": f"image-layout-{self.image_count}",
                "descr": alt_text or f"报告图片 {self.image_count}",
            },
        )
        graphic = ET.SubElement(inline, f"{{{_A}}}graphic")
        graphic_data = ET.SubElement(graphic, f"{{{_A}}}graphicData", {"uri": _PIC})
        picture = ET.SubElement(graphic_data, f"{{{_PIC}}}pic")
        nv = ET.SubElement(picture, f"{{{_PIC}}}nvPicPr")
        ET.SubElement(
            nv,
            f"{{{_PIC}}}cNvPr",
            {"id": "0", "name": f"image{self.image_count}.png", "descr": alt_text},
        )
        ET.SubElement(nv, f"{{{_PIC}}}cNvPicPr")
        fill = ET.SubElement(picture, f"{{{_PIC}}}blipFill")
        ET.SubElement(
            fill,
            f"{{{_A}}}blip",
            {f"{{{_R}}}embed": f"rId{1000 + self.image_count}"},
        )
        stretch = ET.SubElement(fill, f"{{{_A}}}stretch")
        ET.SubElement(stretch, f"{{{_A}}}fillRect")
        shape = ET.SubElement(picture, f"{{{_PIC}}}spPr")
        transform = ET.SubElement(shape, f"{{{_A}}}xfrm")
        ET.SubElement(transform, f"{{{_A}}}off", {"x": "0", "y": "0"})
        ET.SubElement(
            transform,
            f"{{{_A}}}ext",
            {"cx": str(asset.width_emu), "cy": str(asset.height_emu)},
        )
        geometry = ET.SubElement(shape, f"{{{_A}}}prstGeom", {"prst": "rect"})
        ET.SubElement(geometry, f"{{{_A}}}avLst")

    def _add_after_layout_spacing(self) -> None:
        paragraph = ET.SubElement(self.body, f"{{{_W}}}p")
        self.paragraph_count += 1
        p_pr = ET.SubElement(paragraph, f"{{{_W}}}pPr")
        ET.SubElement(p_pr, f"{{{_W}}}spacing", {f"{{{_W}}}after": "80"})


def _parse_integer(value: str) -> int:
    try:
        return int(value.strip().replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"Ranking 数量无法解析: {value}") from exc


def _parse_percentage(value: str) -> float:
    text = value.strip().removesuffix("%").replace(",", "")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Ranking 占比无法解析: {value}") from exc
