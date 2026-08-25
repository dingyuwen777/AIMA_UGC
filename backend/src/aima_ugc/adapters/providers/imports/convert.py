"""XLSX → Canonical JSONL 的生产编排入口。"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from aima_ugc.platform.time import beijing_now

from .excel_profile import get_excel_import_profile
from .excel_reader import iter_excel_rows
from .mapper import map_excel_row
from .models import (
    ExcelBatchConversionSummary,
    ExcelBatchImportRejectedRowsError,
    ExcelConversionSummary,
    ExcelImportRejectedRowsError,
    ExcelImportRowError,
    ExcelSourceConversionSummary,
)


def convert_excel_to_canonical_jsonl(
    *,
    input_path: Path,
    output_path: Path,
    profile_name: str,
    sheet_name: str | None = None,
    observed_at: datetime | None = None,
) -> ExcelConversionSummary:
    """流式转换完整工作表；任一行非法时不发布部分业务 JSONL。"""

    source_path = Path(input_path)
    target_path = Path(output_path)
    profile = get_excel_import_profile(profile_name)
    run_observed_at = observed_at or beijing_now()
    if run_observed_at.tzinfo is None:
        raise ValueError("observed_at 必须包含时区")
    run_observed_at = run_observed_at.astimezone(UTC)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    error_path = target_path.with_name("conversion_errors.jsonl")
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_error_path = error_path.with_name(f".{error_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    temp_error_path.unlink(missing_ok=True)
    target_path.unlink(missing_ok=True)
    error_path.unlink(missing_ok=True)

    rows_seen = 0
    rows_written = 0
    rows_rejected = 0
    try:
        with (
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
            temp_error_path.open("w", encoding="utf-8", newline="\n") as error_file,
        ):
            for row in iter_excel_rows(source_path, profile=profile, sheet_name=sheet_name):
                rows_seen += 1
                try:
                    content = map_excel_row(
                        row,
                        profile=profile,
                        input_name=source_path.name,
                        sheet_name=row.sheet_name,
                        observed_at=run_observed_at,
                    )
                except ExcelImportRowError as exc:
                    rows_rejected += 1
                    _write_error(error_file, row.row_number, exc.code, exc.message)
                    continue
                except ValidationError:
                    rows_rejected += 1
                    _write_error(
                        error_file,
                        row.row_number,
                        "canonical_validation_error",
                        "CanonicalContentV1 校验失败",
                    )
                    continue
                output_file.write(content.model_dump_json())
                output_file.write("\n")
                rows_written += 1

            output_file.flush()
            os.fsync(output_file.fileno())
            error_file.flush()
            os.fsync(error_file.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        temp_error_path.unlink(missing_ok=True)
        raise

    summary = ExcelConversionSummary(
        input_path=source_path,
        output_path=target_path,
        error_path=error_path,
        rows_seen=rows_seen,
        rows_written=rows_written,
        rows_rejected=rows_rejected,
    )
    temp_error_path.replace(error_path)
    if rows_rejected:
        temp_path.unlink(missing_ok=True)
        raise ExcelImportRejectedRowsError(summary)
    temp_path.replace(target_path)
    return summary


def convert_excel_files_to_canonical_jsonl(
    *,
    input_paths: Sequence[Path],
    output_path: Path,
    profile_name: str,
    sheet_name: str | None = None,
    observed_at: datetime | None = None,
) -> ExcelBatchConversionSummary:
    """按显式顺序流式合并多个 Excel；任一坏行时不发布部分 JSONL。"""

    source_paths = tuple(Path(path) for path in input_paths)
    if not source_paths:
        raise ValueError("多 Excel 转换至少需要一个输入文件")
    source_names: set[str] = set()
    resolved_paths: set[Path] = set()
    for source_path in source_paths:
        resolved = source_path.resolve()
        if resolved in resolved_paths:
            raise ValueError(f"多 Excel 输入路径重复: {source_path}")
        resolved_paths.add(resolved)
        normalized_name = source_path.name.casefold()
        if normalized_name in source_names:
            raise ValueError(f"多 Excel 文件名重复，无法唯一保留来源: {source_path.name}")
        source_names.add(normalized_name)

    target_path = Path(output_path)
    profile = get_excel_import_profile(profile_name)
    run_observed_at = observed_at or beijing_now()
    if run_observed_at.tzinfo is None:
        raise ValueError("observed_at 必须包含时区")
    run_observed_at = run_observed_at.astimezone(UTC)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    error_path = target_path.with_name("conversion_errors.jsonl")
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_error_path = error_path.with_name(f".{error_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    temp_error_path.unlink(missing_ok=True)
    target_path.unlink(missing_ok=True)
    error_path.unlink(missing_ok=True)

    file_summaries: list[ExcelSourceConversionSummary] = []
    try:
        with (
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
            temp_error_path.open("w", encoding="utf-8", newline="\n") as error_file,
        ):
            for source_path in source_paths:
                rows_seen = 0
                rows_written = 0
                rows_rejected = 0
                for row in iter_excel_rows(
                    source_path,
                    profile=profile,
                    sheet_name=sheet_name,
                ):
                    rows_seen += 1
                    try:
                        content = map_excel_row(
                            row,
                            profile=profile,
                            input_name=source_path.name,
                            sheet_name=row.sheet_name,
                            observed_at=run_observed_at,
                        )
                    except ExcelImportRowError as exc:
                        rows_rejected += 1
                        _write_error(
                            error_file,
                            row.row_number,
                            exc.code,
                            exc.message,
                            input_name=source_path.name,
                        )
                        continue
                    except ValidationError:
                        rows_rejected += 1
                        _write_error(
                            error_file,
                            row.row_number,
                            "canonical_validation_error",
                            "CanonicalContentV1 校验失败",
                            input_name=source_path.name,
                        )
                        continue
                    output_file.write(content.model_dump_json())
                    output_file.write("\n")
                    rows_written += 1
                file_summaries.append(
                    ExcelSourceConversionSummary(
                        input_path=source_path,
                        rows_seen=rows_seen,
                        rows_written=rows_written,
                        rows_rejected=rows_rejected,
                    )
                )

            output_file.flush()
            os.fsync(output_file.fileno())
            error_file.flush()
            os.fsync(error_file.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        temp_error_path.unlink(missing_ok=True)
        raise

    summary = ExcelBatchConversionSummary(
        input_paths=source_paths,
        output_path=target_path,
        error_path=error_path,
        files=tuple(file_summaries),
        rows_seen=sum(item.rows_seen for item in file_summaries),
        rows_written=sum(item.rows_written for item in file_summaries),
        rows_rejected=sum(item.rows_rejected for item in file_summaries),
    )
    temp_error_path.replace(error_path)
    if summary.rows_rejected:
        temp_path.unlink(missing_ok=True)
        raise ExcelBatchImportRejectedRowsError(summary)
    temp_path.replace(target_path)
    return summary


def _write_error(
    error_file: TextIO,
    row_number: int,
    code: str,
    message: str,
    *,
    input_name: str | None = None,
) -> None:
    payload = {
        **({"input_name": input_name} if input_name is not None else {}),
        "row_number": row_number,
        "code": code,
        "message": message,
    }
    error_file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    error_file.write("\n")
