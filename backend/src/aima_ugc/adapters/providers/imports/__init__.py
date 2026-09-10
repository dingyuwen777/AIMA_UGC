"""Excel File Provider 公共入口。"""

from .convert import convert_excel_files_to_canonical_jsonl, convert_excel_to_canonical_jsonl
from .excel_profile import AIMA_MONITORING_EXCEL_V1, ExcelImportProfile, get_excel_import_profile
from .labeled_content_reader import (
    CONTENT_SHEET_NAME,
    REAL_USER_VOICE_TYPE,
    TARGET_PLATFORMS,
    LabeledContent,
    LabeledContentReaderError,
    LabeledContentReadSummary,
    iter_labeled_contents,
    read_labeled_content_files,
    read_labeled_contents,
)
from .models import (
    ExcelBatchConversionSummary,
    ExcelBatchImportRejectedRowsError,
    ExcelConversionSummary,
    ExcelImportRejectedRowsError,
    ExcelSourceConversionSummary,
)

__all__ = [
    "AIMA_MONITORING_EXCEL_V1",
    "CONTENT_SHEET_NAME",
    "REAL_USER_VOICE_TYPE",
    "TARGET_PLATFORMS",
    "ExcelBatchConversionSummary",
    "ExcelBatchImportRejectedRowsError",
    "ExcelConversionSummary",
    "ExcelImportProfile",
    "ExcelImportRejectedRowsError",
    "ExcelSourceConversionSummary",
    "LabeledContent",
    "LabeledContentReadSummary",
    "LabeledContentReaderError",
    "convert_excel_files_to_canonical_jsonl",
    "convert_excel_to_canonical_jsonl",
    "get_excel_import_profile",
    "iter_labeled_contents",
    "read_labeled_content_files",
    "read_labeled_contents",
]
