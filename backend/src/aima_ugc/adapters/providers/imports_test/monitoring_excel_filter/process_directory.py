"""监测 Excel 目录批量过滤人工入口。"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from aima_ugc.adapters.providers.imports.excel_profile import get_excel_import_profile
from aima_ugc.adapters.providers.imports.excel_reader import iter_excel_rows
from aima_ugc.adapters.providers.imports.mapper import map_excel_row
from aima_ugc.adapters.providers.imports.models import ExcelImportRowError
from aima_ugc.adapters.providers.imports_test.incremental_state import (
    SHARD_NAMES,
    AppendOnlyShardIndex,
    atomic_write_json,
    content_identity_key,
    iter_completed_run_dirs,
    load_json_object,
    resolve_summary_output,
    sha256_file,
    shard_name,
    state_lock,
)
from aima_ugc.adapters.providers.imports_test.keyword_pack import load_keyword_pack
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.modules.analysis import (
    ContentFilterSummary,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
)
from aima_ugc.platform.time import beijing_now

INPUT_DIR = Path(r"D:\慧科数据")
OUTPUT_ROOT = Path(__file__).with_name("output")
KEYWORD_PACK_FILE = Path(__file__).with_name("keyword_pack.txt")
PROFILE = "aima-monitoring-excel.v1"
SHEET_NAME: str | None = None

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")
_STATE_SCHEMA = "monitoring-excel-filter-state.v1"
_RUN_SCHEMA = "monitoring-excel-filter-run.v2"
_INCREMENTAL_SEMANTICS = "monitoring-incremental.v1"


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
    files_processed: int
    files_skipped_unchanged: int
    files_skipped_duplicate_binary: int
    keyword_count: int
    rows_seen: int
    rows_supported_platform: int
    rows_skipped_platform_unmapped: int
    rows_keyword_matched: int
    rows_keyword_filtered_out: int
    rows_after_deduplication: int
    duplicates_removed: int
    historical_duplicates_removed: int
    deduplication_conflicts: int
    skipped_media_names: dict[str, int]
    files: tuple[SourceFileSummary, ...]
    canonical_path: Path
    filtered_path: Path
    deduplicated_path: Path
    deduplication_conflicts_path: Path
    state_manifest_path: Path
    current_manifest_path: Path


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
        if path.is_file() and path.suffix.casefold() == ".xlsx" and not path.name.startswith("~$")
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
    """自动接管历史 run，只处理新增 Excel 并输出跨 run 全局新增帖子。"""

    input_root = Path(input_dir)
    target_root = Path(output_root)
    discovered_paths = discover_input_files(input_root)
    signature = _pipeline_signature(
        profile_name=profile_name,
        sheet_name=sheet_name,
        keyword_pack_file=Path(keyword_pack_file),
    )

    with state_lock(target_root):
        state, index = _load_and_reconcile_state(
            input_root=input_root,
            output_root=target_root,
            signature=signature,
        )
        process_paths, pending_files, unchanged_count, duplicate_binary_count = _classify_files(
            input_paths=discovered_paths,
            input_root=input_root,
            state=state,
        )
        actual_run_id, run_dir = prepare_run_dir(output_root=target_root, run_id=run_id)
        canonical_path = run_dir / "canonical" / "contents.jsonl"
        filtered_path = run_dir / "filtered" / "contents.jsonl"
        deduplicated_path = run_dir / "deduplicated" / "contents.jsonl"
        within_run_path = run_dir / "deduplicated" / ".within_run.jsonl"
        run_state_delta = run_dir / "state_delta" / "content_index"

        try:
            keyword_count = load_keyword_pack(Path(keyword_pack_file)).effective_keyword_count
            if process_paths:
                conversion = convert_supported_platforms(
                    input_paths=process_paths,
                    input_root=input_root,
                    output_path=canonical_path,
                    profile_name=profile_name,
                    sheet_name=sheet_name,
                )
                filtering, keyword_count = filter_keywords(
                    canonical_path=canonical_path,
                    filtered_path=filtered_path,
                    keyword_pack_file=Path(keyword_pack_file),
                )
                within_run = deduplicate_content_jsonl(
                    input_path=filtered_path,
                    output_path=within_run_path,
                )
                historical_duplicates = _filter_historical_duplicates(
                    input_path=within_run_path,
                    output_path=deduplicated_path,
                    index=index,
                    delta_root=run_state_delta,
                    run_id=actual_run_id,
                )
                within_run_path.unlink(missing_ok=True)
            else:
                _write_empty_jsonl(canonical_path)
                _write_empty_jsonl(filtered_path)
                _write_empty_jsonl(deduplicated_path)
                _write_empty_jsonl(run_dir / "deduplicated" / "deduplication_conflicts.jsonl")
                conversion = DirectoryConversionSummary(
                    input_root=input_root,
                    input_paths=(),
                    output_path=canonical_path,
                    files=(),
                    rows_seen=0,
                    rows_supported_platform=0,
                    rows_skipped_platform_unmapped=0,
                    skipped_media_names={},
                )
                filtering = ContentFilterSummary(
                    input_path=canonical_path,
                    output_path=filtered_path,
                    rows_seen=0,
                    rows_written=0,
                    rows_filtered_out=0,
                )
                within_run = None
                historical_duplicates = 0

            rows_after_deduplication = _count_non_empty_lines(deduplicated_path)
            within_duplicates = 0 if within_run is None else within_run.duplicates_removed
            deduplication_conflicts = 0 if within_run is None else within_run.conflicts
            conflict_path = run_dir / "deduplicated" / "deduplication_conflicts.jsonl"
            state_manifest_path = target_root / "state" / "manifest.json"
            current_manifest_path = target_root / "current" / "manifest.json"
            summary = MonitoringFilterRunSummary(
                run_id=actual_run_id,
                run_dir=run_dir,
                run_summary_path=run_dir / "run_summary.json",
                input_root=input_root,
                input_file_count=len(discovered_paths),
                files_processed=len(process_paths),
                files_skipped_unchanged=unchanged_count,
                files_skipped_duplicate_binary=duplicate_binary_count,
                keyword_count=keyword_count,
                rows_seen=conversion.rows_seen,
                rows_supported_platform=conversion.rows_supported_platform,
                rows_skipped_platform_unmapped=conversion.rows_skipped_platform_unmapped,
                rows_keyword_matched=filtering.rows_written,
                rows_keyword_filtered_out=filtering.rows_filtered_out,
                rows_after_deduplication=rows_after_deduplication,
                duplicates_removed=within_duplicates + historical_duplicates,
                historical_duplicates_removed=historical_duplicates,
                deduplication_conflicts=deduplication_conflicts,
                skipped_media_names=conversion.skipped_media_names,
                files=conversion.files,
                canonical_path=canonical_path,
                filtered_path=filtered_path,
                deduplicated_path=deduplicated_path,
                deduplication_conflicts_path=conflict_path,
                state_manifest_path=state_manifest_path,
                current_manifest_path=current_manifest_path,
            )
            _write_run_summary(
                summary,
                signature=signature,
                pending_files=pending_files,
            )
        except BaseException:
            shutil.rmtree(run_dir, ignore_errors=True)
            raise

        # run_summary 已经证明本次 run 完成；状态即使中断也可由下次 reconcile 从 run 自动恢复。
        index.append_delta_dir(run_state_delta)
        _commit_monitoring_state(
            state=state,
            pending_files=pending_files,
            run_id=actual_run_id,
            state_manifest_path=summary.state_manifest_path,
        )
        _write_current_manifest(target_root, state)
        return summary


def _pipeline_signature(
    *,
    profile_name: str,
    sheet_name: str | None,
    keyword_pack_file: Path,
) -> dict[str, object]:
    """冻结会改变历史过滤结果的配置，配置漂移时禁止静默增量。"""

    return {
        "semantics": _INCREMENTAL_SEMANTICS,
        "profile_name": profile_name,
        "sheet_name": sheet_name,
        "keyword_pack_sha256": sha256_file(keyword_pack_file),
    }


def _load_and_reconcile_state(
    *,
    input_root: Path,
    output_root: Path,
    signature: dict[str, object],
) -> tuple[dict[str, Any], AppendOnlyShardIndex]:
    """读取 state；首次升级时自动从本机旧 runs 建立基线，并修复落后的索引。"""

    state_root = output_root / "state"
    manifest_path = state_root / "manifest.json"
    state = load_json_object(manifest_path)
    if state:
        if state.get("schema_version") != _STATE_SCHEMA:
            raise ValueError(f"不支持的监测增量状态版本: {manifest_path}")
        if state.get("pipeline_signature") != signature:
            raise ValueError(
                "监测 Excel 增量配置已变化（Profile/Sheet/Keyword Pack）；"
                "为避免漏算历史数据，请使用新的 output_root 或人工重建 state"
            )
    else:
        state = {
            "schema_version": _STATE_SCHEMA,
            "pipeline_signature": signature,
            "indexed_runs": [],
            "files": {},
        }

    index = AppendOnlyShardIndex(state_root / "content_index")
    indexed_runs = set(_string_list(state.get("indexed_runs")))
    files = _dict_object(state.get("files"))

    for run_dir in iter_completed_run_dirs(output_root):
        if run_dir.name in indexed_runs:
            continue
        summary = load_json_object(run_dir / "run_summary.json")
        schema = summary.get("schema_version")
        if schema not in {"monitoring-excel-filter-run.v1", _RUN_SCHEMA}:
            continue
        deduplicated = resolve_summary_output(
            run_dir=run_dir,
            summary=summary,
            output_key="deduplicated",
            fallback_relative="deduplicated/contents.jsonl",
        )
        if deduplicated.is_file():
            delta_root = state_root / ".reconcile" / run_dir.name / "content_index"
            _build_identity_delta(
                input_path=deduplicated,
                delta_root=delta_root,
                run_id=run_dir.name,
            )
            index.append_delta_dir(delta_root)
            shutil.rmtree(delta_root.parent.parent, ignore_errors=True)

        decisions = summary.get("file_decisions")
        if isinstance(decisions, list):
            for item in decisions:
                if not isinstance(item, dict) or item.get("status") not in {
                    "processed",
                    "duplicate_binary",
                }:
                    continue
                source = item.get("source")
                if isinstance(source, str) and source and source not in files:
                    files[source] = dict(item)
        else:
            legacy_files = summary.get("files")
            if isinstance(legacy_files, list):
                for item in legacy_files:
                    if not isinstance(item, dict):
                        continue
                    source = item.get("source")
                    if not isinstance(source, str) or not source or source in files:
                        continue
                    source_path = input_root / Path(source)
                    if source_path.is_file():
                        files[source] = _source_fingerprint(
                            source_path,
                            source=source,
                            completed_run_id=run_dir.name,
                            status="processed",
                        )
        indexed_runs.add(run_dir.name)
        state["indexed_runs"] = sorted(indexed_runs)
        state["files"] = files
        atomic_write_json(manifest_path, state)

    state["indexed_runs"] = sorted(indexed_runs)
    state["files"] = files
    atomic_write_json(manifest_path, state)
    return state, index


def _classify_files(
    *,
    input_paths: tuple[Path, ...],
    input_root: Path,
    state: dict[str, Any],
) -> tuple[tuple[Path, ...], dict[str, dict[str, Any]], int, int]:
    """只选择真正新增文件；历史文件变化时 fail closed，二进制复制件直接跳过。"""

    files = _dict_object(state.get("files"))
    known_sha = {
        str(item.get("sha256")): source
        for source, item in files.items()
        if isinstance(item, dict) and isinstance(item.get("sha256"), str)
    }
    process_paths: list[Path] = []
    pending_files: dict[str, dict[str, Any]] = {}
    unchanged_count = 0
    duplicate_binary_count = 0

    for path in input_paths:
        source = path.relative_to(input_root).as_posix()
        stat = path.stat()
        existing = files.get(source)
        if isinstance(existing, dict):
            old_size = existing.get("size")
            old_mtime = existing.get("mtime_ns")
            if old_size == stat.st_size and old_mtime == stat.st_mtime_ns:
                unchanged_count += 1
                continue
            current_sha = sha256_file(path)
            if current_sha == existing.get("sha256"):
                unchanged_count += 1
                pending_files[source] = {
                    **existing,
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
                continue
            raise ValueError(f"已处理 Excel 内容发生变化，增量模式拒绝静默覆盖历史结果: {path}")

        current_sha = sha256_file(path)
        duplicate_of = known_sha.get(current_sha)
        if duplicate_of is not None:
            duplicate_binary_count += 1
            pending_files[source] = {
                "source": source,
                "status": "duplicate_binary",
                "duplicate_of": duplicate_of,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": current_sha,
            }
            continue

        process_paths.append(path)
        pending_files[source] = {
            "source": source,
            "status": "processed",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": current_sha,
        }
        known_sha[current_sha] = source

    return tuple(process_paths), pending_files, unchanged_count, duplicate_binary_count


def _filter_historical_duplicates(
    *,
    input_path: Path,
    output_path: Path,
    index: AppendOnlyShardIndex,
    delta_root: Path,
    run_id: str,
) -> int:
    """按单分片内存上限判重，并按输入原顺序发布跨历史全局新增记录。"""

    partition_root = output_path.parent / ".history_partitions"
    partition_root.mkdir(parents=True, exist_ok=False)
    flags_path = partition_root / "keep_flags.bin"
    writers: dict[str, TextIO] = {}
    try:
        with ExitStack() as stack:
            with input_path.open("rb") as source_file, flags_path.open("wb") as flags_file:
                for line_number, raw_line in enumerate(source_file, start=1):
                    flags_file.write(b"\x00")
                    if not raw_line.strip():
                        continue
                    record = _parse_unified_record(raw_line, input_path, line_number)
                    key = content_identity_key(
                        record.content.platform,
                        record.content.external_content_id,
                    )
                    shard = shard_name(key)
                    writer = writers.get(shard)
                    if writer is None:
                        writer = stack.enter_context(
                            (partition_root / f"{shard}.jsonl").open(
                                "w",
                                encoding="utf-8",
                                newline="\n",
                            )
                        )
                        writers[shard] = writer
                    writer.write(f"{line_number}\t{record.model_dump_json()}\n")
                flags_file.flush()
                os.fsync(flags_file.fileno())
            for writer in writers.values():
                writer.flush()
                os.fsync(writer.fileno())

        historical_duplicates = 0
        delta_root.mkdir(parents=True, exist_ok=True)
        with flags_path.open("r+b") as flags_file:
            for shard in SHARD_NAMES:
                partition = partition_root / f"{shard}.jsonl"
                if not partition.is_file():
                    continue
                known = index.load_shard(shard)
                delta_path = delta_root / f"{shard}.jsonl"
                with (
                    partition.open("r", encoding="utf-8-sig") as part_file,
                    delta_path.open("w", encoding="utf-8", newline="\n") as delta_file,
                ):
                    for partition_line_number, line in enumerate(part_file, start=1):
                        try:
                            source_line_text, record_json = line.rstrip("\n").split("\t", 1)
                            source_line_number = int(source_line_text)
                        except (ValueError, TypeError) as exc:
                            raise ValueError(
                                f"增量历史分片记录非法: {partition}: 第 {partition_line_number} 行"
                            ) from exc
                        record = _parse_unified_record(
                            record_json.encode("utf-8"),
                            partition,
                            partition_line_number,
                        )
                        key = content_identity_key(
                            record.content.platform,
                            record.content.external_content_id,
                        )
                        if key in known:
                            historical_duplicates += 1
                            continue
                        flags_file.seek(source_line_number - 1)
                        flags_file.write(b"\x01")
                        entry = {"key": key, "run_id": run_id}
                        delta_file.write(
                            json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
                        )
                        delta_file.write("\n")
                        known[key] = entry
                    delta_file.flush()
                    os.fsync(delta_file.fileno())
            flags_file.flush()
            os.fsync(flags_file.fileno())

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output_path.with_name(f".{output_path.name}.tmp")
        temp_output.unlink(missing_ok=True)
        try:
            with (
                input_path.open("rb") as source_file,
                flags_path.open("rb") as flags_file,
                temp_output.open("wb") as output_file,
            ):
                for raw_line in source_file:
                    flag = flags_file.read(1)
                    if len(flag) != 1:
                        raise RuntimeError("增量历史判重 flag 数量少于输入行数")
                    if flag == b"\x01":
                        output_file.write(raw_line)
                if flags_file.read(1):
                    raise RuntimeError("增量历史判重 flag 数量多于输入行数")
                output_file.flush()
                os.fsync(output_file.fileno())
            os.replace(temp_output, output_path)
        except BaseException:
            temp_output.unlink(missing_ok=True)
            raise
        return historical_duplicates
    finally:
        shutil.rmtree(partition_root, ignore_errors=True)


def _build_identity_delta(*, input_path: Path, delta_root: Path, run_id: str) -> None:
    """把历史 run 的最终 JSONL 变成可直接并入分片 identity index 的 delta。"""

    shutil.rmtree(delta_root, ignore_errors=True)
    delta_root.mkdir(parents=True, exist_ok=False)
    writers: dict[str, TextIO] = {}
    with ExitStack() as stack, input_path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            record = _parse_unified_record(raw_line, input_path, line_number)
            key = content_identity_key(record.content.platform, record.content.external_content_id)
            shard = shard_name(key)
            writer = writers.get(shard)
            if writer is None:
                writer = stack.enter_context(
                    (delta_root / f"{shard}.jsonl").open("w", encoding="utf-8", newline="\n")
                )
                writers[shard] = writer
            writer.write(json.dumps({"key": key, "run_id": run_id}, ensure_ascii=False))
            writer.write("\n")
        for writer in writers.values():
            writer.flush()
            os.fsync(writer.fileno())


def _parse_unified_record(
    raw_line: bytes,
    path: Path,
    line_number: int,
) -> UnifiedContentRecordV1:
    """校验增量去重输入，索引损坏时带路径和行号失败关闭。"""

    try:
        return UnifiedContentRecordV1.model_validate_json(raw_line)
    except ValueError as exc:
        raise ValueError(f"增量内容 JSONL 非法: {path}: 第 {line_number} 行") from exc


def _source_fingerprint(
    path: Path,
    *,
    source: str,
    completed_run_id: str,
    status: str,
) -> dict[str, Any]:
    """为历史或新增 Excel 保存可验证文件身份。"""

    stat = path.stat()
    return {
        "source": source,
        "status": status,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
        "completed_run_id": completed_run_id,
    }


def _commit_monitoring_state(
    *,
    state: dict[str, Any],
    pending_files: dict[str, dict[str, Any]],
    run_id: str,
    state_manifest_path: Path,
) -> None:
    """成功 run 发布后推进文件 checkpoint；下次仍可从 run 自愈 identity index。"""

    files = _dict_object(state.get("files"))
    for source, item in pending_files.items():
        files[source] = {**item, "completed_run_id": run_id}
    indexed_runs = set(_string_list(state.get("indexed_runs")))
    indexed_runs.add(run_id)
    state["files"] = files
    state["indexed_runs"] = sorted(indexed_runs)
    atomic_write_json(state_manifest_path, state)


def _write_current_manifest(output_root: Path, state: dict[str, Any]) -> None:
    """用轻量 manifest 表示累计历史，避免每次复制数十 GB 的全量 JSONL。"""

    parts: list[dict[str, object]] = []
    total_rows = 0
    for run_dir in iter_completed_run_dirs(output_root):
        summary = load_json_object(run_dir / "run_summary.json")
        if summary.get("schema_version") not in {"monitoring-excel-filter-run.v1", _RUN_SCHEMA}:
            continue
        output = resolve_summary_output(
            run_dir=run_dir,
            summary=summary,
            output_key="deduplicated",
            fallback_relative="deduplicated/contents.jsonl",
        )
        if not output.is_file():
            continue
        rows = summary.get("rows_after_deduplication")
        row_count = rows if isinstance(rows, int) else _count_non_empty_lines(output)
        total_rows += row_count
        parts.append({"run_id": run_dir.name, "path": str(output), "rows": row_count})
    atomic_write_json(
        output_root / "current" / "manifest.json",
        {
            "schema_version": "monitoring-excel-current-manifest.v1",
            "total_rows": total_rows,
            "parts": parts,
            "state_indexed_runs": _string_list(state.get("indexed_runs")),
        },
    )


def _write_run_summary(
    summary: MonitoringFilterRunSummary,
    *,
    signature: dict[str, object],
    pending_files: dict[str, dict[str, Any]],
) -> None:
    """把成功完成的增量流水线统计原子写入 ``run_summary.json``。"""

    processed_sources = {item.source for item in summary.files}
    file_decisions: list[dict[str, Any]] = []
    for source, item in sorted(pending_files.items()):
        decision = dict(item)
        if source in processed_sources:
            decision["status"] = "processed"
        file_decisions.append(decision)
    payload: dict[str, object] = {
        "schema_version": _RUN_SCHEMA,
        "run_id": summary.run_id,
        "input_root": str(summary.input_root),
        "input_file_count": summary.input_file_count,
        "files_processed": summary.files_processed,
        "files_skipped_unchanged": summary.files_skipped_unchanged,
        "files_skipped_duplicate_binary": summary.files_skipped_duplicate_binary,
        "keyword_count": summary.keyword_count,
        "pipeline_signature": signature,
        "rows_seen": summary.rows_seen,
        "rows_supported_platform": summary.rows_supported_platform,
        "rows_skipped_platform_unmapped": summary.rows_skipped_platform_unmapped,
        "rows_keyword_matched": summary.rows_keyword_matched,
        "rows_keyword_filtered_out": summary.rows_keyword_filtered_out,
        "rows_after_deduplication": summary.rows_after_deduplication,
        "duplicates_removed": summary.duplicates_removed,
        "historical_duplicates_removed": summary.historical_duplicates_removed,
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
        "file_decisions": file_decisions,
        "outputs": {
            "canonical": str(summary.canonical_path),
            "filtered": str(summary.filtered_path),
            "deduplicated": str(summary.deduplicated_path),
            "deduplication_conflicts": str(summary.deduplication_conflicts_path),
        },
    }
    atomic_write_json(summary.run_summary_path, payload)


def _write_empty_jsonl(path: Path) -> None:
    """原子创建空 JSONL，no-op run 也保留稳定产物契约。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    with temp.open("wb") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _count_non_empty_lines(path: Path) -> int:
    """流式统计 JSONL 有效记录数。"""

    with Path(path).open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def _dict_object(value: object) -> dict[str, Any]:
    """把状态中的可选 JSON Object 收敛为可修改字典。"""

    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    """读取状态中的字符串列表，忽略非法元素。"""

    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


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
    """使用文件顶部人工配置执行一次可续跑目录过滤任务。"""

    summary = process_directory(
        input_dir=INPUT_DIR,
        output_root=OUTPUT_ROOT,
        keyword_pack_file=KEYWORD_PACK_FILE,
    )
    print(
        "监测 Excel 目录增量处理完成: "
        f"run_id={summary.run_id}, "
        f"input_files={summary.input_file_count}, "
        f"processed_files={summary.files_processed}, "
        f"skipped_unchanged={summary.files_skipped_unchanged}, "
        f"rows_seen={summary.rows_seen}, "
        f"matched={summary.rows_keyword_matched}, "
        f"historical_duplicates={summary.historical_duplicates_removed}, "
        f"new_rows={summary.rows_after_deduplication}, "
        f"output={summary.deduplicated_path}"
    )


if __name__ == "__main__":
    main()
