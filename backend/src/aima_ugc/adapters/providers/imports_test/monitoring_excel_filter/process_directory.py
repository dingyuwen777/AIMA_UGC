"""监测 Excel 目录批量过滤人工入口。"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.imports.excel_profile import get_excel_import_profile
from aima_ugc.adapters.providers.imports.excel_reader import iter_excel_rows
from aima_ugc.adapters.providers.imports.mapper import map_excel_row
from aima_ugc.adapters.providers.imports.models import ExcelImportRowError
from aima_ugc.adapters.providers.imports_test.keyword_pack import load_keyword_pack
from aima_ugc.modules.analysis import (
    ContentFilterSummary,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
)
from aima_ugc.platform.time import beijing_now

INPUT_DIR = Path(r"E:\\AIMA_UGC_data\\monitoring")
OUTPUT_ROOT = Path(__file__).with_name("output")
KEYWORD_PACK_FILE = Path(__file__).with_name("keyword_pack.txt")
PROFILE = "aima-monitoring-excel.v1"
SHEET_NAME: str | None = None

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")


@dataclass(frozen=True, slots=True)
class SourceFileSummary:
    """记录单个 Excel 的读取、五平台保留和非目标平台跳过统计。"""

    source: str
    rows_seen: int
    rows_supported_platform: int
    rows_skipped_platform_unmapped: int
    skipped_media_names: dict[str, int]


@dataclass(frozen=True, slots=True)
class DirectoryConversionSummary:
    """记录一次目录级 Excel → Canonical 转换统计。"""

    input_root: Path
    input_paths: tuple[Path, ...]
    output_path: Path
    files: tuple[SourceFileSummary, ...]
    rows_seen: int
    rows_supported_platform: int
    rows_skipped_platform_unmapped: int
    skipped_media_names: dict[str, int]


@dataclass(frozen=True, slots=True)
class MonitoringFilterRunSummary:
    """记录一次目录监测数据筛选任务的最终交付统计与文件位置。"""

    run_id: str
    run_dir: Path
    run_summary_path: Path
    input_root: Path
    input_file_count: int
    keyword_count: int
    rows_seen: int
    rows_supported_platform: int
    rows_skipped_platform_unmapped: int
    rows_keyword_matched: int
    rows_keyword_filtered_out: int
    rows_after_deduplication: int
    duplicates_removed: int
    deduplication_conflicts: int
    skipped_media_names: dict[str, int]
    files: tuple[SourceFileSummary, ...]
    canonical_path: Path
    filtered_path: Path
    deduplicated_path: Path
    deduplication_conflicts_path: Path


def discover_input_files(input_dir: Path) -> tuple[Path, ...]:
    """递归发现输入目录中的 XLSX，并按文件名和相对路径稳定排序。"""

    root = Path(input_dir)
    if not root.exists():
        raise FileNotFoundError(f"输入目录不存在: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"输入路径不是目录: {root}")

    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.casefold() == ".xlsx"
        and not path.name.startswith("~$")
    ]
    if not files:
        raise FileNotFoundError(f"输入目录未发现 XLSX: {root}")

    files.sort(
        key=lambda path: (
            path.name.casefold(),
            path.relative_to(root).as_posix().casefold(),
        )
    )
    return tuple(files)


def prepare_run_dir(*, output_root: Path, run_id: str | None = None) -> tuple[str, Path]:
    """创建独立运行目录，避免一次性批处理覆盖既有输出。"""

    actual_run_id = _resolve_run_id(run_id)
    run_dir = Path(output_root) / "runs" / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return actual_run_id, run_dir


def convert_supported_platforms(
    *,
    input_paths: tuple[Path, ...],
    input_root: Path,
    output_path: Path,
    profile_name: str,
    sheet_name: str | None,
    observed_at: datetime | None = None,
) -> DirectoryConversionSummary:
    """把目录内 Excel 转为五平台 Canonical，并只跳过 ``platform_unmapped``。"""

    if not input_paths:
        raise ValueError("至少需要一个输入 XLSX")

    root = Path(input_root)
    profile = get_excel_import_profile(profile_name)
    run_observed_at = observed_at or beijing_now()
    if run_observed_at.tzinfo is None:
        raise ValueError("observed_at 必须包含时区")
    run_observed_at = run_observed_at.astimezone(UTC)

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    target_path.unlink(missing_ok=True)

    file_summaries: list[SourceFileSummary] = []
    skipped_media_names: Counter[str] = Counter()
    rows_seen = 0
    rows_supported_platform = 0
    rows_skipped_platform_unmapped = 0

    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            for source_path in input_paths:
                source = Path(source_path)
                relative_source = source.relative_to(root).as_posix()
                file_rows_seen = 0
                file_rows_supported = 0
                file_rows_skipped = 0
                file_skipped_media_names: Counter[str] = Counter()

                for row in iter_excel_rows(source, profile=profile, sheet_name=sheet_name):
                    file_rows_seen += 1
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
                            raise
                        media_name = _display_media_name(row.values.get("媒体名称（中文）"))
                        file_rows_skipped += 1
                        rows_skipped_platform_unmapped += 1
                        file_skipped_media_names[media_name] += 1
                        skipped_media_names[media_name] += 1
                        continue

                    output_file.write(content.model_dump_json())
                    output_file.write("\n")
                    file_rows_supported += 1
                    rows_supported_platform += 1

                file_summaries.append(
                    SourceFileSummary(
                        source=relative_source,
                        rows_seen=file_rows_seen,
                        rows_supported_platform=file_rows_supported,
                        rows_skipped_platform_unmapped=file_rows_skipped,
                        skipped_media_names=dict(sorted(file_skipped_media_names.items())),
                    )
                )

            output_file.flush()
            os.fsync(output_file.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    temp_path.replace(target_path)
    return DirectoryConversionSummary(
        input_root=root,
        input_paths=input_paths,
        output_path=target_path,
        files=tuple(file_summaries),
        rows_seen=rows_seen,
        rows_supported_platform=rows_supported_platform,
        rows_skipped_platform_unmapped=rows_skipped_platform_unmapped,
        skipped_media_names=dict(sorted(skipped_media_names.items())),
    )


def filter_keywords(
    *,
    canonical_path: Path,
    filtered_path: Path,
    keyword_pack_file: Path,
) -> tuple[ContentFilterSummary, int]:
    """加载本工具词包并复用正式 Canonical JSONL 关键词过滤实现。"""

    keyword_pack = load_keyword_pack(keyword_pack_file)
    summary = filter_canonical_content_jsonl(
        input_path=canonical_path,
        output_path=filtered_path,
        keywords=keyword_pack.keywords,
    )
    return summary, keyword_pack.effective_keyword_count


def process_directory(
    *,
    input_dir: Path,
    output_root: Path,
    keyword_pack_file: Path,
    profile_name: str = PROFILE,
    sheet_name: str | None = SHEET_NAME,
    run_id: str | None = None,
) -> MonitoringFilterRunSummary:
    """执行目录发现、五平台转换、关键词过滤、跨文件去重和摘要输出。"""

    input_paths = discover_input_files(input_dir)
    actual_run_id, run_dir = prepare_run_dir(output_root=output_root, run_id=run_id)
    canonical_path = run_dir / "canonical" / "contents.jsonl"
    filtered_path = run_dir / "filtered" / "contents.jsonl"
    deduplicated_path = run_dir / "deduplicated" / "contents.jsonl"

    conversion = convert_supported_platforms(
        input_paths=input_paths,
        input_root=Path(input_dir),
        output_path=canonical_path,
        profile_name=profile_name,
        sheet_name=sheet_name,
    )
    filtering, keyword_count = filter_keywords(
        canonical_path=canonical_path,
        filtered_path=filtered_path,
        keyword_pack_file=keyword_pack_file,
    )
    deduplication = deduplicate_content_jsonl(
        input_path=filtered_path,
        output_path=deduplicated_path,
    )

    run_summary_path = run_dir / "run_summary.json"
    summary = MonitoringFilterRunSummary(
        run_id=actual_run_id,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        input_root=Path(input_dir),
        input_file_count=len(input_paths),
        keyword_count=keyword_count,
        rows_seen=conversion.rows_seen,
        rows_supported_platform=conversion.rows_supported_platform,
        rows_skipped_platform_unmapped=conversion.rows_skipped_platform_unmapped,
        rows_keyword_matched=filtering.rows_written,
        rows_keyword_filtered_out=filtering.rows_filtered_out,
        rows_after_deduplication=deduplication.rows_written,
        duplicates_removed=deduplication.duplicates_removed,
        deduplication_conflicts=deduplication.conflicts,
        skipped_media_names=conversion.skipped_media_names,
        files=conversion.files,
        canonical_path=canonical_path,
        filtered_path=filtered_path,
        deduplicated_path=deduplicated_path,
        deduplication_conflicts_path=deduplication.conflict_path,
    )
    _write_run_summary(summary)
    return summary


def _write_run_summary(summary: MonitoringFilterRunSummary) -> None:
    """把成功完成的整条离线流水线统计原子写入 ``run_summary.json``。"""

    payload: dict[str, object] = {
        "schema_version": "monitoring-excel-filter-run.v1",
        "run_id": summary.run_id,
        "input_root": str(summary.input_root),
        "input_file_count": summary.input_file_count,
        "keyword_count": summary.keyword_count,
        "rows_seen": summary.rows_seen,
        "rows_supported_platform": summary.rows_supported_platform,
        "rows_skipped_platform_unmapped": summary.rows_skipped_platform_unmapped,
        "rows_keyword_matched": summary.rows_keyword_matched,
        "rows_keyword_filtered_out": summary.rows_keyword_filtered_out,
        "rows_after_deduplication": summary.rows_after_deduplication,
        "duplicates_removed": summary.duplicates_removed,
        "deduplication_conflicts": summary.deduplication_conflicts,
        "skipped_media_names": summary.skipped_media_names,
        "files": [
            {
                "source": item.source,
                "rows_seen": item.rows_seen,
                "rows_supported_platform": item.rows_supported_platform,
                "rows_skipped_platform_unmapped": item.rows_skipped_platform_unmapped,
                "skipped_media_names": item.skipped_media_names,
            }
            for item in summary.files
        ],
        "outputs": {
            "canonical": str(summary.canonical_path),
            "filtered": str(summary.filtered_path),
            "deduplicated": str(summary.deduplicated_path),
            "deduplication_conflicts": str(summary.deduplication_conflicts_path),
        },
    }
    _atomic_write_json(summary.run_summary_path, payload)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """使用临时文件、fsync 和原子替换写 JSON，避免发布半截摘要。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _resolve_run_id(run_id: str | None) -> str:
    """生成或校验文件系统安全的人工运行 ID。"""

    value = run_id or beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def _display_media_name(value: Any) -> str:
    """把已确认非空的未映射媒体值转为摘要中的可读名称。"""

    text = "" if value is None else str(value).strip()
    return text or "<unknown>"


def main() -> None:
    """使用文件顶部人工配置执行一次完整目录过滤任务。"""

    summary = process_directory(
        input_dir=INPUT_DIR,
        output_root=OUTPUT_ROOT,
        keyword_pack_file=KEYWORD_PACK_FILE,
    )
    print(
        "监测 Excel 目录处理完成: "
        f"run_id={summary.run_id}, "
        f"input_files={summary.input_file_count}, "
        f"rows_seen={summary.rows_seen}, "
        f"supported={summary.rows_supported_platform}, "
        f"matched={summary.rows_keyword_matched}, "
        f"final={summary.rows_after_deduplication}, "
        f"output={summary.deduplicated_path}"
    )


if __name__ == "__main__":
    main()
