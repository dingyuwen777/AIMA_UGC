"""监测 Excel 目录批量过滤人工入口；只处理 AIMA 当前五个平台。"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from aima_ugc.adapters.providers.imports import AIMA_MONITORING_EXCEL_V1
from aima_ugc.adapters.providers.imports.excel_profile import get_excel_import_profile
from aima_ugc.adapters.providers.imports.excel_reader import iter_excel_rows
from aima_ugc.adapters.providers.imports.mapper import map_excel_row
from aima_ugc.adapters.providers.imports.models import ExcelImportRowError
from aima_ugc.adapters.providers.imports_test.keyword_pack import load_keyword_pack
from aima_ugc.modules.analysis import (
    ContentDeduplicationSummary,
    ContentFilterSummary,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
)
from aima_ugc.platform.time import beijing_now

INPUT_DIR = Path(r"E:\AIMA_UGC_data\monitoring")
OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output" / "monitoring_excel_filter"
KEYWORD_PACK_FILE = Path(__file__).with_name("keyword_pack.txt")
PROFILE = AIMA_MONITORING_EXCEL_V1
SHEET_NAME: str | None = None

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")


@dataclass(frozen=True, slots=True)
class SourceFileSummary:
    """记录单个源 Excel 的读取、五平台转换和非目标来源跳过统计。"""

    source: str
    rows_seen: int
    rows_supported_platform: int
    rows_skipped_platform_unmapped: int


@dataclass(frozen=True, slots=True)
class DirectoryConversionSummary:
    """记录一次目录 Excel → Canonical JSONL 的转换结果。"""

    input_root: Path
    output_path: Path
    files: tuple[SourceFileSummary, ...]
    skipped_media_names: tuple[tuple[str, int], ...]
    rows_seen: int
    rows_supported_platform: int
    rows_skipped_platform_unmapped: int


@dataclass(frozen=True, slots=True)
class MonitoringFilterRunSummary:
    """记录一次完整目录过滤运行的最终结果。"""

    run_id: str
    run_dir: Path
    run_summary_path: Path
    canonical_path: Path
    filtered_path: Path
    deduplicated_path: Path
    deduplication_conflicts_path: Path


def discover_input_files(input_dir: Path) -> tuple[Path, ...]:
    """递归发现输入目录中的 XLSX，并返回确定性排序后的文件列表。"""

    root = Path(input_dir)
    if not root.exists():
        raise FileNotFoundError(f"监测 Excel 输入目录不存在: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"监测 Excel 输入路径不是目录: {root}")

    files = tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file()
                and path.suffix.casefold() == ".xlsx"
                and not path.name.startswith("~$")
            ),
            key=lambda path: path.relative_to(root).as_posix().casefold(),
        )
    )
    if not files:
        raise FileNotFoundError(f"监测 Excel 输入目录未发现 .xlsx 文件: {root}")
    return files


def prepare_run_dir(*, output_root: Path, run_id: str | None = None) -> tuple[str, Path]:
    """创建一次独立输出目录，禁止覆盖已有 run。"""

    actual_run_id = run_id or beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(actual_run_id):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    run_dir = Path(output_root) / "runs" / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return actual_run_id, run_dir


def convert_supported_platforms(
    *,
    input_paths: tuple[Path, ...],
    input_root: Path,
    output_path: Path,
    profile_name: str = PROFILE,
    sheet_name: str | None = SHEET_NAME,
    observed_at: datetime | None = None,
) -> DirectoryConversionSummary:
    """流式转换五平台 Excel 行；只把明确的 ``platform_unmapped`` 当作预期跳过。"""

    if not input_paths:
        raise ValueError("目录转换至少需要一个 Excel 输入文件")

    root = Path(input_root).resolve()
    profile = get_excel_import_profile(profile_name)
    run_observed_at = observed_at or beijing_now()
    if run_observed_at.tzinfo is None or run_observed_at.utcoffset() is None:
        raise ValueError("observed_at 必须包含时区")
    run_observed_at = run_observed_at.astimezone(UTC)

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_path.unlink(missing_ok=True)

    file_summaries: list[SourceFileSummary] = []
    skipped_media_names: Counter[str] = Counter()
    total_rows_seen = 0
    total_rows_supported = 0
    total_rows_skipped = 0

    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            for source_path in input_paths:
                resolved_source = Path(source_path).resolve()
                try:
                    relative_source = resolved_source.relative_to(root).as_posix()
                except ValueError as exc:
                    raise ValueError(f"Excel 不在 input_root 下: {source_path}") from exc

                rows_seen = 0
                rows_supported = 0
                rows_skipped = 0
                for row in iter_excel_rows(
                    resolved_source,
                    profile=profile,
                    sheet_name=sheet_name,
                ):
                    rows_seen += 1
                    try:
                        content = map_excel_row(
                            row,
                            profile=profile,
                            input_name=relative_source,
                            sheet_name=row.sheet_name,
                            observed_at=run_observed_at,
                        )
                    except ExcelImportRowError as exc:
                        if exc.code != "platform_unmapped":
                            raise ValueError(
                                f"{relative_source}: 第 {row.row_number} 行转换失败 "
                                f"[{exc.code}] {exc.message}"
                            ) from exc
                        rows_skipped += 1
                        media_name = _display_text(row.values.get("媒体名称（中文）"))
                        skipped_media_names[media_name] += 1
                        continue
                    except ValidationError as exc:
                        raise ValueError(
                            f"{relative_source}: 第 {row.row_number} 行 "
                            "CanonicalContentV1 校验失败"
                        ) from exc

                    output_file.write(content.model_dump_json())
                    output_file.write("\n")
                    rows_supported += 1

                if rows_seen != rows_supported + rows_skipped:
                    raise RuntimeError(f"{relative_source}: 转换统计不守恒")

                file_summaries.append(
                    SourceFileSummary(
                        source=relative_source,
                        rows_seen=rows_seen,
                        rows_supported_platform=rows_supported,
                        rows_skipped_platform_unmapped=rows_skipped,
                    )
                )
                total_rows_seen += rows_seen
                total_rows_supported += rows_supported
                total_rows_skipped += rows_skipped

            output_file.flush()
            os.fsync(output_file.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    if total_rows_seen != total_rows_supported + total_rows_skipped:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("目录转换统计不守恒")

    os.replace(temp_path, target_path)
    return DirectoryConversionSummary(
        input_root=root,
        output_path=target_path,
        files=tuple(file_summaries),
        skipped_media_names=tuple(sorted(skipped_media_names.items())),
        rows_seen=total_rows_seen,
        rows_supported_platform=total_rows_supported,
        rows_skipped_platform_unmapped=total_rows_skipped,
    )


def filter_keywords(
    *,
    canonical_path: Path,
    filtered_path: Path,
    keywords: tuple[str, ...],
) -> ContentFilterSummary:
    """复用现有关键词过滤；品牌词和车型词位于同一 OR 维度。"""

    return filter_canonical_content_jsonl(
        input_path=canonical_path,
        output_path=filtered_path,
        keywords=keywords,
    )


def deduplicate(
    *,
    filtered_path: Path,
    deduplicated_path: Path,
) -> ContentDeduplicationSummary:
    """复用现有稳定身份去重，统一处理跨 Excel 重复内容。"""

    return deduplicate_content_jsonl(
        input_path=filtered_path,
        output_path=deduplicated_path,
    )


def process_directory(
    *,
    input_dir: Path = INPUT_DIR,
    output_root: Path = OUTPUT_ROOT,
    keyword_pack_file: Path = KEYWORD_PACK_FILE,
    profile_name: str = PROFILE,
    sheet_name: str | None = SHEET_NAME,
    run_id: str | None = None,
    observed_at: datetime | None = None,
) -> MonitoringFilterRunSummary:
    """完成目录发现、五平台转换、关键词过滤、去重和运行摘要。"""

    input_paths = discover_input_files(input_dir)
    keyword_pack = load_keyword_pack(keyword_pack_file)
    actual_run_id, run_dir = prepare_run_dir(output_root=output_root, run_id=run_id)

    canonical_path = run_dir / "canonical" / "contents.jsonl"
    filtered_path = run_dir / "filtered" / "contents.jsonl"
    deduplicated_path = run_dir / "deduplicated" / "contents.jsonl"

    conversion = convert_supported_platforms(
        input_paths=input_paths,
        input_root=input_dir,
        output_path=canonical_path,
        profile_name=profile_name,
        sheet_name=sheet_name,
        observed_at=observed_at,
    )
    filtering = filter_keywords(
        canonical_path=canonical_path,
        filtered_path=filtered_path,
        keywords=keyword_pack.keywords,
    )
    deduplication = deduplicate(
        filtered_path=filtered_path,
        deduplicated_path=deduplicated_path,
    )

    if filtering.rows_seen != conversion.rows_supported_platform:
        raise RuntimeError("Canonical 行数与过滤输入统计不一致")
    if deduplication.rows_seen != filtering.rows_written:
        raise RuntimeError("过滤输出行数与去重输入统计不一致")
    if deduplication.rows_written + deduplication.duplicates_removed != deduplication.rows_seen:
        raise RuntimeError("去重统计不守恒")

    run_summary_path = run_dir / "run_summary.json"
    _atomic_write_json(
        run_summary_path,
        _run_summary_payload(
            run_id=actual_run_id,
            conversion=conversion,
            filtering=filtering,
            deduplication=deduplication,
            keyword_count=keyword_pack.effective_keyword_count,
        ),
    )
    return MonitoringFilterRunSummary(
        run_id=actual_run_id,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        canonical_path=canonical_path,
        filtered_path=filtered_path,
        deduplicated_path=deduplicated_path,
        deduplication_conflicts_path=deduplication.conflict_path,
    )


def _run_summary_payload(
    *,
    run_id: str,
    conversion: DirectoryConversionSummary,
    filtering: ContentFilterSummary,
    deduplication: ContentDeduplicationSummary,
    keyword_count: int,
) -> dict[str, object]:
    """构造稳定且可对账的人工运行摘要。"""

    return {
        "schema_version": "monitoring-excel-filter-run.v1",
        "run_id": run_id,
        "input_root": str(conversion.input_root),
        "input_file_count": len(conversion.files),
        "keyword_count": keyword_count,
        "rows_seen": conversion.rows_seen,
        "rows_supported_platform": conversion.rows_supported_platform,
        "rows_skipped_platform_unmapped": conversion.rows_skipped_platform_unmapped,
        "rows_keyword_matched": filtering.rows_written,
        "rows_keyword_filtered_out": filtering.rows_filtered_out,
        "rows_after_deduplication": deduplication.rows_written,
        "duplicates_removed": deduplication.duplicates_removed,
        "deduplication_conflicts": deduplication.conflicts,
        "skipped_media_names": dict(conversion.skipped_media_names),
        "files": [
            {
                "source": item.source,
                "rows_seen": item.rows_seen,
                "rows_supported_platform": item.rows_supported_platform,
                "rows_skipped_platform_unmapped": item.rows_skipped_platform_unmapped,
            }
            for item in conversion.files
        ],
        "outputs": {
            "canonical": str(conversion.output_path),
            "filtered": str(filtering.output_path),
            "deduplicated": str(deduplication.output_path),
            "deduplication_conflicts": str(deduplication.conflict_path),
        },
    }


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """原子写入 UTF-8 JSON，失败时不发布半成品。"""

    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp_path, target_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _display_text(value: Any) -> str:
    """把非空媒体来源值转换成稳定可读文本，仅用于跳过统计。"""

    text = "" if value is None else str(value).strip()
    return text or "<empty>"


def main() -> None:
    """使用文件顶部人工配置执行一次目录批处理。"""

    result = process_directory()
    print(
        "监测 Excel 目录过滤完成: "
        f"run_id={result.run_id}, "
        f"final_jsonl={result.deduplicated_path}, "
        f"summary={result.run_summary_path}"
    )


if __name__ == "__main__":
    main()
