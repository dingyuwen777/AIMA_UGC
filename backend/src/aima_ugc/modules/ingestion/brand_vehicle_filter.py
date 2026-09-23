"""Stage 3 Excel/Historical 共用的品牌车型过滤快照与确定性过滤能力。"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.analysis import (
    ContentFilterSummary,
    deduplicate_unified_content_records,
)
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolution,
    BrandVehicleResolver,
)


class BrandVehicleFilterSnapshot(BaseModel):
    """任务创建时冻结的 Brand/Vehicle Filter，并标明数据入口的 Search 语义。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brand-vehicle-filter.v1"] = "brand-vehicle-filter.v1"
    search_semantics: Literal["not_applicable", "keyword_pack"] = "not_applicable"
    catalog: BrandVehicleCatalogSnapshot


@dataclass(frozen=True, slots=True)
class CanonicalFilterDeduplicationSummary:
    """Canonical 流过滤与去重的一次物化摘要。"""

    output_path: Path
    conflict_path: Path
    rows_seen: int
    rows_matched: int
    rows_filtered_out: int
    rows_written: int
    duplicates_removed: int
    conflicts: int


def resolve_canonical_brand_vehicle(
    snapshot: BrandVehicleFilterSnapshot,
    content: CanonicalContentV1,
    *,
    resolver: BrandVehicleResolver | None = None,
) -> BrandVehicleResolution:
    """用冻结目录解析一条 Canonical Content；Excel `text` 对应 Resolver `raw_text`。"""

    return (resolver or BrandVehicleResolver(snapshot.catalog)).resolve(
        snapshot.catalog,
        title=content.title,
        raw_text=content.text,
        transcript_text=None,
    )


def filter_canonical_content_by_brand_vehicle_jsonl(
    *,
    input_path: Path,
    output_path: Path,
    snapshot: BrandVehicleFilterSnapshot,
) -> ContentFilterSummary:
    """按冻结 Brand/Vehicle Snapshot 过滤 Canonical JSONL，并保留统一记录格式。"""

    source_path = Path(input_path)
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    target_path.unlink(missing_ok=True)
    rows_seen = 0
    rows_written = 0
    resolver = BrandVehicleResolver(snapshot.catalog)
    try:
        with (
            source_path.open("rb") as input_file,
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
        ):
            for line_number, raw_line in enumerate(input_file, start=1):
                rows_seen += 1
                content = _parse_canonical_line(raw_line, source_path, line_number)
                resolution = resolve_canonical_brand_vehicle(
                    snapshot,
                    content,
                    resolver=resolver,
                )
                if not resolution.matched:
                    continue
                record = UnifiedContentRecordV1(content=content)
                output_file.write(record.model_dump_json(exclude_none=False) + "\n")
                rows_written += 1
            output_file.flush()
            os.fsync(output_file.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    temp_path.replace(target_path)
    return ContentFilterSummary(
        input_path=source_path,
        output_path=target_path,
        rows_seen=rows_seen,
        rows_written=rows_written,
        rows_filtered_out=rows_seen - rows_written,
    )


def filter_and_deduplicate_canonical_contents(
    contents: Iterable[CanonicalContentV1],
    *,
    output_path: Path,
    snapshot: BrandVehicleFilterSnapshot,
    input_label: Path | None = None,
) -> CanonicalFilterDeduplicationSummary:
    """单次遍历完成目录过滤与身份去重，只发布一个 Unified JSONL。"""

    rows_seen = 0
    rows_matched = 0
    resolver = BrandVehicleResolver(snapshot.catalog)

    def matched_records() -> Iterator[UnifiedContentRecordV1]:
        nonlocal rows_seen, rows_matched
        for content in contents:
            rows_seen += 1
            resolution = resolve_canonical_brand_vehicle(
                snapshot,
                content,
                resolver=resolver,
            )
            if not resolution.matched:
                continue
            rows_matched += 1
            yield UnifiedContentRecordV1(content=content)

    deduplication = deduplicate_unified_content_records(
        matched_records(),
        input_path=input_label or Path("canonical-content.v1"),
        output_path=output_path,
    )
    return CanonicalFilterDeduplicationSummary(
        output_path=deduplication.output_path,
        conflict_path=deduplication.conflict_path,
        rows_seen=rows_seen,
        rows_matched=rows_matched,
        rows_filtered_out=rows_seen - rows_matched,
        rows_written=deduplication.rows_written,
        duplicates_removed=deduplication.duplicates_removed,
        conflicts=deduplication.conflicts,
    )


def _parse_canonical_line(raw_line: bytes, path: Path, line_number: int) -> CanonicalContentV1:
    """Fail-closed 解析单行 Canonical JSONL，避免坏行被过滤阶段静默吞掉。"""

    if not raw_line.strip():
        raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝继续处理")
    try:
        return CanonicalContentV1.model_validate_json(raw_line)
    except ValidationError as exc:
        raise ValueError(f"{path}: 第 {line_number} 行不是合法 CanonicalContentV1") from exc


__all__ = [
    "BrandVehicleFilterSnapshot",
    "CanonicalFilterDeduplicationSummary",
    "filter_and_deduplicate_canonical_contents",
    "filter_canonical_content_by_brand_vehicle_jsonl",
    "resolve_canonical_brand_vehicle",
]
