"""使用 openpyxl 流式读取受控 Profile 的 XLSX。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from openpyxl import load_workbook

from .excel_profile import ExcelImportProfile
from .models import ExcelImportRow


def iter_excel_rows(
    input_path: Path,
    *,
    profile: ExcelImportProfile,
    sheet_name: str | None = None,
) -> Iterator[ExcelImportRow]:
    """逐行读取 XLSX；只保留值，不把 Workbook 常驻为普通可写模式。"""

    path = Path(input_path)
    if path.suffix.casefold() != ".xlsx":
        raise ValueError(f"仅支持 .xlsx 文件: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        selected_sheet = sheet_name or profile.default_sheet_name
        if selected_sheet not in workbook.sheetnames:
            raise ValueError(f"工作表不存在: {selected_sheet}")
        worksheet = workbook[selected_sheet]
        rows = worksheet.iter_rows(values_only=True)
        try:
            raw_headers = next(rows)
        except StopIteration as exc:
            raise ValueError(f"工作表为空: {selected_sheet}") from exc

        headers = tuple(_header_name(value) for value in raw_headers)
        non_empty_headers = tuple(header for header in headers if header is not None)
        if len(non_empty_headers) != len(set(non_empty_headers)):
            raise ValueError("Excel 表头包含重复列名")
        missing = [header for header in profile.required_headers if header not in non_empty_headers]
        if missing:
            raise ValueError(f"Excel Profile 缺少必需列: {', '.join(missing)}")

        for row_number, values in enumerate(rows, start=2):
            if _row_is_blank(values):
                continue
            row_values = {
                header: values[index] if index < len(values) else None
                for index, header in enumerate(headers)
                if header is not None
            }
            yield ExcelImportRow(row_number=row_number, values=row_values)
    finally:
        workbook.close()


def _header_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).lstrip("\ufeff").strip()
    return text or None


def _row_is_blank(values: tuple[object, ...]) -> bool:
    return all(value is None or (isinstance(value, str) and not value.strip()) for value in values)
