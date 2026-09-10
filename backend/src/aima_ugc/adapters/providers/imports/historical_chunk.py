"""历史 XLSX 到有界 Pure Canonical JSONL Chunk 的流式转换。"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from .excel_profile import get_excel_import_profile
from .excel_reader import iter_excel_rows
from .mapper import map_excel_row
from .models import ExcelImportRowError


@dataclass(frozen=True, slots=True)
class HistoricalInvalidRow:
    """不能伪造成 Canonical、但必须进入逐行账本的最小错误事实。"""

    source_row_ordinal: int
    error_code: str


@dataclass(frozen=True, slots=True)
class HistoricalChunkDescriptor:
    ordinal: int
    row_start: int
    row_end: int
    row_count: int
    canonical_row_ordinals: tuple[int, ...]
    invalid_rows: tuple[HistoricalInvalidRow, ...]
    path: Path


@dataclass(frozen=True, slots=True)
class HistoricalConversionSummary:
    rows_seen: int
    canonical_rows: int
    invalid: int
    chunks: int


def convert_historical_excel_to_chunks(
    *,
    input_path: Path,
    output_dir: Path,
    profile_name: str,
    observed_at: datetime,
    chunk_rows: int,
    publish: Callable[[HistoricalChunkDescriptor], None],
) -> HistoricalConversionSummary:
    """只执行 Reader/Mapper；合法 Canonical 与 invalid 最小事实分离发布。"""

    if chunk_rows < 1:
        raise ValueError("chunk_rows 必须为正数")
    if observed_at.utcoffset() is None:
        raise ValueError("observed_at 必须包含时区")
    profile = get_excel_import_profile(profile_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    counters = {"rows_seen": 0, "canonical_rows": 0, "invalid": 0, "chunks": 0}
    handle = None
    descriptor_values: dict[str, int] = {}
    canonical_row_ordinals: list[int] = []
    invalid_rows: list[HistoricalInvalidRow] = []
    chunk_path: Path | None = None

    def open_chunk(row_number: int) -> None:
        nonlocal handle, chunk_path, descriptor_values, canonical_row_ordinals, invalid_rows
        ordinal = counters["chunks"]
        chunk_path = output_dir / f"chunk-{ordinal:08d}.jsonl"
        handle = chunk_path.open("w", encoding="utf-8", newline="\n")
        descriptor_values = {
            "ordinal": ordinal,
            "row_start": row_number,
            "row_end": row_number,
            "row_count": 0,
        }
        canonical_row_ordinals = []
        invalid_rows = []

    def close_chunk() -> None:
        nonlocal handle, chunk_path
        if handle is None or chunk_path is None:
            return
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        descriptor = HistoricalChunkDescriptor(
            path=chunk_path,
            canonical_row_ordinals=tuple(canonical_row_ordinals),
            invalid_rows=tuple(invalid_rows),
            **descriptor_values,
        )
        publish(descriptor)
        chunk_path.unlink(missing_ok=True)
        counters["chunks"] += 1
        handle = None
        chunk_path = None

    try:
        for row in iter_excel_rows(input_path, profile=profile):
            if handle is None:
                open_chunk(row.row_number)
            assert handle is not None
            counters["rows_seen"] += 1
            descriptor_values["row_end"] = row.row_number
            descriptor_values["row_count"] += 1
            try:
                content = map_excel_row(
                    row,
                    profile=profile,
                    input_name=input_path.name,
                    sheet_name=row.sheet_name,
                    observed_at=observed_at,
                )
                handle.write(content.model_dump_json())
                handle.write("\n")
                canonical_row_ordinals.append(row.row_number)
                counters["canonical_rows"] += 1
            except ExcelImportRowError as exc:
                invalid_rows.append(HistoricalInvalidRow(row.row_number, exc.code))
                counters["invalid"] += 1
            except ValidationError:
                invalid_rows.append(
                    HistoricalInvalidRow(row.row_number, "canonical_validation_error")
                )
                counters["invalid"] += 1
            if descriptor_values["row_count"] >= chunk_rows:
                close_chunk()
        close_chunk()
    except BaseException:
        if handle is not None:
            handle.close()
        if chunk_path is not None:
            chunk_path.unlink(missing_ok=True)
        raise
    finally:
        for path in output_dir.glob("chunk-*.jsonl"):
            try:
                path.unlink()
            except OSError:
                pass
    return HistoricalConversionSummary(**counters)


__all__ = [
    "HistoricalChunkDescriptor",
    "HistoricalConversionSummary",
    "HistoricalInvalidRow",
    "convert_historical_excel_to_chunks",
]
