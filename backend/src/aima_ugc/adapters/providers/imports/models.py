"""Excel File Provider 的最小输入/输出模型。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExcelImportRow:
    """Reader 从源工作表读取的一行，保留原始列值和物理行号。"""

    row_number: int
    values: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ExcelConversionSummary:
    """一次 XLSX → Canonical JSONL 转换的可观察汇总。"""

    input_path: Path
    output_path: Path
    error_path: Path
    rows_seen: int
    rows_written: int
    rows_rejected: int


@dataclass(frozen=True, slots=True)
class ExcelSourceConversionSummary:
    """多文件转换中一个源 Excel 的行计数。"""

    input_path: Path
    rows_seen: int
    rows_written: int
    rows_rejected: int


@dataclass(frozen=True, slots=True)
class ExcelBatchConversionSummary:
    """多个 Excel 合并发布到同一 Canonical JSONL 的汇总。"""

    input_paths: tuple[Path, ...]
    output_path: Path
    error_path: Path
    files: tuple[ExcelSourceConversionSummary, ...]
    rows_seen: int
    rows_written: int
    rows_rejected: int


class ExcelImportRowError(ValueError):
    """可安全写入错误清单的单行输入错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ExcelImportRejectedRowsError(RuntimeError):
    """存在被拒绝行时阻止发布部分 Canonical JSONL。"""

    def __init__(self, summary: ExcelConversionSummary) -> None:
        self.summary = summary
        super().__init__(
            f"Excel 转换存在 {summary.rows_rejected} 行错误；"
            f"详情见 {summary.error_path}，未发布 {summary.output_path}"
        )


class ExcelBatchImportRejectedRowsError(RuntimeError):
    """多文件转换存在坏行时阻止发布整个合并 JSONL。"""

    def __init__(self, summary: ExcelBatchConversionSummary) -> None:
        self.summary = summary
        super().__init__(
            f"多 Excel 转换存在 {summary.rows_rejected} 行错误；"
            f"详情见 {summary.error_path}，未发布 {summary.output_path}"
        )
