"""按 openpyxl 3.1.5 的值语义流式读取 XLSX Worksheet XML。"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import Any

from openpyxl.cell.text import Text
from openpyxl.utils.datetime import from_excel, from_ISO8601
from openpyxl.xml.functions import iterparse

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_ROW = f"{_NS}row"
_CELL = f"{_NS}c"
_SHEET_DATA = f"{_NS}sheetData"
_VALUE = f"{_NS}v"
_INLINE = f"{_NS}is"
_TEXT = f"{_NS}t"


def iter_worksheet_values(workbook: Any, worksheet: Any) -> Iterator[tuple[object, ...]]:
    """跳过逐 Cell 对象装配；日期、共享字符串及缺失行保持原读取语义。"""

    archive = workbook._archive
    worksheet_path = worksheet._worksheet_path
    with archive.open(worksheet_path) as source:
        sheet_data = None
        row_values: dict[int, object] = {}
        previous_row = 0
        previous_column = 0
        for event, element in iterparse(source, events=("start", "end")):
            if event == "start":
                if element.tag == _SHEET_DATA:
                    sheet_data = element
                elif element.tag == _ROW:
                    row_values = {}
                    previous_column = 0
                continue
            if element.tag == _CELL:
                coordinate = element.get("r")
                if coordinate:
                    column = _column_number(coordinate)
                    if column == 0:
                        raise ValueError("Worksheet Cell 坐标无效")
                else:
                    column = previous_column + 1
                previous_column = column
                row_values[column] = _cell_value(workbook, worksheet, element, coordinate)
                element.clear()
            elif element.tag == _ROW:
                row_number = int(element.get("r") or previous_row + 1)
                for _ in range(previous_row + 1, row_number):
                    yield ()
                width = max(row_values, default=0)
                yield tuple(row_values.get(index) for index in range(1, width + 1))
                previous_row = row_number
                element.clear()
                if sheet_data is not None:
                    sheet_data.clear()


def _column_number(coordinate: str) -> int:
    column = 0
    for char in coordinate:
        value = ord(char)
        if 65 <= value <= 90:
            column = column * 26 + value - 64
        else:
            break
    return column


def _cell_value(workbook: Any, worksheet: Any, element: Any, coordinate: str | None) -> object:
    kind = element.get("t", "n")
    if kind == "inlineStr":
        inline = element.find(_INLINE)
        if inline is None:
            return None
        if len(inline) == 1 and inline[0].tag == _TEXT:
            return inline[0].text or ""
        rich_text = Text.from_tree(inline)
        return rich_text.content if rich_text is not None else None

    raw = element.findtext(_VALUE) or None
    if raw is None:
        return None
    if kind == "n":
        value: object = float(raw) if any(char in raw for char in ".Ee") else int(raw)
        style_id = int(element.get("s", "0"))
        if style_id in workbook._date_formats:
            try:
                return from_excel(
                    value,
                    workbook.epoch,
                    timedelta=style_id in workbook._timedelta_formats,
                )
            except OverflowError, ValueError:
                warnings.warn(
                    f"Cell {coordinate} is marked as a date but the serial value {value} "
                    "is outside the limits for dates. The cell will be treated as an error.",
                    stacklevel=2,
                )
                return "#VALUE!"
        return value
    if kind == "s":
        return worksheet._shared_strings[int(raw)]
    if kind == "b":
        return bool(int(raw))
    if kind == "d":
        return from_ISO8601(raw)  # type: ignore[no-untyped-call]
    return raw


__all__ = ["iter_worksheet_values"]
