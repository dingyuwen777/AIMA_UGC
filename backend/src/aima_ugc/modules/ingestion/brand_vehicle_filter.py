"""Stage 3 Excel/Historical 共用的品牌车型过滤快照与确定性过滤能力。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.modules.analysis import ContentFilterSummary
from aima_ugc.modules.vehicles.brand_vehicle import (
    BrandVehicleCatalogSnapshot,
    BrandVehicleResolution,
    BrandVehicleResolver,
)


class BrandVehicleFilterSnapshot(BaseModel):
    """任务创建时冻结的 Brand/Vehicle Filter；Excel Search 明确不适用。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brand-vehicle-filter.v1"] = "brand-vehicle-filter.v1"
    search_semantics: Literal["not_applicable"] = "not_applicable"
    catalog: BrandVehicleCatalogSnapshot


def resolve_canonical_brand_vehicle(
    snapshot: BrandVehicleFilterSnapshot,
    content: CanonicalContentV1,
) -> BrandVehicleResolution:
    """用冻结目录解析一条 Canonical Content；Excel `text` 对应 Resolver `raw_text`。"""

    return BrandVehicleResolver().resolve(
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
    try:
        with (
            source_path.open("rb") as input_file,
            temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
        ):
            for line_number, raw_line in enumerate(input_file, start=1):
                rows_seen += 1
                content = _parse_canonical_line(raw_line, source_path, line_number)
                resolution = resolve_canonical_brand_vehicle(snapshot, content)
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
    "filter_canonical_content_by_brand_vehicle_jsonl",
    "resolve_canonical_brand_vehicle",
]
