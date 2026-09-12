"""把跨品牌车型共现 JSONL 无损拆分为五个平台文件。"""

from __future__ import annotations

import json
import os
import re
import shutil
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError

from aima_ugc.adapters.providers.imports_test.vehicle_pair_filter.filter_vehicle_pairs import (
    VehiclePairRecordV1,
)
from aima_ugc.contracts.platform import PLATFORM_NAMES, PlatformName
from aima_ugc.platform.time import beijing_now

INPUT_JSONL = Path(
    r"E:\AIMA_UGC_data\vehicle_pair_filter\output\runs\<run_id>\comparison_posts.jsonl"
)
OUTPUT_ROOT = Path(__file__).with_name("output")

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")


@dataclass(frozen=True, slots=True)
class PlatformSplitRunSummary:
    """记录一次五平台无损拆分的统计和正式产物路径。"""

    run_id: str
    run_dir: Path
    input_path: Path
    run_summary_path: Path
    rows_seen: int
    platform_counts: dict[PlatformName, int]
    output_paths: dict[PlatformName, Path]


def split_by_platform(
    *,
    input_path: Path,
    output_root: Path,
    run_id: str | None = None,
) -> PlatformSplitRunSummary:
    """校验 VehiclePairRecordV1 后按正式 platform 无损拆成五个 JSONL。"""

    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    actual_run_id = _resolve_run_id(run_id)
    root = Path(output_root)
    runs_root = root / "runs"
    final_run_dir = runs_root / actual_run_id
    staging_dir = root / f".staging-{actual_run_id}"

    if final_run_dir.exists():
        raise FileExistsError(f"目标 run 已存在: {final_run_dir}")
    if staging_dir.exists():
        raise FileExistsError(f"staging run 已存在，请先人工确认后清理: {staging_dir}")

    runs_root.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=False)

    staging_paths: dict[PlatformName, Path] = {
        platform: staging_dir / f"{platform}.jsonl" for platform in PLATFORM_NAMES
    }
    output_paths: dict[PlatformName, Path] = {
        platform: final_run_dir / f"{platform}.jsonl" for platform in PLATFORM_NAMES
    }
    platform_counts: dict[PlatformName, int] = {platform: 0 for platform in PLATFORM_NAMES}
    rows_seen = 0

    try:
        with ExitStack() as stack:
            writers: dict[PlatformName, BinaryIO] = {
                item: stack.enter_context(staging_paths[item].open("wb")) for item in PLATFORM_NAMES
            }
            with source_path.open("rb") as source_file:
                for line_number, raw_line in enumerate(source_file, start=1):
                    if not raw_line.strip():
                        continue
                    record = _parse_input_record(
                        raw_line,
                        input_path=source_path,
                        line_number=line_number,
                    )
                    platform = record.record.content.platform
                    if platform not in writers:
                        raise ValueError(
                            f"输入 JSONL 第 {line_number} 行包含非正式平台: {platform!r}"
                        )
                    writers[platform].write(raw_line)
                    platform_counts[platform] += 1
                    rows_seen += 1

            for writer in writers.values():
                writer.flush()
                os.fsync(writer.fileno())

        if rows_seen != sum(platform_counts.values()):
            raise RuntimeError("五平台拆分行数对账失败")

        summary = PlatformSplitRunSummary(
            run_id=actual_run_id,
            run_dir=final_run_dir,
            input_path=source_path,
            run_summary_path=final_run_dir / "run_summary.json",
            rows_seen=rows_seen,
            platform_counts=platform_counts,
            output_paths=output_paths,
        )
        _write_run_summary(staging_dir / "run_summary.json", summary)
        os.replace(staging_dir, final_run_dir)
        return summary
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _parse_input_record(
    raw_line: bytes,
    *,
    input_path: Path,
    line_number: int,
) -> VehiclePairRecordV1:
    """按第二阶段输出模型校验一行输入，并保留明确的行号定位。"""

    try:
        return VehiclePairRecordV1.model_validate_json(raw_line)
    except (ValidationError, ValueError) as exc:
        raise ValueError(
            f"输入 JSONL 第 {line_number} 行不符合 VehiclePairRecordV1: {input_path}"
        ) from exc


def _write_run_summary(path: Path, summary: PlatformSplitRunSummary) -> None:
    """把五平台计数和最终发布路径写入 staging 内的摘要文件。"""

    payload: dict[str, object] = {
        "schema_version": "cross-brand-platform-split-run.v1",
        "run_id": summary.run_id,
        "input": str(summary.input_path),
        "rows_seen": summary.rows_seen,
        "platform_counts": {
            platform: summary.platform_counts[platform] for platform in PLATFORM_NAMES
        },
        "outputs": {platform: str(summary.output_paths[platform]) for platform in PLATFORM_NAMES},
    }
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
        output_file.flush()
        os.fsync(output_file.fileno())


def _resolve_run_id(run_id: str | None) -> str:
    """生成或校验文件系统安全的 run ID。"""

    value = run_id or beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def main() -> None:
    """使用文件顶部人工配置执行一次五平台拆分。"""

    summary = split_by_platform(
        input_path=INPUT_JSONL,
        output_root=OUTPUT_ROOT,
    )
    counts = ", ".join(
        f"{platform}={summary.platform_counts[platform]}" for platform in PLATFORM_NAMES
    )
    print(
        "跨品牌车型共现帖子平台拆分完成: "
        f"run_id={summary.run_id}, rows_seen={summary.rows_seen}, {counts}, "
        f"output={summary.run_dir}"
    )


if __name__ == "__main__":
    main()
