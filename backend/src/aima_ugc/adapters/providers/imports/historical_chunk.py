"""历史 XLSX 到版本化有界 gzip JSONL Chunk 的流式转换。"""

from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from aima_ugc.modules.analysis import RelevanceKeyword, RelevanceService
from aima_ugc.modules.ingestion.historical_chunk import HISTORICAL_CHUNK_SCHEMA_VERSION

from .excel_profile import get_excel_import_profile
from .excel_reader import iter_excel_rows
from .mapper import map_excel_row
from .models import ExcelImportRowError


@dataclass(frozen=True, slots=True)
class HistoricalChunkDescriptor:
    ordinal: int
    row_start: int
    row_end: int
    row_count: int
    candidate_count: int
    filtered_count: int
    invalid_count: int
    path: Path


@dataclass(frozen=True, slots=True)
class HistoricalConversionSummary:
    rows_seen: int
    candidates: int
    filtered: int
    invalid: int
    chunks: int


def convert_historical_excel_to_chunks(
    *,
    input_path: Path,
    output_dir: Path,
    profile_name: str,
    effective_keywords: tuple[str, ...],
    observed_at: datetime,
    chunk_rows: int,
    publish: Callable[[HistoricalChunkDescriptor], None],
) -> HistoricalConversionSummary:
    """流式映射并逐 Chunk 发布；不会把完整工作簿或全部 Canonical 放入内存。"""

    if chunk_rows < 1:
        raise ValueError("chunk_rows 必须为正数")
    if observed_at.utcoffset() is None:
        raise ValueError("observed_at 必须包含时区")
    profile = get_excel_import_profile(profile_name)
    relevance = RelevanceService(
        tuple(
            RelevanceKeyword(text=value, priority=index)
            for index, value in enumerate(effective_keywords)
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    counters = {"rows_seen": 0, "candidates": 0, "filtered": 0, "invalid": 0, "chunks": 0}
    handle: gzip.GzipFile | None = None
    descriptor_values: dict[str, int] = {}
    chunk_path: Path | None = None

    def open_chunk(row_number: int) -> None:
        nonlocal handle, chunk_path, descriptor_values
        ordinal = counters["chunks"]
        chunk_path = output_dir / f"chunk-{ordinal:08d}.jsonl.gz"
        handle = gzip.GzipFile(filename=chunk_path, mode="wb", compresslevel=6, mtime=0)
        descriptor_values = {
            "ordinal": ordinal,
            "row_start": row_number,
            "row_end": row_number,
            "row_count": 0,
            "candidate_count": 0,
            "filtered_count": 0,
            "invalid_count": 0,
        }

    def close_chunk() -> None:
        nonlocal handle, chunk_path
        if handle is None or chunk_path is None:
            return
        handle.close()
        descriptor = HistoricalChunkDescriptor(path=chunk_path, **descriptor_values)
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
            payload: dict[str, object]
            try:
                content = map_excel_row(
                    row,
                    profile=profile,
                    input_name=input_path.name,
                    sheet_name=row.sheet_name,
                    observed_at=observed_at,
                )
                decision = relevance.evaluate(content)
                outcome = "candidate" if decision.matched else "filtered"
                payload = {
                    "schema_version": HISTORICAL_CHUNK_SCHEMA_VERSION,
                    "source_row_ordinal": row.row_number,
                    "outcome": outcome,
                    "content": content.model_dump(mode="json"),
                    "error_code": None,
                }
                counter_name = "candidates" if decision.matched else "filtered"
                descriptor_name = "candidate_count" if decision.matched else "filtered_count"
                counters[counter_name] += 1
                descriptor_values[descriptor_name] += 1
            except ExcelImportRowError as exc:
                payload = {
                    "schema_version": HISTORICAL_CHUNK_SCHEMA_VERSION,
                    "source_row_ordinal": row.row_number,
                    "outcome": "invalid",
                    "content": None,
                    "error_code": exc.code,
                }
                counters["invalid"] += 1
                descriptor_values["invalid_count"] += 1
            except ValidationError:
                payload = {
                    "schema_version": HISTORICAL_CHUNK_SCHEMA_VERSION,
                    "source_row_ordinal": row.row_number,
                    "outcome": "invalid",
                    "content": None,
                    "error_code": "canonical_validation_error",
                }
                counters["invalid"] += 1
                descriptor_values["invalid_count"] += 1
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            handle.write(encoded + b"\n")
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
        for path in output_dir.glob("chunk-*.jsonl.gz"):
            try:
                path.unlink()
            except OSError:
                pass
    return HistoricalConversionSummary(**counters)


__all__ = [
    "HistoricalChunkDescriptor",
    "HistoricalConversionSummary",
    "convert_historical_excel_to_chunks",
]
